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
# DATA ANALYTICS BACKEND LOGIC ENGINES  (unchanged behavior)
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

# ══════════════════════════════════════════════════════════
# NEW: INFRASTRUCTURE & ROOM UTILISATION ANALYTICS ENGINES
# (purely additive — do not touch solver/backend behaviour)
# ══════════════════════════════════════════════════════════
def calculate_room_workload(timetable_data, rooms_list):
    """Per-room utilisation counts, feeds the new infrastructure bar charts."""
    if not timetable_data:
        return pd.DataFrame(columns=["Room", "Classes Scheduled", "Utilization %"])
    total_slots = 5 * 8  # 5 days x 8 periods, matches stress matrix grid
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
    """Aggregate infra (room) load per day for the new bar chart."""
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
    """Highest composite-stress day/period combinations — surfaces bottlenecks."""
    if stress_df.empty:
        return pd.DataFrame()
    return stress_df.sort_values("Composite Stress Index", ascending=False).head(top_n).reset_index(drop=True)

# ══════════════════════════════════════════════════════════
# APP INITIALIZATION & THEME
# ══════════════════════════════════════════════════════════
st.set_page_config(page_title="Slotra", layout="wide", initial_sidebar_state="expanded")

INITIAL_STATES = {
    "timetable": None, "violations": [], "dark_mode": True, "page": "home",
    "teachers": [], "input_mode": "excel", "splash_done": False,
    "manual_instructors": [{"name": "", "subjects": "", "max_days": 5, "max_periods": 20, "exclusions": ""}]
}
for k, v in INITIAL_STATES.items():
    if k not in st.session_state: st.session_state[k] = v

D = st.session_state.dark_mode
THEME = {
    "bg": "#0B0E14" if D else "#F5F7FA",
    "card": "rgba(22, 28, 45, 0.65)" if D else "rgba(255, 255, 255, 0.9)",
    "accent": "#14A8B7" if D else "#0070F3",
    "accent_neon": "#4FC3F7",
    "text": "#F3F4F6" if D else "#111827",
    "sub": "#9CA3AF" if D else "#4B5563",
    "border": "rgba(20,168,183,0.18)" if D else "rgba(0,112,243,0.18)",
    "grid": "rgba(255,255,255,0.02)" if D else "rgba(0,0,0,0.03)",
    "danger": "#EF4444",
    "success": "#22C55E",
    "warning": "#F59E0B",
}

# ── LOGO ENGINE & CINEMATIC SPLASH ──────────────────────
logo_filename = "slotra_logo.png"
logo_src = f"data:image/png;base64,{base64.b64encode(open(logo_filename, 'rb').read()).decode()}" if os.path.exists(logo_filename) else ""

if not st.session_state.splash_done:
    st.markdown(f"<div class='netflix-preloader' style='position:fixed; inset:0; background:#0B0E14; display:flex; justify-content:center; align-items:center; z-index:999;'><img src='{logo_src}' style='width:200px; border-radius:20px; border:2px solid {THEME['accent']}; animation: pulse 1.8s infinite;'></div>", unsafe_allow_html=True)
    time.sleep(2.0)
    st.session_state.splash_done = True
    st.rerun()

# ══════════════════════════════════════════════════════════
# GLOBAL CSS STYLES
# ══════════════════════════════════════════════════════════
st.markdown(f"""<style>
    .stApp {{background-color: {THEME['bg']}!important; color: {THEME['text']}!important;}}
    .brand-header-center-layer {{display: flex; align-items: center; justify-content: center; gap: 18px; margin: 0 auto 2.5rem auto; padding: 14px 28px; background: #0E131F; border: 2px solid {THEME['accent']}; border-radius: 16px; max-width: fit-content;}}
    .instructor-card {{background: {THEME['card']}; border: 1px solid {THEME['border']}; border-radius: 12px; padding: 1.2rem; margin-bottom: 1rem;}}

    /* ── Top corner bar: date badge (left) + theme toggle (right) ── */
    .topbar-row {{ display:flex; align-items:center; justify-content:space-between; margin-bottom: 0.8rem; }}
    .date-badge {{
        display:flex; align-items:center; gap:10px;
        background: {THEME['card']}; border: 1px solid {THEME['border']};
        border-radius: 999px; padding: 8px 18px; width: fit-content;
        font-family: 'Segoe UI', sans-serif; color: {THEME['text']};
        box-shadow: 0 4px 14px rgba(0,0,0,0.15);
    }}
    .date-badge .dot {{ width:8px; height:8px; border-radius:50%; background:{THEME['success']}; box-shadow: 0 0 8px {THEME['success']}; animation: pulse-dot 1.6s infinite; }}
    @keyframes pulse-dot {{ 0%{{opacity:1}} 50%{{opacity:0.35}} 100%{{opacity:1}} }}
    div[data-testid="stHorizontalBlock"] .stButton>button {{
        border-radius: 999px !important; border: 1px solid {THEME['border']} !important;
        background: {THEME['card']} !important; color: {THEME['text']} !important;
        font-weight: 600 !important; padding: 6px 16px !important;
    }}
    div[data-testid="stHorizontalBlock"] .stButton>button:hover {{
        border-color: {THEME['accent']} !important; color: {THEME['accent']} !important;
    }}

    /* ── Premium metric / analytics cards ── */
    .analytics-card {{
        background: {THEME['card']}; border: 1px solid {THEME['border']};
        border-radius: 14px; padding: 1rem 1.2rem; margin-bottom: 0.6rem;
    }}
    .section-title {{
        font-size: 1.05rem; font-weight: 800; color: {THEME['text']};
        margin: 1.6rem 0 0.4rem 0; padding-left: 4px; border-left: 4px solid {THEME['accent']};
        padding-left: 10px;
    }}
</style>""", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════
# TOP CORNER BAR — live date (top-left) + theme toggle (top-right)
# ══════════════════════════════════════════════════════════
top_left, top_right = st.columns([5, 1])

with top_left:
    # Live, self-updating date/time badge rendered client-side via JS so it
    # always reflects "today" without needing a Streamlit rerun.
    components.html(f"""
    <div id="slotra-date-badge" style="
        display:flex; align-items:center; gap:10px;
        background:{THEME['card']}; border:1px solid {THEME['border']};
        border-radius:999px; padding:8px 18px; width:fit-content;
        font-family:'Segoe UI',sans-serif; color:{THEME['text']}; font-size:13.5px;
        box-shadow:0 4px 14px rgba(0,0,0,0.15);">
        <span style="width:8px;height:8px;border-radius:50%;background:{THEME['success']};
            box-shadow:0 0 8px {THEME['success']};"></span>
        <span id="slotra-date-text" style="font-weight:600;"></span>
    </div>
    <script>
        function renderSlotraDate() {{
            const el = document.getElementById('slotra-date-text');
            if (!el) return;
            const now = new Date();
            const opts = {{ weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' }};
            const timeOpts = {{ hour: '2-digit', minute: '2-digit' }};
            el.innerText = now.toLocaleDateString(undefined, opts) + '  •  ' + now.toLocaleTimeString(undefined, timeOpts);
        }}
        renderSlotraDate();
        setInterval(renderSlotraDate, 1000);
    </script>
    """, height=48)

with top_right:
    toggle_label = "🌙 Dark" if not st.session_state.dark_mode else "☀️ Light"
    if st.button(toggle_label, key="theme_toggle_btn", help="Switch between light and dark mode"):
        st.session_state.dark_mode = not st.session_state.dark_mode
        st.rerun()

# ══════════════════════════════════════════════════════════
# SIDEBAR & MAIN FLOW
# ══════════════════════════════════════════════════════════
with st.sidebar:
    st.markdown("### 🎛️ Spatial & Cohort Setup")
    num_rooms = st.number_input("Number of Rooms", 1, 10, 3)
    rooms_list = [Room(id=f"R{i+1}", name=st.text_input(f"Room {i+1} Name", f"Room {101+i}"), capacity=40) for i in range(num_rooms)]
    num_sections = st.number_input("Number of Sections", 1, 5, 2)
    sections_list = [Section(id=f"SEC_{chr(65+i)}", name=st.text_input(f"Section {chr(65+i)} Name", f"Grade 10-{chr(65+i)}"), strength=35, subject_periods={"Math": 4, "Physics": 4, "Chemistry": 3, "English": 3}) for i in range(num_sections)]

if st.session_state.page == "home":
    st.markdown(f"<div class='brand-header-center-layer'><img src='{logo_src}' style='width:52px; border-radius:8px;'><div style='display:flex; flex-direction:column;'><div style='font-size:28px; font-weight:900;'>SLOTRA</div><div style='color:{THEME['sub']}; font-size:9px;'>PLAN SMART. ACHIEVE MORE.</div></div></div>", unsafe_allow_html=True)
    if st.button("Generate Optimized Timetable", type="primary"):
        # Logic to solve and update session_state.timetable, then set st.session_state.page = "dashboard"
        st.rerun()
else:
    # ══════════════════════════════════════════════════════
    # EXECUTIVE ANALYTICS RENDERING
    # ══════════════════════════════════════════════════════
    st.header("📊 Executive Analytics Suite")
    df = pd.DataFrame(...)  # (Your processed timetable data)

    # 1. METRICS
    c1, c2, c3, c4 = st.columns(4)
    # ... (Your metric cards here)

    # 2. WORKLOAD & PERFORMANCE VISUALS (existing)
    st.markdown("### 📈 Performance & Load Analytics")
    col_a, col_b, col_c = st.columns(3)
    template = "plotly_dark" if D else "plotly"

    with col_a: st.plotly_chart(px.pie(df.groupby("Teacher").size().reset_index(name="Classes"), values='Classes', names='Teacher', title='Workload Distribution', template=template), use_container_width=True)
    with col_b: st.plotly_chart(px.bar(df.groupby("Teacher").size().reset_index(name="Classes"), x='Teacher', y='Classes', title='Class Count per Instructor', template=template), use_container_width=True)
    with col_c: st.plotly_chart(px.box(pd.DataFrame([{"Period": s.timeslot.period + 1} for s in st.session_state.timetable]), y="Period", title="Period Density Analysis", template=template), use_container_width=True)

    # ══════════════════════════════════════════════════════
    # 3. NEW — INFRASTRUCTURE STRESS & WORKLOAD ANALYTICS
    # ══════════════════════════════════════════════════════
    st.markdown(f"<div class='section-title'>🏗️ Infrastructure Stress &amp; Workload Analytics</div>", unsafe_allow_html=True)

    stress_df = calculate_system_stress_matrix(
        st.session_state.timetable or [], total_rooms=num_rooms, total_teachers=len(st.session_state.teachers) or 1
    )
    room_workload_df = calculate_room_workload(st.session_state.timetable or [], rooms_list)
    infra_day_df = calculate_infra_daywise_load(stress_df)
    peak_pressure_df = calculate_peak_pressure_periods(stress_df)

    infra_col1, infra_col2 = st.columns(2)

    with infra_col1:
        st.plotly_chart(
            px.bar(
                infra_day_df, x="Day", y="Total Rooms Used",
                color="Avg Room Saturation %", color_continuous_scale="Tealgrn" if D else "Blues",
                title="Infrastructure Workload by Day", template=template
            ),
            use_container_width=True
        )

    with infra_col2:
        st.plotly_chart(
            px.bar(
                room_workload_df, x="Room", y="Classes Scheduled",
                color="Utilization %", color_continuous_scale="Oranges",
                title="Room-wise Utilization", template=template
            ),
            use_container_width=True
        )

    # Composite stress heatmap — Day x Period pressure map
    if not stress_df.empty:
        heat_pivot = stress_df.pivot(index="Period", columns="Day", values="Composite Stress Index")
        day_order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
        heat_pivot = heat_pivot[[d for d in day_order if d in heat_pivot.columns]]
        st.plotly_chart(
            px.imshow(
                heat_pivot, text_auto=True, aspect="auto",
                color_continuous_scale="Inferno" if D else "YlOrRd",
                title="Composite Stress Heatmap (Day × Period)", template=template
            ),
            use_container_width=True
        )

    # Peak pressure table + workload equity metric
    eq_col1, eq_col2 = st.columns([2, 1])
    with eq_col1:
        st.markdown("**🔥 Top Pressure Slots**")
        if not peak_pressure_df.empty:
            st.dataframe(peak_pressure_df, use_container_width=True, hide_index=True)
        else:
            st.caption("No timetable data yet — generate a timetable to see pressure hotspots.")

    with eq_col2:
        gini = calculate_workload_inequality_gini(df, st.session_state.teachers) if not df.empty else 0.0
        st.metric("Workload Equity (Gini)", gini, help="0 = perfectly balanced, 1 = fully unequal teacher load")

    # ══════════════════════════════════════════════════════
    # 4. NEW — COHORT FATIGUE & SUBJECT DISTRIBUTION ANALYTICS
    # ══════════════════════════════════════════════════════
    st.markdown(f"<div class='section-title'>🧠 Cohort Fatigue &amp; Subject Distribution</div>", unsafe_allow_html=True)

    fatigue_col1, fatigue_col2 = st.columns([1, 1])
    fatigue_df = analyze_subject_fatigue_index(df) if not df.empty else pd.DataFrame()

    with fatigue_col1:
        st.markdown("**📋 Fatigue Cluster Report**")
        if not fatigue_df.empty:
            st.dataframe(fatigue_df, use_container_width=True, hide_index=True)
        else:
            st.caption("No section data available yet.")

    with fatigue_col2:
        if not df.empty and "Subject" in df.columns:
            st.plotly_chart(
                px.sunburst(
                    df, path=["Section", "Subject"], title="Subject Load Breakdown by Section",
                    template=template
                ),
                use_container_width=True
            )
        else:
            st.caption("Subject breakdown will appear once a timetable is generated.")

    if st.button("← Modify Constraints / Inputs"):
        st.session_state.page = "home"
        st.rerun()
