import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import streamlit as st
import pandas as pd
import plotly.express as px
import base64
import numpy as np
from datetime import datetime
from src.models import Teacher, Room, Section, Constraint
from src.solver import TimetableSolver
from src.constraints import check_hard_constraints

# ── DATA ANALYTICS BACKEND LOGIC ENGINES ────────────────
def calculate_system_stress_matrix(timetable_data, total_rooms, total_teachers):
    """
    Analyzes spatial and resource allocations to spot density anomalies.
    """
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
                "Room Saturation %": round(room_pct, 1),
                "Staff Saturation %": round(teach_pct, 1),
                "Composite Stress Index": round(stress_index, 1)
            })
            
    return pd.DataFrame(analysis_records)


def analyze_subject_fatigue_index(df_records):
    """
    Calculates the statistical distribution variance of subjects across days.
    """
    if df_records.empty:
        return pd.DataFrame()
        
    clump_check = df_records.groupby(["Section", "Day", "Subject"]).size().reset_index(name="DailyCount")
    variance_report = []
    
    for section in clump_check["Section"].unique():
        sec_data = clump_check[clump_check["Section"] == section]
        std_dev = sec_data["DailyCount"].std()
        max_back_to_back = sec_data["DailyCount"].max()
        
        status = "Optimal"
        if max_back_to_back >= 3 or std_dev > 1.2:
            status = "🚨 Fatigue Cluster Risk"
            
        variance_report.append({
            "Cohort Section": section,
            "Distribution StdDev": round(std_dev, 2) if not pd.isna(std_dev) else 0.0,
            "Peak Daily Frequency": int(max_back_to_back),
            "Balance Status": status
        })
        
    return pd.DataFrame(variance_report)


def calculate_workload_inequality_gini(df_records, total_teachers_list):
    """
    Computes the statistical Gini Coefficient of workload distribution.
    0.0 = Absolute Balance, 1.0 = Maximized Structural Inequality
    """
    if df_records.empty:
        return 0.0
    counts_map = df_records.groupby("Teacher").size().to_dict()
    all_workloads = [counts_map.get(t.name, 0) for t in total_teachers_list]
        
    array = np.array(all_workloads, dtype=float)
    if len(array) == 0 or array.sum() == 0:
        return 0.0
        
    array = np.sort(array)
    index = np.arange(1, array.shape[0] + 1)
    n = array.shape[0]
    gini = ((np.sum((2 * index - n - 1) * array)) / (n * np.sum(array)))
    return round(gini, 3)


# ── APP INITIALIZATION ─────────────────────────────────
st.set_page_config(
    page_title="Slotra", 
    layout="wide", 
    page_icon=None, 
    initial_sidebar_state="collapsed"
)

INITIAL_STATES = {
    "timetable": None, "violations": [], "dark_mode": True, "page": "splash",
    "teachers": [], "rooms": [], "sections": [],
    "simulation_headroom": 3,
    "teacher_rows": [
        {"name": "Mr. Kumar", "subjects": "Math,Physics", "max_days": 5, "max_periods": 22, "unavailable": "0:1,4:7"},
        {"name": "Ms. Priya", "subjects": "English", "max_days": 4, "max_periods": 18, "unavailable": "1:0,1:1"},
        {"name": "Mr. Rajan", "subjects": "Science", "max_days": 5, "max_periods": 20, "unavailable": ""},
        {"name": "Ms. Deepa", "subjects": "Computer Science", "max_days": 3, "max_periods": 12, "unavailable": "2:4"},
        {"name": "Mr. Arjun", "subjects": "History,Geography", "max_days": 5, "max_periods": 20, "unavailable": ""},
    ],
    "room_rows": [
        {"id": "R101", "name": "Room 101", "capacity": 40},
        {"id": "R102", "name": "Room 102", "capacity": 40},
        {"id": "R103", "name": "Room 103", "capacity": 35},
    ],
    "section_rows": [
        {"id": "10A", "name": "Class 10 A", "strength": 35, "subjects": "Math:5,English:5,Science:4,History:3,Geography:3"},
        {"id": "10B", "name": "Class 10 B", "strength": 33, "subjects": "Math:5,English:5,Science:4,History:3,Geography:3"},
        {"id": "11A", "name": "Class 11 A", "strength": 30, "subjects": "Math:5,English:4,Science:4,Computer Science:4,History:3"},
    ]
}

for key, val in INITIAL_STATES.items():
    if key not in st.session_state:
        st.session_state[key] = val

@st.cache_data(show_spinner=False)
def get_base64_logo():
    logo_path = os.path.join(os.path.dirname(__file__), "slotra_logo.png")
    if os.path.exists(logo_path):
        with open(logo_path, "rb") as f:
            return base64.b64encode(f.read()).decode()
    return ""

logo_b64 = get_base64_logo()
D = st.session_state.dark_mode

THEME = {
    "bg": "#0B0E14" if D else "#F5F7FA",
    "card": "rgba(22, 28, 45, 0.65)" if D else "rgba(255, 255, 255, 0.9)",
    "card2": "rgba(30, 41, 67, 0.4)" if D else "rgba(240, 244, 255, 0.7)",
    "accent": "#4FC3F7" if D else "#0070F3",
    "accent_rgb": "79, 195, 247" if D else "0, 112, 243",
    "text": "#F3F4F6" if D else "#111827",
    "sub": "#9CA3AF" if D else "#4B5563",
    "border": "rgba(79,195,247,0.18)" if D else "rgba(0,112,243,0.15)",
    "grid": "rgba(255,255,255,0.02)" if D else "rgba(0,0,0,0.025)"
}

st.markdown(f"""
<style>
    section[data-testid="stSidebar"] {{display:none;}}
    #MainMenu, footer, header {{visibility:hidden;}}
    .stApp {{background-color: {THEME['bg']}!important; color: {THEME['text']}!important; font-family: 'Inter', sans-serif;}}
    .block-container {{padding: 1rem 3rem 3rem !important; max-width: 1400px;}}
    .grid-bg {{position:fixed; inset:0; pointer-events:none; z-index:0; background-image: linear-gradient({THEME['grid']} 1px, transparent 1px), linear-gradient(90deg, {THEME['grid']} 1px, transparent 1px); background-size: 32px 32px;}}
    .topbar {{display:flex; align-items:center; justify-content:space-between; padding: 1rem 0; border-bottom:1px solid {THEME['border']}; margin-bottom:1.5rem; position:relative; z-index:10;}}
    .logo-img {{width:44px; height:44px; border-radius:10px; box-shadow: 0 4px 12px rgba(0,0,0,0.2);}}
    .hero-section {{text-align:center; padding: 2.5rem 0 1.5rem; position:relative; z-index:1;}}
    .hero-title {{font-size: 56px; font-weight: 800; color: {THEME['text']}; letter-spacing: -2px; margin-bottom: 0px; font-family: 'JetBrains Mono', monospace;}}
    .hero-sub {{font-size: 14px; color: {THEME['accent']}; text-transform: uppercase; letter-spacing: 0.15em; font-weight: 600; margin-bottom: 2rem;}}
    .stat-row {{display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; max-width: 600px; margin: 0 auto 2.5rem;}}
    .stat-cell {{background: {THEME['card']}; border: 1px solid {THEME['border']}; backdrop-filter: blur(8px); padding: 1.2rem; text-align: center; border-radius: 12px; transition: transform 0.2s;}}
    .stat-cell:hover {{transform: translateY(-2px); border-color: {THEME['accent']};}}
    .stat-num {{font-size: 32px; font-weight: 800; color: {THEME['text']}; font-family: 'JetBrains Mono', monospace;}}
    .stat-lbl {{font-size: 10px; color: {THEME['sub']}; text-transform: uppercase; letter-spacing: .08em; margin-top: 4px; font-weight: 600;}}
    .feat-grid {{display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 14px; margin-bottom: 2.5rem;}}
    .fc {{background: {THEME['card']}; border: 1px solid {THEME['border']}; backdrop-filter: blur(10px); border-radius: 14px; padding: 1.2rem; transition: all 0.25s;}}
    .fc:hover {{border-color: {THEME['accent']}AA; box-shadow: 0 8px 24px rgba({THEME['accent_rgb']}, 0.08); transform: translateY(-3px);}}
    .fi {{font-size: 22px; margin-bottom: 8px; color: {THEME['accent']};}}
    .ft {{font-size: 14px; font-weight: 700; color: {THEME['text']}; margin-bottom: 4px;}}
    .fd {{font-size: 12px; color: {THEME['sub']}; line-height: 1.5;}}
    .section-header-panel {{background: {THEME['card2']}; border: 1px solid {THEME['border']}; border-radius: 12px; padding: 14px 20px; margin: 1.5rem 0 0.75rem; display: flex; align-items: center; justify-content: space-between;}}
    .row-container {{background: {THEME['card']}; border: 1px solid {THEME['border']}; border-radius: 10px; padding: 16px; margin-bottom: 12px; transition: border-color 0.2s;}}
    .row-container:hover {{border-color: rgba({THEME['accent_rgb']}, 0.4);}}
    .field-label {{font-size: 10px; font-weight: 700; color: {THEME['sub']}; text-transform: uppercase; letter-spacing: .06em; margin-bottom: 5px;}}
    .hint-tag {{font-size: 9px; color: {THEME['accent']}; background: rgba({THEME['accent_rgb']}, 0.1); padding: 1px 6px; border-radius: 4px; margin-left: 6px;}}
    div[data-testid="stTextInput"]>div>div>input, div[data-testid="stNumberInput"]>div>div>input {{ background-color: {THEME['bg']}!important; border: 1px solid {THEME['border']}!important; color: {THEME['text']}!important; border-radius: 8px!important; padding: 0.4rem 0.75rem!important;}}
    div[data-testid="stButton"]>button[kind="primary"] {{ background: linear-gradient(135deg, {THEME['accent']} 0%, #0051B3 100%)!important; color: #FFFFFF!important; border: none!important; border-radius: 10px!important; font-size: 14px!important; font-weight: 700!important; padding: 0.75rem 2.5rem!important; letter-spacing: .05em!important; text-transform: uppercase; box-shadow: 0 4px 20px rgba({THEME['accent_rgb']}, 0.25)!important; transition: all 0.2s!important; width: 100%;}}
    div[data-testid="stButton"]>button:not([kind="primary"]) {{ font-size: 12px!important; border-radius: 8px!important; border: 1px solid {THEME['border']}!important; background: {THEME['card2']}!important; color: {THEME['text']}!important; font-weight: 600!important; transition: all 0.2s!important;}}
    #splash {{position:fixed; inset:0; z-index:99999; background:#07090E; display:flex; flex-direction:column; align-items:center; justify-content:center; animation:splashFade 0.4s ease 1.4s forwards;}}
    @keyframes splashFade {{ 0% {{opacity:1;}} 100% {{opacity:0; pointer-events:none;}} }}
    .splash-logo {{width:90px; height:90px; border-radius:22px; object-fit:cover; animation:splashPop 0.5s cubic-bezier(.34,1.56,.64,1) both; box-shadow: 0 0 40px rgba(79,195,247,0.4);}}
    .splash-name {{font-size:32px; font-weight:800; color:#FFFFFF; letter-spacing:-1px; font-family:'JetBrains Mono', monospace; margin-top:16px;}}
    .splash-bar {{width:40px; height:2px; border-radius:999px; background: {THEME['accent']}; margin-top:12px;}}
</style>
<div class="grid-bg"></div>
""", unsafe_allow_html=True)

if st.session_state.page == "splash":
    if logo_b64:
        st.markdown(f"""
        <div id="splash">
          <img class="splash-logo" src="data:image/png;base64,{logo_b64}" alt="Slotra Core Loading"/>
          <div class="splash-name">SLOTRA</div>
          <div class="splash-bar"></div>
        </div>
        <script>
          setTimeout(function(){{
            var s=document.getElementById('splash');
            if(s) s.style.display='none';
          }}, 1600);
        </script>""", unsafe_allow_html=True)
    st.session_state.page = "home"
    import time; time.sleep(1.4)
    st.rerun()

logo_html = f'<img class="logo-img" src="data:image/png;base64,{logo_b64}" alt="Slotra"/>' if logo_b64 else f'<div style="font-size:24px; font-weight:900; color:{THEME["accent"]}; font-family:\'JetBrains Mono\'">Slotra</div>'

col_tl, col_tr = st.columns([4, 2])
with col_tl:
    st.markdown(f'<div class="topbar"><div>{logo_html}</div></div>', unsafe_allow_html=True)
with col_tr:
    st.markdown(f"""
    <div style="display:flex; align-items:center; justify-content:flex-end; gap:14px; padding-top:.6rem;">
      <div style="text-align:right; border-right:2px solid {THEME['accent']}50; padding-right:12px;">
        <div style="font-size:12px; font-weight:700; color:{THEME['accent']}; line-height:1.2; text-transform:uppercase; letter-spacing:0.05em;">{datetime.now().strftime("%A")}</div>
        <div style="font-size:10px; color:{THEME['sub']}; font-family:\'JetBrains Mono\'">{datetime.now().strftime("%d %b %Y")}</div>
      </div>
    </div>""", unsafe_allow_html=True)
    if st.button("☀️" if D else "🌙", key="theme_toggle"):
        st.session_state.dark_mode = not st.session_state.dark_mode
        st.rerun()

# ════════════════════════════════════════════════════════
#  HOME PROFILE SECTION (CONFIGURATION ARCHITECTURE)
# ════════════════════════════════════════════════════════
if st.session_state.page == "home":
    tt = st.session_state.timetable
    viol = st.session_state.violations
    
    st.markdown(f"""
    <div class="hero-section">
      <div class="hero-title">SLOTRA</div>
      <div class="hero-sub">High-Performance Combinatorial Timetable Clustering Engine</div>
    </div>
    <div class="stat-row">
      <div class="stat-cell"><div class="stat-num">{len(tt) if tt else 0}</div><div class="stat-lbl">Active Assignments</div></div>
      <div class="stat-cell"><div class="stat-num" style="color: {'#FF5252' if viol else THEME['accent']}">{len(viol) if viol else 0}</div><div class="stat-lbl">Clash Violations</div></div>
      <div class="stat-cell"><div class="stat-num">{len(st.session_state.section_rows)}</div><div class="stat-lbl">Class Sections</div></div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown(f"<div class='section-header-panel'><span style='font-size:14px; font-weight:700;'>Instructor Resource Matrix</span></div>", unsafe_allow_html=True)
    
    @st.fragment
    def render_teachers():
        for i, row in enumerate(st.session_state.teacher_rows):
            st.markdown(f"<div class='row-container'><div class='field-label'>Resource #{i+1:02d}</div>", unsafe_allow_html=True)
            c1, c2 = st.columns([2, 3])
            with c1:
                st.session_state.teacher_rows[i]["name"] = st.text_input("Name", value=row.get("name", ""), key=f"tn_v3_{i}", label_visibility="collapsed")
            with c2:
                st.session_state.teacher_rows[i]["subjects"] = st.text_input("Subjects", value=row.get("subjects", ""), key=f"ts_v3_{i}", label_visibility="collapsed")
            
            st.markdown("<div style='margin-top: 8px;'></div>", unsafe_allow_html=True)
            c3, c4, c5, c6 = st.columns([1.2, 1.2, 2.2, 0.4])
            with c3:
                st.session_state.teacher_rows[i]["max_days"] = st.number_input("Max Days", min_value=1, max_value=5, value=int(row.get("max_days", 5)), key=f"tmd_v3_{i}", label_visibility="collapsed")
            with c4:
                st.session_state.teacher_rows[i]["max_periods"] = st.number_input("Max Periods", min_value=1, max_value=40, value=int(row.get("max_periods", 20)), key=f"tmp_v3_{i}", label_visibility="collapsed")
            with c5:
                st.session_state.teacher_rows[i]["unavailable"] = st.text_input("Exclusions", value=row.get("unavailable", ""), key=f"tu_v3_{i}", label_visibility="collapsed")
            with c6:
                if st.button("✕", key=f"td_v3_{i}"):
                    st.session_state.teacher_rows.pop(i)
                    st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)
    render_teachers()
    
    if st.button("＋ Append Instructor Entry", key="add_teacher_btn"):
        st.session_state.teacher_rows.append({"name": "", "subjects": "", "max_days": 5, "max_periods": 20, "unavailable": ""})
        st.rerun()

    st.markdown(f"<div class='section-header-panel'><span style='font-size:14px; font-weight:700;'>Spatial Infrastructure Allocations</span></div>", unsafe_allow_html=True)
    @st.fragment
    def render_rooms():
        for i, row in enumerate(st.session_state.room_rows):
            st.markdown(f"<div class='row-container'><div class='field-label'>Location Unit #{i+1:02d}</div>", unsafe_allow_html=True)
            c1, c2, c3, c4 = st.columns([1.5, 2.5, 1.5, 0.4])
            with c1: st.session_state.room_rows[i]["id"] = st.text_input("ID", value=row["id"], key=f"ri_v2_{i}", label_visibility="collapsed")
            with c2: st.session_state.room_rows[i]["name"] = st.text_input("Name", value=row["name"], key=f"rn_v2_{i}", label_visibility="collapsed")
            with c3: st.session_state.room_rows[i]["capacity"] = st.number_input("Capacity", value=row["capacity"], min_value=1, key=f"rc_v2_{i}", label_visibility="collapsed")
            with c4:
                if st.button("✕", key=f"rd_v2_{i}"):
                    st.session_state.room_rows.pop(i)
                    st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)
    render_rooms()

    if st.button("＋ Append Location Unit", key="add_room_btn"):
        st.session_state.room_rows.append({"id": "", "name": "", "capacity": 30})
        st.rerun()

    st.markdown(f"<div class='section-header-panel'><span style='font-size:14px; font-weight:700;'>Cohort Curriculum Parameters</span></div>", unsafe_allow_html=True)
    @st.fragment
    def render_sections():
        for i, row in enumerate(st.session_state.section_rows):
            st.markdown(f"<div class='row-container'><div class='field-label'>Cohort Section #{i+1:02d}</div>", unsafe_allow_html=True)
            c1, c2, c3, c4, c5 = st.columns([1.2, 1.8, 1.2, 4, 0.4])
            with c1: st.session_state.section_rows[i]["id"] = st.text_input("ID", value=row["id"], key=f"si_v2_{i}", label_visibility="collapsed")
            with c2: st.session_state.section_rows[i]["name"] = st.text_input("Name", value=row["name"], key=f"sn_v2_{i}", label_visibility="collapsed")
            with c3: st.session_state.section_rows[i]["strength"] = st.number_input("Strength", value=row["strength"], min_value=1, key=f"ss_v2_{i}", label_visibility="collapsed")
            with c4: st.session_state.section_rows[i]["subjects"] = st.text_input("Load Map", value=row["subjects"], key=f"sb_v2_{i}", label_visibility="collapsed")
            with c5:
                if st.button("✕", key=f"sd_v2_{i}"):
                    st.session_state.section_rows.pop(i)
                    st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)
    render_sections()

    if st.button("＋ Append Cohort Parameters", key="add_sec_btn"):
        st.session_state.section_rows.append({"id": "", "name": "", "strength": 30, "subjects": ""})
        st.rerun()

    st.markdown("<br><br>", unsafe_allow_html=True)
    _, center_btn_col, _ = st.columns([1.5, 2, 1.5])
    with center_btn_col:
        execute_solver = st.button("Execute Hard-Constraint Optimization", type="primary")

    if execute_solver:
        teachers_list = []
        for i, r in enumerate(st.session_state.teacher_rows):
            if not r["name"].strip(): continue
            subjs = [s.strip() for s in r["subjects"].split(",") if s.strip()]
            raw_unavail = r.get("unavailable", "")
            parsed_exclusions = []
            if raw_unavail.strip():
                for block in raw_unavail.split(","):
                    if ":" in block:
                        try:
                            d_idx, p_idx = block.strip().split(":")
                            parsed_exclusions.append((int(d_idx), int(p_idx)))
                        except ValueError: pass
            
            teacher_obj = Teacher(id=f"T{i+1:03d}", name=r["name"].strip(), subjects=subjs, unavailable=parsed_exclusions)
            teacher_obj.max_days = int(r.get("max_days", 5))
            teacher_obj.max_periods = int(r.get("max_periods", 20))
            teachers_list.append(teacher_obj)

        rooms_list = [Room(id=r["id"].strip(), name=r["name"].strip(), capacity=int(r["capacity"])) for r in st.session_state.room_rows if r["id"].strip()]
        
        sections_list = []
        for r in st.session_state.section_rows:
            if not r["id"].strip(): continue
            sp_map = {}
            for token in r["subjects"].split(","):
                if ":" in token:
                    p = token.rsplit(":", 1)
                    try: sp_map[p[0].strip()] = int(p[1].strip())
                    except: pass
            sections_list.append(Section(id=r["id"].strip(), name=r["name"].strip(), strength=int(r["strength"]), subject_periods=sp_map))

        if not teachers_list or not rooms_list or not sections_list:
            st.error("Engine Refusal: Ensure all data matrices contain structural properties.")
        else:
            with st.spinner("Processing Linear Matrix Arrays..."):
                try:
                    solver = TimetableSolver(teachers_list, rooms_list, sections_list)
                    solver.create_variables()
                    solver.add_coverage_constraint()
                    solver.add_section_no_clash()
                    solver.add_teacher_no_clash()
                    solver.add_room_no_clash()
                    
                    generated_tt = solver.solve()
                    calculated_violations = check_hard_constraints(generated_tt, teachers_list, rooms_list)
                    
                    st.session_state.update({
                        "timetable": generated_tt, "violations": calculated_violations,
                        "teachers": teachers_list, "rooms": rooms_list, "sections": sections_list,
                        "page": "dashboard"
                    })
                    st.rerun()
                except Exception as e: st.error(f"Solver Engine Compilation Fault: {e}")

# ════════════════════════════════════════════════════════
#  EXECUTIVE MANAGEMENT DASHBOARD PANELS
# ════════════════════════════════════════════════════════
else:
    teachers, rooms = st.session_state.teachers, st.session_state.rooms
    sections, timetable = st.session_state.sections, st.session_state.timetable
    violations = st.session_state.violations

    col_back, col_regen = st.columns([1, 1])
    with col_back:
        if st.button("← Revert to Schema Parameters"):
            st.session_state.page = "home"
            st.rerun()
    with col_regen:
        if st.button("🔄 Recalculate Combinatorics Matrix", type="primary"):
            with st.spinner("Re-solving..."):
                try:
                    solver = TimetableSolver(teachers, rooms, sections)
                    solver.create_variables(); solver.add_coverage_constraint(); solver.add_section_no_clash(); solver.add_teacher_no_clash(); solver.add_room_no_clash()
                    st.session_state.timetable = solver.solve()
                    st.session_state.violations = check_hard_constraints(st.session_state.timetable, teachers, rooms)
                    st.rerun()
                except Exception as e: st.error(f"Fault: {e}")

    st.markdown("<br>", unsafe_allow_html=True)
    
    # Process structured baseline frame variables
    days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
    processed_records = []
    for allocation in timetable:
        matched_teacher = next((t for t in teachers if t.id == allocation.teacher_id), None)
        processed_records.append({
            "Section": allocation.section_id, "Subject": allocation.subject,
            "Teacher": matched_teacher.name if matched_teacher else allocation.teacher_id,
            "Room": allocation.room_id, "Day": days[allocation.timeslot.day],
            "DayN": allocation.timeslot.day, "PerN": allocation.timeslot.period + 1,
            "Period": f"Period {allocation.timeslot.period + 1}"
        })
    df = pd.DataFrame(processed_records)
    if not df.empty: df = df.sort_values(["DayN", "PerN"])

    # Execute dynamic advanced compute backend algorithms
    stress_df = calculate_system_stress_matrix(timetable, len(rooms), len(teachers))
    fatigue_df = analyze_subject_fatigue_index(df)
    gini_val = calculate_workload_inequality_gini(df, teachers)

    # Upper KPI Panels
    c1, c2, c3, c4 = st.columns(4)
    metrics_schema = [
        (len(timetable), "Total Load Placements"),
        (len(violations), "Conflict Anomalies"),
        (f"{gini_val:.3f}", "Workload Gini Coefficient"),
        (f"{stress_df['Composite Stress Index'].mean():.1f}%", "Mean System Stress Index")
    ]
    for idx, (metric, label) in enumerate(metrics_schema):
        with [c1, c2, c3, c4][idx]:
            color = "color: #FF5252;" if (idx == 1 and len(violations) > 0) or (idx == 2 and gini_val > 0.4) else f"color: {THEME['accent']};"
            st.markdown(f"<div style='background:{THEME['card']}; border:1px solid {THEME['border']}; border-radius:12px; padding:1.2rem; text-align:center;'><div style=\"font-size:32px; font-weight:800; font-family:'JetBrains Mono'; {color}\">{metric}</div><div style='font-size:10px; color:{THEME['sub']}; text-transform:uppercase; font-weight:600; margin-top:4px;'>{label}</div></div>", unsafe_allow_html=True)

    # ── TELEMETRY NLP REASONING SYSTEM ──
    st.markdown("<br>", unsafe_allow_html=True)
    with st.container():
        peak_stress_row = stress_df.loc[stress_df['Composite Stress Index'].idxmax()] if not stress_df.empty else None
        stress_text = f"Highest operational density is localized on <b>{peak_stress_row['Day']} {peak_stress_row['Period']}</b> with a stress factor of <b>{peak_stress_row['Composite Stress Index']}%</b>." if peak_stress_row is not None else ""
        st.markdown(f"""
        <div style="background: {THEME['card2']}; border: 1px solid {THEME['accent']}40; border-radius: 12px; padding: 18px;">
            <span style="color: {THEME['accent']}; font-weight: 700; font-size: 11px; text-transform: uppercase; letter-spacing: 0.08em;">📊 Deep-Data Automated Insights Engine</span>
            <p style="margin: 8px 0 0 0; font-size: 13px; color: {THEME['text']}; line-height: 1.6;">
                The platform contains an infrastructure footprint of <b>{len(rooms)} location structures</b> mapping <b>{len(timetable)} slots</b>. 
                Our workload inequality profile indicates a <b>Gini factor of {gini_val:.3f}</b>, implying an {"equitable distribution of operational hours across active instructors." if gini_val <= 0.3 else "uneven concentration of assignments that may require redistribution."}
                {stress_text}
            </p>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)
    if not violations: st.success("Enterprise Status Validation Check: PASS (100% Conflict-Free Structural Integrity)")
    else:
        st.error(f"Anomaly Alert: {len(violations)} Hard-Overlap Violations found inside solver bounds.")
        for v in violations: st.caption(f"⚠ {v}")

    # Tabs Interfaces
    t1, t2, t3, t4, t5, t6 = st.tabs([
        "📅 Schedule Matrices", "👨‍🏫 Staff Workloads", "📊 Structural Density Analytics", 
        "🧠 Curriculum Balance", "🎛️ What-If Control Studio", "📥 Export Hub"
    ])

    with t1:
        chosen_section = st.selectbox("Select Target Cohort Section Array", [s.id for s in sections], key="sec_select")
        filtered_df = df[df["Section"] == chosen_section].copy() if not df.empty else pd.DataFrame()
        
        if not filtered_df.empty:
            unique_subjects = filtered_df["Subject"].unique().tolist()
            palette_colors = px.colors.qualitative.G10 if D else px.colors.qualitative.Pastel
            color_map = {subj: palette_colors[i % len(palette_colors)] for i, subj in enumerate(unique_subjects)}
            
            schedule_grid = {day: {f"P{p}": "" for p in range(1, 9)} for day in days}
            for _, r in filtered_df.iterrows():
                schedule_grid[r["Day"]][f"P{r['PerN']}"] = f"{r['Subject']} \n ({r['Teacher']} // {r['Room']})"
                
            styled_grid_df = pd.DataFrame(schedule_grid, index=[f"P{p}" for p in range(1, 9)])
            def apply_cell_coloring(cell_value):
                if not cell_value: return ""
                subject_key = cell_value.split(" \n ")[0]
                text_color = "#FFFFFF" if D else "#000000"
                return f"background-color: {color_map.get(subject_key, '#888888')}35; color: {text_color}; font-weight:600; border-left: 3px solid {color_map.get(subject_key, '#888')};"
            st.dataframe(styled_grid_df.style.map(apply_cell_coloring), use_container_width=True, height=340)

    with t2:
        chosen_teacher = st.selectbox("Select Target Instructor Interface", [t.name for t in teachers], key="tch_select")
        teacher_df = df[df["Teacher"] == chosen_teacher].copy() if not df.empty else pd.DataFrame()
        if not teacher_df.empty:
            workload_per_day = teacher_df.groupby("Day").size().reindex(days, fill_value=0).reset_index(name="Periods")
            fig_t = px.bar(workload_per_day, x="Day", y="Periods", color="Periods", color_continuous_scale="Sunset" if D else "Blues")
            fig_t.update_layout(plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)", font_color=THEME['text'], height=240)
            st.plotly_chart(fig_t, use_container_width=True)
            st.dataframe(teacher_df[["Day", "Period", "Section", "Subject", "Room"]].reset_index(drop=True), use_container_width=True)

    with t3:
        st.markdown("### System-Wide Operational Stress Matrix")
        fig_stress = px.density_heatmap(stress_df, x="Period", y="Day", z="Composite Stress Index", color_continuous_scale="Viridis" if D else "YlGnBu")
        fig_stress.update_layout(plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)", font_color=THEME['text'], height=280)
        st.plotly_chart(fig_stress, use_container_width=True)
        st.dataframe(stress_df, use_container_width=True)

    with t4:
        st.markdown("### Cohort Structural Fatigue Analysis")
        st.caption("Tracks the deviation coefficients of curriculum subjects to evaluate pacing uniformity.")
        st.dataframe(fatigue_df, use_container_width=True)
        
        if not fatigue_df.empty:
            fig_fatigue = px.bar(fatigue_df, x="Cohort Section", y="Distribution StdDev", color="Balance Status", color_discrete_map={"Optimal": THEME['accent'], "🚨 Fatigue Cluster Risk": "#FF5252"})
            fig_fatigue.update_layout(plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)", font_color=THEME['text'], height=240)
            st.plotly_chart(fig_fatigue, use_container_width=True)

    with t5:
        st.markdown("### Resource Overhead Simulation Studio")
        sim_val = st.slider("Hypothetical Capacity Buffer Target (Periods)", min_value=1, max_value=10, value=st.session_state.simulation_headroom)
        st.session_state.simulation_headroom = sim_val
        
        sim_records = []
        for t in teachers:
            current_allocated = len(df[df["Teacher"] == t.name]) if not df.empty else 0
            allowed_max = getattr(t, 'max_periods', 20)
            sim_headroom = allowed_max - current_allocated - sim_val
            sim_records.append({
                "Instructor": t.name, "Allocated Load": current_allocated,
                "Configured Max": allowed_max, "Simulated Headroom": sim_headroom,
                "Status Flag": "✓ OPTIMAL" if sim_headroom >= 0 else "⚠️ SATURATED"
            })
        st.dataframe(pd.DataFrame(sim_records), use_container_width=True)

    with t6:
        st.markdown("### Production File Pipeline Generation Engine")
        if not df.empty:
            for sc_obj in sections:
                section_export_df = df[df["Section"] == sc_obj.id][["Day", "Period", "Subject", "Teacher", "Room"]].reset_index(drop=True)
                st.download_button(label=f"📥 Bulk Transmit Data: Class {sc_obj.id} (CSV)", data=section_export_df.to_csv(index=False), file_name=f"matrix_timetable_{sc_obj.id}.csv", mime="text/csv", key=f"dl_v2_{sc_obj.id}")
            st.markdown("<div style='margin: 1.5rem 0;'></div>", unsafe_allow_html=True)
            st.download_button(label="📊 Transmit Enterprise Master Database Array (All Channels)", data=df[["Section", "Day", "Period", "Subject", "Teacher", "Room"]].reset_index(drop=True).to_csv(index=False), file_name="complete_master_timetable.csv", mime="text/csv", key="dl_v2_all_master", use_container_width=True)

st.markdown(f"""<br><p align="center"><img src="https://capsule-render.vercel.app/api?type=rect&color={THEME['accent'].replace('#', '')}&height=6&section=footer&radius=2" width="100%" /></p>""", unsafe_allow_html=True)