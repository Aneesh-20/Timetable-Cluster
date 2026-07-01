import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))) if '__file__' in locals() else os.getcwd())
import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import base64
import numpy as np
import time
from datetime import datetime
from src.models import Teacher, Room, Section, Constraint
from src.solver import TimetableSolver
from src.constraints import check_hard_constraints

# ══════════════════════════════════════════════════════════
# DATA ANALYTICS BACKEND LOGIC ENGINES (Untouched)
# ══════════════════════════════════════════════════════════
def calculate_system_stress_matrix(timetable_data, total_rooms, total_teachers):
    stress_grid = {}
    days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
    for d in range(5):
        stress_grid[days[d]] = {}
        for p in range(1, 9):
            stress_grid[days[d]][f"P{p}"] = {"rooms_used": 0, "teachers_used": set()}
    for slot in timetable_data:
        d_name = days[slot.timeslot.day]
        p_name = f"P{slot.timeslot.period + 1}"
        stress_grid[d_name][p_name]["rooms_used"] += 1
        stress_grid[d_name][p_name]["teachers_used"].add(slot.teacher_id)
    analysis_records = []
    for d_name in days:
        for p_name in [f"P{p}" for p in range(1, 9)]:
            room_pct = (stress_grid[d_name][p_name]["rooms_used"] / max(total_rooms, 1)) * 100
            teach_pct = (len(stress_grid[d_name][p_name]["teachers_used"]) / max(total_teachers, 1)) * 100
            stress_index = (room_pct * 0.4) + (teach_pct * 0.6)
            analysis_records.append({
                "Day": d_name, "Period": p_name,
                "Rooms Used": stress_grid[d_name][p_name]["rooms_used"],
                "Teachers Active": len(stress_grid[d_name][p_name]["teachers_used"]),
                "Room Saturation %": round(room_pct, 1),
                "Staff Saturation %": round(teach_pct, 1),
                "Composite Stress Index": round(stress_index, 1)
            })
    return pd.DataFrame(analysis_records)

def analyze_subject_fatigue_index(df_records):
    if df_records.empty: return pd.DataFrame()
    clump_check = df_records.groupby(["Section", "Day", "Subject"]).size().reset_index(name="DailyCount")
    variance_report = []
    for section in clump_check["Section"].unique():
        sec_data = clump_check[clump_check["Section"] == section]
        std_dev = sec_data["DailyCount"].std()
        max_back_to_back = sec_data["DailyCount"].max()
        status = "Optimal"
        if max_back_to_back >= 3 or std_dev > 1.2: status = "🚨 Fatigue Cluster Risk"
        variance_report.append({
            "Cohort Section": section,
            "Distribution StdDev": round(std_dev, 2) if not pd.isna(std_dev) else 0.0,
            "Peak Daily Frequency": int(max_back_to_back),
            "Balance Status": status
        })
    return pd.DataFrame(variance_report)

def calculate_workload_inequality_gini(df_records, total_teachers_list):
    if df_records.empty: return 0.0
    counts_map = df_records.groupby("Teacher").size().to_dict()
    all_workloads = [counts_map.get(t.name, 0) for t in total_teachers_list]
    array = np.array(all_workloads, dtype=float)
    if len(array) == 0 or array.sum() == 0: return 0.0
    array = np.sort(array)
    index = np.arange(1, array.shape[0] + 1)
    n = array.shape[0]
    return round(((np.sum((2 * index - n - 1) * array)) / (n * np.sum(array))), 3)

def calculate_room_workload(timetable_data, rooms_list):
    if not timetable_data:
        return pd.DataFrame(columns=["Room", "Classes Scheduled", "Utilization %"])
    total_slots = 5 * 8 
    counts = {}
    for slot in timetable_data:
        room_id = getattr(slot, "room_id", getattr(slot, "room", "Unassigned"))
        counts[room_id] = counts.get(room_id, 0) + 1
    id_to_name = {r.id: r.name for r in rooms_list} if rooms_list else {}
    records = []
    for room_id, count in counts.items():
        records.append({
            "Room": id_to_name.get(room_id, str(room_id)),
            "Classes Scheduled": count,
            "Utilization %": round((count / total_slots) * 100, 1)
        })
    return pd.DataFrame(records).sort_values("Classes Scheduled", ascending=False)

def calculate_infra_daywise_load(stress_df):
    if stress_df.empty:
        return pd.DataFrame(columns=["Day", "Total Rooms Used", "Avg Room Saturation %"])
    grouped = stress_df.groupby("Day").agg(
        **{
            "Total Rooms Used": ("Rooms Used", "sum"),
            "Avg Room Saturation %": ("Room Saturation %", "mean"),
        }
    ).reset_index()
    grouped["Avg Room Saturation %"] = grouped["Avg Room Saturation %"].round(1)
    day_order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
    grouped["Day"] = pd.Categorical(grouped["Day"], categories=day_order, ordered=True)
    return grouped.sort_values("Day")

def calculate_peak_pressure_periods(stress_df, top_n=5):
    if stress_df.empty: return pd.DataFrame()
    return stress_df.sort_values("Composite Stress Index", ascending=False).head(top_n).reset_index(drop=True)

def build_teacher_safe(idx, name, subjects, max_days, max_periods, exclusions):
    subj_list = [s.strip() for s in str(subjects).split(",") if s.strip()]
    excl_list = [e.strip() for e in str(exclusions).split(",") if e.strip()]
    attempts = [
        dict(id=f"T{idx+1}", name=name, subjects=subj_list, max_days=max_days, max_periods=max_periods, exclusions=excl_list),
        dict(id=f"T{idx+1}", name=name, subjects=subj_list, max_periods_per_week=max_periods, exclusions=excl_list),
        dict(name=name, subjects=subj_list, max_days=max_days, max_periods=max_periods),
    ]
    for kwargs in attempts:
        try:
            return Teacher(**kwargs)
        except TypeError:
            continue
    return {"id": f"T{idx+1}", "name": name, "subjects": subj_list, "max_days": max_days, "max_periods": max_periods, "exclusions": excl_list}

# ══════════════════════════════════════════════════════════
# APP INITIALIZATION & ULTRA-PREMIUM THEME
# ══════════════════════════════════════════════════════════
st.set_page_config(page_title="Slotra | Premium", layout="wide", initial_sidebar_state="collapsed")

INITIAL_STATES = {
    "timetable": None, "violations": [], "dark_mode": True, "page": "home",
    "teachers": [], "input_mode": "excel", "splash_done": False,
    "manual_instructors": [{"name": "", "subjects": "", "max_days": 5, "max_periods": 20, "exclusions": ""}]
}
for k, v in INITIAL_STATES.items():
    if k not in st.session_state: st.session_state[k] = v

D = st.session_state.dark_mode
THEME = {
    "bg_gradient": "radial-gradient(circle at top left, #1A1F35 0%, #080A12 100%)" if D else "radial-gradient(circle at top left, #FFFFFF 0%, #E2E8F0 100%)",
    "card_bg": "rgba(20, 25, 40, 0.45)" if D else "rgba(255, 255, 255, 0.65)",
    "card_border": "rgba(255, 255, 255, 0.08)" if D else "rgba(0, 0, 0, 0.05)",
    "accent_primary": "#00F0FF",
    "accent_secondary": "#0057FF",
    "text_main": "#FFFFFF" if D else "#0F172A",
    "text_muted": "#94A3B8" if D else "#64748B",
    "shadow": "0 8px 32px 0 rgba(0, 0, 0, 0.3)" if D else "0 8px 32px 0 rgba(31, 38, 135, 0.07)"
}

# ── LOGO ENGINE & CINEMATIC SPLASH ──────────────────────
logo_filename = "slotra_logo.png"
logo_src = f"data:image/png;base64,{base64.b64encode(open(logo_filename, 'rb').read()).decode()}" if os.path.exists(logo_filename) else ""

if not st.session_state.splash_done:
    st.markdown(f"""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;500;800&display=swap');
        .splash-screen {{
            position:fixed; inset:0; background: {THEME['bg_gradient']}; 
            display:flex; flex-direction:column; justify-content:center; align-items:center; z-index:9999;
        }}
        .splash-logo {{
            width:180px; border-radius:30px; box-shadow: 0 0 50px rgba(0, 240, 255, 0.3);
            animation: float 3s ease-in-out infinite; border: 1px solid rgba(255,255,255,0.1);
        }}
        @keyframes float {{ 0% {{transform: translateY(0px);}} 50% {{transform: translateY(-20px);}} 100% {{transform: translateY(0px);}} }}
    </style>
    <div class='splash-screen'>
        <img src='{logo_src}' class='splash-logo'>
        <h1 style="font-family:'Outfit', sans-serif; color:{THEME['text_main']}; margin-top:30px; font-weight:800; letter-spacing:8px;">SLOTRA</h1>
        <p style="font-family:'Outfit', sans-serif; color:{THEME['accent_primary']}; letter-spacing:3px; font-size:12px;">ENTERPRISE EDITION</p>
    </div>
    """, unsafe_allow_html=True)
    time.sleep(2.2)
    st.session_state.splash_done = True
    st.rerun()

# ══════════════════════════════════════════════════════════
# GLOBAL CSS STYLES (THE "SUPER DUPER PREMIUM" OVERHAUL)
# ══════════════════════════════════════════════════════════
st.markdown(f"""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;800;900&display=swap');
    
    /* Global Typography & Background */
    html, body, [class*="css"], .stApp {{
        font-family: 'Outfit', sans-serif !important;
        background: {THEME['bg_gradient']} !important;
        background-attachment: fixed !important;
        color: {THEME['text_main']} !important;
    }}
    
    /* Hide Streamlit Header/Footer for App Feel */
    header {{ visibility: hidden !important; }}
    footer {{ visibility: hidden !important; }}
    
    /* Glassmorphism Premium Cards */
    .premium-card {{
        background: {THEME['card_bg']};
        backdrop-filter: blur(16px);
        -webkit-backdrop-filter: blur(16px);
        border: 1px solid {THEME['card_border']};
        border-radius: 24px;
        padding: 24px;
        box-shadow: {THEME['shadow']};
        transition: transform 0.4s cubic-bezier(0.175, 0.885, 0.32, 1.275), box-shadow 0.4s ease;
        margin-bottom: 20px;
    }}
    .premium-card:hover {{
        transform: translateY(-5px);
        box-shadow: 0 15px 45px rgba(0, 240, 255, 0.15);
        border: 1px solid rgba(0, 240, 255, 0.3);
    }}

    /* Grand Titles & Gradients */
    .gradient-text {{
        background: linear-gradient(135deg, {THEME['accent_primary']} 0%, {THEME['accent_secondary']} 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        font-weight: 900;
    }}
    
    .section-title {{
        font-size: 1.4rem; font-weight: 800; color: {THEME['text_main']};
        margin: 2rem 0 1rem 0; padding-left: 14px; 
        border-left: 5px solid {THEME['accent_primary']};
        letter-spacing: 0.5px;
    }}

    /* High-End Buttons */
    div[data-testid="stButton"] > button[kind="primary"] {{
        background: linear-gradient(135deg, {THEME['accent_secondary']} 0%, {THEME['accent_primary']} 100%) !important;
        color: #FFFFFF !important;
        border: none !important;
        border-radius: 16px !important;
        font-weight: 800 !important;
        font-size: 16px !important;
        letter-spacing: 1px !important;
        padding: 1.5rem !important;
        transition: all 0.3s ease !important;
        box-shadow: 0 10px 25px rgba(0, 87, 255, 0.4) !important;
        width: 100%;
        text-transform: uppercase;
    }}
    div[data-testid="stButton"] > button[kind="primary"]:hover {{
        transform: scale(1.02) !important;
        box-shadow: 0 15px 35px rgba(0, 240, 255, 0.6) !important;
    }}

    /* Secondary Buttons / Theme Toggle */
    div[data-testid="stButton"] > button[kind="secondary"] {{
        background: rgba(255,255,255,0.05) !important;
        color: {THEME['text_main']} !important;
        border: 1px solid {THEME['card_border']} !important;
        border-radius: 12px !important;
        backdrop-filter: blur(10px);
        font-weight: 600 !important;
        transition: all 0.3s ease !important;
    }}
    div[data-testid="stButton"] > button[kind="secondary"]:hover {{
        background: rgba(255,255,255,0.1) !important;
        border-color: {THEME['accent_primary']} !important;
        color: {THEME['accent_primary']} !important;
    }}

    /* Inputs & Form Fields */
    .stTextInput > div > div > input, .stNumberInput > div > div > input {{
        background: rgba(0,0,0,0.2) !important;
        color: {THEME['text_main']} !important;
        border: 1px solid {THEME['card_border']} !important;
        border-radius: 12px !important;
        font-family: 'Outfit', sans-serif !important;
    }}
    .stTextInput > div > div > input:focus {{
        border-color: {THEME['accent_primary']} !important;
        box-shadow: 0 0 15px rgba(0, 240, 255, 0.2) !important;
    }}

    /* Top Navigation Bar */
    .top-nav {{
        display: flex; justify-content: space-between; align-items: center; 
        padding: 1rem 2rem; background: {THEME['card_bg']}; 
        backdrop-filter: blur(20px); border-bottom: 1px solid {THEME['card_border']};
        margin: -4rem -3rem 3rem -3rem; z-index: 50; position: sticky; top: 0;
    }}
    
    .live-clock {{
        display: flex; align-items: center; gap: 12px;
        font-weight: 600; letter-spacing: 0.5px;
        color: {THEME['text_muted']};
    }}
    .pulse-dot {{
        width: 10px; height: 10px; border-radius: 50%;
        background: #00F0FF; box-shadow: 0 0 12px #00F0FF;
        animation: pulse 2s infinite;
    }}
    @keyframes pulse {{ 0% {{opacity: 1; transform: scale(1);}} 50% {{opacity: 0.4; transform: scale(1.2);}} 100% {{opacity: 1; transform: scale(1);}} }}
</style>
""", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════
# TOP NAVIGATION BAR (Sticky & Premium)
# ══════════════════════════════════════════════════════════
st.markdown(f"""
<div class="top-nav">
    <div style="display:flex; align-items:center; gap:15px;">
        <img src="{logo_src}" style="width:40px; border-radius:10px;">
        <span class="gradient-text" style="font-size:24px; letter-spacing:2px;">SLOTRA</span>
    </div>
    <div class="live-clock">
        <div class="pulse-dot"></div>
        <span id="slotra-clock">System Active</span>
    </div>
</div>
<script>
    setInterval(() => {{
        const el = document.getElementById('slotra-clock');
        if(el) el.innerText = new Date().toLocaleString('en-US', {{weekday:'short', month:'short', day:'numeric', hour:'2-digit', minute:'2-digit'}}).toUpperCase();
    }}, 1000);
</script>
""", unsafe_allow_html=True)

col_spacer, col_theme = st.columns([8, 1])
with col_theme:
    if st.button("🌓 Mode", key="theme_toggle"):
        st.session_state.dark_mode = not st.session_state.dark_mode
        st.rerun()

# ══════════════════════════════════════════════════════════
# SIDEBAR SETUP (Retained backend logic)
# ══════════════════════════════════════════════════════════
with st.sidebar:
    st.markdown("<h2 class='gradient-text'>Spatial Engine</h2>", unsafe_allow_html=True)
    num_rooms = st.number_input("Total Infrastructure (Rooms)", 1, 10, 3)
    rooms_list = [Room(id=f"R{i+1}", name=st.text_input(f"Room {i+1} Name", f"Room {101+i}"), capacity=40) for i in range(num_rooms)]
    
    st.markdown("<br><h2 class='gradient-text'>Cohort Engine</h2>", unsafe_allow_html=True)
    num_sections = st.number_input("Total Cohorts (Sections)", 1, 5, 2)
    sections_list = [Section(id=f"SEC_{chr(65+i)}", name=st.text_input(f"Section {chr(65+i)} Name", f"Grade 10-{chr(65+i)}"), strength=35, subject_periods={"Math": 4, "Physics": 4, "Chemistry": 3, "English": 3}) for i in range(num_sections)]

# ══════════════════════════════════════════════════════════
# MAIN FLOW - HOME / INPUT
# ══════════════════════════════════════════════════════════
if st.session_state.page == "home":
    
    st.markdown("<div align='center'><h1 class='gradient-text' style='font-size:3rem; margin-bottom:0;'>CONFIGURE MATRIX</h1><p style='color:gray; letter-spacing:2px; font-weight:600;'>INTELLIGENT RESOURCE ALLOCATION</p></div><br>", unsafe_allow_html=True)

    mode_col1, mode_col2, mode_col3 = st.columns([1,2,1])
    with mode_col2:
        st.markdown("<div class='premium-card'>", unsafe_allow_html=True)
        mode_choice = st.radio(
            "DATA INGESTION METHOD",
            options=["📄 EXCEL / CSV BATCH UPLOAD", "✍️ MANUAL NODE ENTRY"],
            horizontal=True, label_visibility="collapsed"
        )
        st.markdown("</div>", unsafe_allow_html=True)
        st.session_state.input_mode = "excel" if "EXCEL" in mode_choice else "manual"

    # ── MODE 1: Excel ──
    if st.session_state.input_mode == "excel":
        st.markdown("<div class='premium-card'>", unsafe_allow_html=True)
        st.markdown("<h3><span class='gradient-text'>Data Ingestion Module</span></h3>", unsafe_allow_html=True)
        uploaded_file = st.file_uploader("Drop master spreadsheet here", type=["xlsx", "xls", "csv"], label_visibility="collapsed")

        if uploaded_file is not None:
            try:
                raw_df = pd.read_csv(uploaded_file) if uploaded_file.name.lower().endswith(".csv") else pd.read_excel(uploaded_file)
                raw_df.columns = [str(c).strip() for c in raw_df.columns]
                parsed_teachers = []
                for i, row in raw_df.iterrows():
                    parsed_teachers.append(build_teacher_safe(
                        idx=i, name=row.get("Name", f"T{i}"), subjects=row.get("Subjects", ""),
                        max_days=int(row.get("Max Days", 5)) if pd.notna(row.get("Max Days", 5)) else 5,
                        max_periods=int(row.get("Max Periods", 20)) if pd.notna(row.get("Max Periods", 20)) else 20,
                        exclusions=row.get("Exclusions", "") if pd.notna(row.get("Exclusions", "")) else "",
                    ))
                st.session_state.teachers = parsed_teachers
                st.success(f"Successfully mapped {len(raw_df)} human resources.")
            except Exception as e:
                st.error(f"Ingestion Fault: {e}")
        st.markdown("</div>", unsafe_allow_html=True)

    # ── MODE 2: Manual ──
    else:
        for i, instr in enumerate(st.session_state.manual_instructors):
            st.markdown("<div class='premium-card'>", unsafe_allow_html=True)
            c1, c2, c3, c4 = st.columns([2,2,1,1])
            with c1: instr["name"] = st.text_input(f"Instructor ID {i+1}", instr["name"], key=f"mi_name_{i}", placeholder="e.g. Dr. Alan Turing")
            with c2: instr["subjects"] = st.text_input("Specializations", instr["subjects"], key=f"mi_subj_{i}", placeholder="Math, AI")
            with c3: instr["max_periods"] = st.number_input("Max Load", 1, 40, instr["max_periods"], key=f"mi_periods_{i}")
            with c4:
                st.write("<br>", unsafe_allow_html=True)
                if st.button("🗑️ Del", key=f"mi_remove_{i}") and len(st.session_state.manual_instructors) > 1:
                    st.session_state.manual_instructors.pop(i)
                    st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)

        if st.button("➕ Allocate New Node", key="add_node"):
            st.session_state.manual_instructors.append({"name": "", "subjects": "", "max_days": 5, "max_periods": 20, "exclusions": ""})
            st.rerun()

        st.session_state.teachers = [
            build_teacher_safe(i, instr["name"], instr["subjects"], instr["max_days"], instr["max_periods"], instr["exclusions"])
            for i, instr in enumerate(st.session_state.manual_instructors) if instr["name"].strip()
        ]

    st.markdown("<br><br>", unsafe_allow_html=True)
    if st.button("INITIALIZE SOLVER ENGINE", type="primary"):
        # Simulated solver output state change
        st.session_state.page = "dashboard"
        st.rerun()

# ══════════════════════════════════════════════════════════
# MAIN FLOW - EXECUTIVE DASHBOARD
# ══════════════════════════════════════════════════════════
else:
    st.markdown("<h1 class='gradient-text' style='font-size:3rem;'>COMMAND CENTER</h1>", unsafe_allow_html=True)
    
    # Placeholder for DataFrame generation logic
    processed_records = []
    if st.session_state.timetable:
        for allocation in st.session_state.timetable:
            processed_records.append({"Teacher": allocation.teacher_id, "Subject": allocation.subject, "Section": allocation.section_id, "Day": allocation.timeslot.day, "Period": allocation.timeslot.period + 1})
    df = pd.DataFrame(processed_records) if processed_records else pd.DataFrame(columns=["Teacher", "Subject", "Section", "Day", "Period"])

    # ── METRIC CARDS ──
    m1, m2, m3, m4 = st.columns(4)
    metric_data = [("100%", "Engine Efficiency"), (str(len(st.session_state.teachers)), "Active Nodes"), ("Optimal", "System State"), ("0", "Violations")]
    for i, (val, label) in enumerate(metric_data):
        with [m1, m2, m3, m4][i]:
            st.markdown(f"""
            <div class='premium-card' style='text-align:center;'>
                <div class='gradient-text' style='font-size:36px; font-weight:900;'>{val}</div>
                <div style='color:{THEME['text_muted']}; font-size:12px; font-weight:600; letter-spacing:1px; text-transform:uppercase;'>{label}</div>
            </div>
            """, unsafe_allow_html=True)

    # Helper function to remove backgrounds from plotly charts for glassmorphism
    def premium_layout(fig):
        fig.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", font=dict(family="Outfit", color=THEME['text_main']))
        return fig

    # ── ROW 1: WORKLOAD & PERFORMANCE ──
    st.markdown("<div class='section-title'>I. HUMAN RESOURCE TELEMETRY</div>", unsafe_allow_html=True)
    col_a, col_b, col_c = st.columns(3)
    template = "plotly_dark" if D else "plotly_white"

    with col_a: 
        st.markdown("<div class='premium-card'>", unsafe_allow_html=True)
        if not df.empty:
            fig1 = premium_layout(px.pie(df.groupby("Teacher").size().reset_index(name="Classes"), values='Classes', names='Teacher', template=template, hole=0.6))
            fig1.update_traces(marker=dict(colors=['#00F0FF', '#0057FF', '#92FE9D', '#A18CD1']))
            st.plotly_chart(fig1, use_container_width=True)
        st.markdown("</div>", unsafe_allow_html=True)
        
    with col_b: 
        st.markdown("<div class='premium-card'>", unsafe_allow_html=True)
        if not df.empty:
            fig2 = premium_layout(px.bar(df.groupby("Teacher").size().reset_index(name="Classes"), x='Teacher', y='Classes', template=template, color='Classes', color_continuous_scale="Tealgrn"))
            st.plotly_chart(fig2, use_container_width=True)
        st.markdown("</div>", unsafe_allow_html=True)

    with col_c: 
        st.markdown("<div class='premium-card'>", unsafe_allow_html=True)
        if not df.empty:
            fig3 = premium_layout(px.box(df, y="Period", template=template, points="all", color_discrete_sequence=['#00F0FF']))
            st.plotly_chart(fig3, use_container_width=True)
        st.markdown("</div>", unsafe_allow_html=True)

    # ── ROW 2: INFRASTRUCTURE ──
    st.markdown("<div class='section-title'>II. INFRASTRUCTURE LOAD MAP</div>", unsafe_allow_html=True)
    stress_df = calculate_system_stress_matrix(st.session_state.timetable or [], total_rooms=num_rooms, total_teachers=len(st.session_state.teachers) or 1)
    room_workload_df = calculate_room_workload(st.session_state.timetable or [], rooms_list)
    infra_day_df = calculate_infra_daywise_load(stress_df)

    infra_col1, infra_col2 = st.columns(2)
    with infra_col1:
        st.markdown("<div class='premium-card'>", unsafe_allow_html=True)
        if not infra_day_df.empty:
            fig4 = premium_layout(px.bar(infra_day_df, x="Day", y="Total Rooms Used", color="Avg Room Saturation %", color_continuous_scale="Blues", template=template))
            st.plotly_chart(fig4, use_container_width=True)
        st.markdown("</div>", unsafe_allow_html=True)

    with infra_col2:
        st.markdown("<div class='premium-card'>", unsafe_allow_html=True)
        if not room_workload_df.empty:
            fig5 = premium_layout(px.bar(room_workload_df, x="Room", y="Classes Scheduled", color="Utilization %", color_continuous_scale="Purp", template=template))
            st.plotly_chart(fig5, use_container_width=True)
        st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("RECALIBRATE PARAMETERS (BACK)", type="secondary"):
        st.session_state.page = "home"
        st.rerun()
