import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import streamlit as st
import pandas as pd
import plotly.express as px
import base64
from datetime import datetime
from src.models import Teacher, Room, Section, Constraint
from src.solver import TimetableSolver
from src.constraints import check_hard_constraints

# ── APP INITIALIZATION ─────────────────────────────────
st.set_page_config(
    page_title="Slotra // Enterprise", 
    layout="wide", 
    page_icon="⚡", 
    initial_sidebar_state="collapsed"
)

# Initialize global state variables elegantly
INITIAL_STATES = {
    "timetable": None, "violations": [], "dark_mode": True, "page": "splash",
    "teachers": [], "rooms": [], "sections": [],
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

# ── PREMIUM ENGINE CORES (CACHING & OPTIMIZATION) ─────
@st.cache_data(show_spinner=False)
def get_base64_logo():
    logo_path = os.path.join(os.path.dirname(__file__), "slotra_logo.png")
    if os.path.exists(logo_path):
        with open(logo_path, "rb") as f:
            return base64.b64encode(f.read()).decode()
    return ""

logo_b64 = get_base64_logo()
D = st.session_state.dark_mode

# Advanced design tokens (Dynamic Palette System)
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

# Injection of High-Performance CSS Layout Engine
st.markdown(f"""
<style>
    section[data-testid="stSidebar"] {{display:none;}}
    #MainMenu, footer, header {{visibility:hidden;}}
    .stApp {{background-color: {THEME['bg']}!important; color: {THEME['text']}!important; font-family: 'Inter', sans-serif;}}
    .block-container {{padding: 1rem 3rem 3rem !important; max-width: 1400px;}}
    
    /* Premium Glassmorphic Grid */
    .grid-bg {{position:fixed; inset:0; pointer-events:none; z-index:0;
        background-image: linear-gradient({THEME['grid']} 1px, transparent 1px), linear-gradient(90deg, {THEME['grid']} 1px, transparent 1px);
        background-size: 32px 32px;}}
    
    /* Topbar Layout & Elements */
    .topbar {{display:flex; align-items:center; justify-content:space-between; padding: 1rem 0; border-bottom:1px solid {THEME['border']}; margin-bottom:1.5rem; position:relative; z-index:10;}}
    .logo-img {{width:44px; height:44px; border-radius:10px; box-shadow: 0 4px 12px rgba(0,0,0,0.2);}}
    
    /* Hero Modern Typography */
    .hero-section {{text-align:center; padding: 2.5rem 0 1.5rem; position:relative; z-index:1;}}
    .hero-title {{font-size: 56px; font-weight: 800; color: {THEME['text']}; letter-spacing: -2px; margin-bottom: 0px; font-family: 'JetBrains Mono', monospace;}}
    .hero-sub {{font-size: 14px; color: {THEME['accent']}; text-transform: uppercase; letter-spacing: 0.15em; font-weight: 600; margin-bottom: 2rem;}}
    
    /* Executive Metric Dashboards */
    .stat-row {{display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; max-width: 600px; margin: 0 auto 2.5rem;}}
    .stat-cell {{background: {THEME['card']}; border: 1px solid {THEME['border']}; backdrop-filter: blur(8px); padding: 1.2rem; text-align: center; border-radius: 12px; transition: transform 0.2s;}}
    .stat-cell:hover {{transform: translateY(-2px); border-color: {THEME['accent']};}}
    .stat-num {{font-size: 32px; font-weight: 800; color: {THEME['text']}; font-family: 'JetBrains Mono', monospace;}}
    .stat-lbl {{font-size: 10px; color: {THEME['sub']}; text-transform: uppercase; letter-spacing: .08em; margin-top: 4px; font-weight: 600;}}

    /* Split Architecture Custom Microcards */
    .feat-grid {{display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 14px; margin-bottom: 2.5rem;}}
    .fc {{background: {THEME['card']}; border: 1px solid {THEME['border']}; backdrop-filter: blur(10px); border-radius: 14px; padding: 1.2rem; transition: all 0.25s;}}
    .fc:hover {{border-color: {THEME['accent']}AA; box-shadow: 0 8px 24px rgba({THEME['accent_rgb']}, 0.08); transform: translateY(-3px);}}
    .fi {{font-size: 22px; margin-bottom: 8px; color: {THEME['accent']};}}
    .ft {{font-size: 14px; font-weight: 700; color: {THEME['text']}; margin-bottom: 4px;}}
    .fd {{font-size: 12px; color: {THEME['sub']}; line-height: 1.5;}}

    /* Data Input System Layouts */
    .section-header-panel {{background: {THEME['card2']}; border: 1px solid {THEME['border']}; border-radius: 12px; padding: 14px 20px; margin: 1.5rem 0 0.75rem; display: flex; align-items: center; justify-content: space-between;}}
    .row-container {{background: {THEME['card']}; border: 1px solid {THEME['border']}; border-radius: 10px; padding: 16px; margin-bottom: 12px; transition: border-color 0.2s;}}
    .row-container:hover {{border-color: rgba({THEME['accent_rgb']}, 0.4);}}
    .field-label {{font-size: 10px; font-weight: 700; color: {THEME['sub']}; text-transform: uppercase; letter-spacing: .06em; margin-bottom: 5px;}}
    .hint-tag {{font-size: 9px; color: {THEME['accent']}; background: rgba({THEME['accent_rgb']}, 0.1); padding: 1px 6px; border-radius: 4px; margin-left: 6px;}}

    /* Custom Input Control Component Overrides */
    div[data-testid="stTextInput"]>div>div>input, div[data-testid="stNumberInput"]>div>div>input {{
        background-color: {THEME['bg']}!important; border: 1px solid {THEME['border']}!important; color: {THEME['text']}!important; border-radius: 8px!important; padding: 0.4rem 0.75rem!important;}}
    div[data-testid="stTextInput"]>div>div>input:focus {{border-color: {THEME['accent']}!important; box-shadow: 0 0 0 2px rgba({THEME['accent_rgb']}, 0.2)!important;}}

    /* Standardized Buttons Architecture */
    div[data-testid="stButton"]>button[kind="primary"] {{
        background: linear-gradient(135deg, {THEME['accent']} 0%, #0051B3 100%)!important; color: #FFFFFF!important; border: none!important; border-radius: 10px!important;
        font-size: 14px!important; font-weight: 700!important; padding: 0.75rem 2.5rem!important; letter-spacing: .05em!important; text-transform: uppercase; box-shadow: 0 4px 20px rgba({THEME['accent_rgb']}, 0.25)!important; transition: all 0.2s!important; width: 100%;}}
    div[data-testid="stButton"]>button[kind="primary"]:hover {{transform: translateY(-1px)!important; box-shadow: 0 6px 24px rgba({THEME['accent_rgb']}, 0.4)!important; opacity: 0.95;}}
    div[data-testid="stButton"]>button:not([kind="primary"]) {{
        font-size: 12px!important; border-radius: 8px!important; border: 1px solid {THEME['border']}!important; background: {THEME['card2']}!important; color: {THEME['text']}!important; font-weight: 600!important; transition: all 0.2s!important;}}
    div[data-testid="stButton"]>button:not([kind="primary"]):hover {{border-color: {THEME['accent']}!important; background: rgba({THEME['accent_rgb']}, 0.05)!important;}}

    /* Splash Screen Engine Styling */
    #splash {{position:fixed; inset:0; z-index:99999; background:#07090E; display:flex; flex-direction:column; align-items:center; justify-content:center; animation:splashFade 0.4s ease 1.4s forwards;}}
    @keyframes splashFade {{ 0% {{opacity:1;}} 100% {{opacity:0; pointer-events:none;}} }}
    .splash-logo {{width:90px; height:90px; border-radius:22px; object-fit:cover; animation:splashPop 0.5s cubic-bezier(.34,1.56,.64,1) both; box-shadow: 0 0 40px rgba(79,195,247,0.4);}}
    @keyframes splashPop {{ 0% {{opacity:0; transform:scale(0.6);}} 100% {{opacity:1; transform:scale(1);}} }}
    .splash-name {{font-size:32px; font-weight:800; color:#FFFFFF; letter-spacing:-1px; font-family:'JetBrains Mono', monospace; margin-top:16px;}}
    .splash-bar {{width:40px; height:2px; border-radius:999px; background: {THEME['accent']}; margin-top:12px;}}
</style>
<div class="grid-bg"></div>
""", unsafe_allow_html=True)

# ── SPLASH SCREEN ROUTER ──────────────────────────────
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

# ── NAVIGATION TOPBAR SYSTEM ──────────────────────────
logo_html = f'<img class="logo-img" src="data:image/png;base64,{logo_b64}" alt="Slotra Enterprise"/>' if logo_b64 else f'<div style="font-size:24px; font-weight:900; color:{THEME["accent"]}; font-family:\'JetBrains Mono\'">S//</div>'

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
    <div class="feat-grid">
      <div class="fc"><div class="fi">⚡</div><div class="ft">Linear Processing</div><div class="fd">Compiles complete architectural data matrices under 1 second flat.</div></div>
      <div class="fc"><div class="fi">🛡️</div><div class="ft">Deterministic Logic</div><div class="fd">Zero chance of space overlapping or overlapping instructor hours.</div></div>
      <div class="fc"><div class="fi">📊</div><div class="ft">Telemetry Analytics</div><div class="fd">Live calculations tracking resource stress and period maps seamlessly.</div></div>
      <div class="fc"><div class="fi">🧬</div><div class="ft">Heuristic Solvers</div><div class="fd">Powered by multi-generational iterative constraint models.</div></div>
    </div>
    """, unsafe_allow_html=True)

    # ── TEACHERS PANEL WITH MATRIX ADVANCED CONSTRAINTS ──
    st.markdown(f"<div class='section-header-panel'><span style='font-size:14px; font-weight:700;'>Instructor Resource Matrix</span><span style='font-size:11px; color:{THEME['sub']}; font-family:monospace;'>st.session_state.teacher_rows</span></div>", unsafe_allow_html=True)
    
    @st.fragment
    def render_teachers():
        for i, row in enumerate(st.session_state.teacher_rows):
            st.markdown(f"<div class='row-container'><div class='field-label'>Resource #{i+1:02d}</div>", unsafe_allow_html=True)
            
            # Row Element 1: Identity & Subject Competence
            c1, c2 = st.columns([2, 3])
            with c1:
                st.markdown("<div class='field-label'>Full name</div>", unsafe_allow_html=True)
                st.session_state.teacher_rows[i]["name"] = st.text_input("Name", value=row.get("name", ""), key=f"tn_v3_{i}", label_visibility="collapsed", placeholder="Instructor Name")
            with c2:
                st.markdown("<div class='field-label'>Subjects <span class='hint-tag'>comma separated</span></div>", unsafe_allow_html=True)
                st.session_state.teacher_rows[i]["subjects"] = st.text_input("Subjects", value=row.get("subjects", ""), key=f"ts_v3_{i}", label_visibility="collapsed", placeholder="e.g. Math,Physics")
            
            # Row Element 2: Operational Bounds & Constraints Mapping
            st.markdown("<div style='margin-top: 8px;'></div>", unsafe_allow_html=True)
            c3, c4, c5, c6 = st.columns([1.2, 1.2, 2.2, 0.4])
            with c3:
                st.markdown("<div class='field-label'>Max Days / Wk</div>", unsafe_allow_html=True)
                st.session_state.teacher_rows[i]["max_days"] = st.number_input("Max Days", min_value=1, max_value=5, value=int(row.get("max_days", 5)), key=f"tmd_v3_{i}", label_visibility="collapsed")
            with c4:
                st.markdown("<div class='field-label'>Max Periods / Wk</div>", unsafe_allow_html=True)
                st.session_state.teacher_rows[i]["max_periods"] = st.number_input("Max Periods", min_value=1, max_value=40, value=int(row.get("max_periods", 20)), key=f"tmp_v3_{i}", label_visibility="collapsed")
            with c5:
                st.markdown("<div class='field-label'>Exclusion Flags <span class='hint-tag'>e.g., 0:1 (Day:Period)</span></div>", unsafe_allow_html=True)
                st.session_state.teacher_rows[i]["unavailable"] = st.text_input("Exclusions", value=row.get("unavailable", ""), key=f"tu_v3_{i}", label_visibility="collapsed", placeholder="Eg: 0:1, 2:4")
            with c6:
                st.markdown("<br>", unsafe_allow_html=True)
                if st.button("✕", key=f"td_v3_{i}"):
                    st.session_state.teacher_rows.pop(i)
                    st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)
    render_teachers()
    
    if st.button("＋ Append Instructor Entry", key="add_teacher_btn"):
        st.session_state.teacher_rows.append({"name": "", "subjects": "", "max_days": 5, "max_periods": 20, "unavailable": ""})
        st.rerun()

    # ── ROOMS PANEL ───────────────────────────────────
    st.markdown(f"<div class='section-header-panel'><span style='font-size:14px; font-weight:700;'>Spatial Infrastructure Allocations</span><span style='font-size:11px; color:{THEME['sub']}; font-family:monospace;'>st.session_state.room_rows</span></div>", unsafe_allow_html=True)
    
    @st.fragment
    def render_rooms():
        for i, row in enumerate(st.session_state.room_rows):
            st.markdown(f"<div class='row-container'><div class='field-label'>Location Unit #{i+1:02d}</div>", unsafe_allow_html=True)
            c1, c2, c3, c4 = st.columns([1.5, 2.5, 1.5, 0.4])
            with c1:
                st.session_state.room_rows[i]["id"] = st.text_input("ID", value=row["id"], key=f"ri_v2_{i}", label_visibility="collapsed", placeholder="Room ID")
            with c2:
                st.session_state.room_rows[i]["name"] = st.text_input("Name", value=row["name"], key=f"rn_v2_{i}", label_visibility="collapsed", placeholder="Display Identifier")
            with c3:
                st.session_state.room_rows[i]["capacity"] = st.number_input("Capacity", value=row["capacity"], min_value=1, key=f"rc_v2_{i}", label_visibility="collapsed")
            with c4:
                if st.button("✕", key=f"rd_v2_{i}"):
                    st.session_state.room_rows.pop(i)
                    st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)
    render_rooms()

    if st.button("＋ Append Location Unit", key="add_room_btn"):
        st.session_state.room_rows.append({"id": "", "name": "", "capacity": 30})
        st.rerun()

    # ── SECTIONS PANEL ─────────────────────────────────
    st.markdown(f"<div class='section-header-panel'><span style='font-size:14px; font-weight:700;'>Cohort Curriculum Structural Parameters</span><span style='font-size:11px; color:{THEME['sub']}; font-family:monospace;'>st.session_state.section_rows</span></div>", unsafe_allow_html=True)
    
    @st.fragment
    def render_sections():
        for i, row in enumerate(st.session_state.section_rows):
            st.markdown(f"<div class='row-container'><div class='field-label'>Cohort Section #{i+1:02d} <span class='hint-tag'>Syntax Guide Structure: Subject:Periods, Subject:Periods</span></div>", unsafe_allow_html=True)
            c1, c2, c3, c4, c5 = st.columns([1.2, 1.8, 1.2, 4, 0.4])
            with c1:
                st.session_state.section_rows[i]["id"] = st.text_input("ID", value=row["id"], key=f"si_v2_{i}", label_visibility="collapsed", placeholder="Section ID")
            with c2:
                st.session_state.section_rows[i]["name"] = st.text_input("Name", value=row["name"], key=f"sn_v2_{i}", label_visibility="collapsed", placeholder="Class Designation")
            with c3:
                st.session_state.section_rows[i]["strength"] = st.number_input("Strength", value=row["strength"], min_value=1, key=f"ss_v2_{i}", label_visibility="collapsed")
            with c4:
                st.session_state.section_rows[i]["subjects"] = st.text_input("Load Map", value=row["subjects"], key=f"sb_v2_{i}", label_visibility="collapsed", placeholder="e.g., Math:5,English:4")
            with c5:
                if st.button("✕", key=f"sd_v2_{i}"):
                    st.session_state.section_rows.pop(i)
                    st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)
    render_sections()

    if st.button("＋ Append Cohort Parameters", key="add_sec_btn"):
        st.session_state.section_rows.append({"id": "", "name": "", "strength": 30, "subjects": ""})
        st.rerun()

    # ── PROCESSING CALL EXECUTION ──────────────────────
    st.markdown("<br><br>", unsafe_allow_html=True)
    _, center_btn_col, _ = st.columns([1.5, 2, 1.5])
    with center_btn_col:
        execute_solver = st.button("Execute Hard-Constraint Optimization", type="primary")

    if execute_solver:
        teachers_list = []
        for i, r in enumerate(st.session_state.teacher_rows):
            if not r["name"].strip(): continue
            subjs = [s.strip() for s in r["subjects"].split(",") if s.strip()]
            
            # Complex Parsing: String blocks to structured exclusion mappings
            raw_unavail = r.get("unavailable", "")
            parsed_exclusions = []
            if raw_unavail.strip():
                for block in raw_unavail.split(","):
                    if ":" in block:
                        try:
                            d_idx, p_idx = block.strip().split(":")
                            parsed_exclusions.append((int(d_idx), int(p_idx)))
                        except ValueError:
                            pass
            
            # SAFE PATTERN: Initialize base model structure parameters cleanly first
            teacher_obj = Teacher(
                id=f"T{i+1:03d}", 
                name=r["name"].strip(), 
                subjects=subjs, 
                unavailable=parsed_exclusions
            )
            
            # Safely append metadata onto the object properties to avoid constructor signature collisions
            teacher_obj.max_days = int(r.get("max_days", 5))
            teacher_obj.max_periods = int(r.get("max_periods", 20))
            
            teachers_list.append(teacher_obj)

        rooms_list = [
            Room(id=r["id"].strip(), name=r["name"].strip(), capacity=int(r["capacity"]))
            for r in st.session_state.room_rows if r["id"].strip()
        ]
        
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
                except Exception as e:
                    st.error(f"Solver Engine Compilation Fault: {e}")

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
                    solver.create_variables()
                    solver.add_coverage_constraint()
                    solver.add_section_no_clash()
                    solver.add_teacher_no_clash()
                    solver.add_room_no_clash()
                    st.session_state.timetable = solver.solve()
                    st.session_state.violations = check_hard_constraints(st.session_state.timetable, teachers, rooms)
                    st.rerun()
                except Exception as e:
                    st.error(f"Fault: {e}")

    # Topline Dashboard Analytics Matrix Cards
    st.markdown("<br>", unsafe_allow_html=True)
    c1, c2, c3, c4 = st.columns(4)
    metrics_schema = [
        (len(timetable), "Total Load Placements"),
        (len(violations), "Conflict Anomaly Detections"),
        (len(sections), "Active Managed Cohorts"),
        (len(teachers), "Assigned Active Staff")
    ]
    for idx, (metric, label) in enumerate(metrics_schema):
        with [c1, c2, c3, c4][idx]:
            text_color_override = "color: #FF5252;" if idx == 1 and metric > 0 else f"color: {THEME['accent']};"
            st.markdown(f"<div class='mc' style='background:{THEME['card']}; border:1px solid {THEME['border']}; border-radius:12px; padding:1.2rem; text-align:center;'><div class='mv' style=\"font-size:36px; font-weight:800; font-family:'JetBrains Mono'; {text_color_override}\">{metric}</div><div class='ml' style='font-size:10px; color:{THEME['sub']}; text-transform:uppercase; font-weight:600; margin-top:4px;'>{label}</div></div>", unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)
    if not violations:
        st.success("Enterprise Status Validation Check: PASS (100% Conflict-Free Structural Integrity)")
    else:
        st.error(f"Anomaly Alert: {len(violations)} Hard-Overlap Violations active within constraints solver framework.")
        for v in violations: st.caption(f"⚠ {v}")
        
    st.markdown(f"<hr style='border-color: {THEME['border']}'>", unsafe_allow_html=True)

    # Data structuring definitions
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
    df = pd.DataFrame(processed_records).sort_values(["DayN", "PerN"])

    # High-Performance UI Tabs Interface System
    t1, t2, t3, t4, t5 = st.tabs([
        "📅 Cohort Schedules Matrix", "👨‍🏫 Instructor Load Profiles", 
        "🏠 Infrastructure Operations", "📊 Spatial Telemetry", "📥 Data Stream Export"
    ])

    with t1:
        chosen_section = st.selectbox("Filter Target Cohort Section Array", [s.id for s in sections], key="sec_select")
        filtered_df = df[df["Section"] == chosen_section].copy()
        
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
        
        # Legend Render
        legend_cols = st.columns(max(len(unique_subjects), 1))
        for i, subj in enumerate(unique_subjects):
            legend_cols[i].markdown(f"<div style='background:{color_map[subj]}25; border:1px solid {color_map[subj]}; padding:6px; border-radius:6px; font-size:11px; text-align:center; font-weight:600;'>{subj}</div>", unsafe_allow_html=True)

    with t2:
        chosen_teacher = st.selectbox("Select Target Instructor Interface", [t.name for t in teachers], key="tch_select")
        teacher_df = df[df["Teacher"] == chosen_teacher].copy()
        st.markdown(f"Allocation Diagnostic: **{len(teacher_df)} Core Operational Periods** mapped to schedule parameters.")
        
        workload_per_day = teacher_df.groupby("Day").size().reindex(days, fill_value=0).reset_index(name="Periods")
        fig_t = px.bar(workload_per_day, x="Day", y="Periods", color="Periods", color_continuous_scale="Sunset" if D else "Blues")
        fig_t.update_layout(plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)", font_color=THEME['text'], font_family="JetBrains Mono", margin=dict(t=10, b=10, l=10, r=10), height=240)
        st.plotly_chart(fig_t, use_container_width=True)
        st.dataframe(teacher_df[["Day", "Period", "Section", "Subject", "Room"]].reset_index(drop=True), use_container_width=True)

    with t3:
        max_slots = 40
        room_utilization = df.groupby("Room").size().reset_index(name="Used")
        room_utilization["Available Free"] = max_slots - room_utilization["Used"]
        room_utilization["Utilization Index %"] = (room_utilization["Used"] / max_slots * 100).round(1)
        
        fig_r = px.bar(room_utilization, x="Room", y=["Used", "Available Free"], barmode="stack", color_discrete_map={"Used": THEME['accent'], "Available Free": "#222C3A" if D else "#E5E7EB"})
        fig_r.update_layout(plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)", font_color=THEME['text'], font_family="JetBrains Mono", margin=dict(t=10, b=10, l=10, r=10), height=260)
        st.plotly_chart(fig_r, use_container_width=True)
        st.dataframe(room_utilization, use_container_width=True)

    with t4:
        layout_l, layout_r = st.columns(2)
        with layout_l:
            subject_dist = df.groupby("Subject").size().reset_index(name="Periods")
            fig_pie = px.pie(subject_dist, names="Subject", values="Periods", hole=0.4, color_discrete_sequence=px.colors.qualitative.Pastel)
            fig_pie.update_layout(paper_bgcolor="rgba(0,0,0,0)", font_color=THEME['text'], font_family="JetBrains Mono", margin=dict(t=20, b=10, l=10, r=10), height=260)
            st.plotly_chart(fig_pie, use_container_width=True)
        with layout_r:
            teacher_workload = df.groupby("Teacher").size().reset_index(name="Total Periods")
            fig_bar = px.bar(teacher_workload, x="Teacher", y="Total Periods", color="Total Periods", color_continuous_scale="Viridis")
            fig_bar.update_layout(plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)", font_color=THEME['text'], font_family="JetBrains Mono", margin=dict(t=20, b=10, l=10, r=10), height=260)
            st.plotly_chart(fig_bar, use_container_width=True)
            
        heat_map_data = df.groupby(["Section", "Subject"]).size().reset_index(name="Periods")
        fig_h = px.density_heatmap(heat_map_data, x="Subject", y="Section", z="Periods", color_continuous_scale="Magma" if D else "YlGnBu")
        fig_h.update_layout(plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)", font_color=THEME['text'], font_family="JetBrains Mono", height=280)
        st.plotly_chart(fig_h, use_container_width=True)

    with t5:
        st.markdown("### Production File Pipeline Generation Engine")
        for sc_obj in sections:
            section_export_df = df[df["Section"] == sc_obj.id][["Day", "Period", "Subject", "Teacher", "Room"]].reset_index(drop=True)
            st.download_button(
                label=f"📥 Bulk Transmit Schema Stream Data: Class {sc_obj.id} (CSV)",
                data=section_export_df.to_csv(index=False),
                file_name=f"enterprise_matrix_timetable_{sc_obj.id}.csv",
                mime="text/csv", key=f"dl_v2_{sc_obj.id}"
            )
        st.markdown("<div style='margin: 1.5rem 0;'></div>", unsafe_allow_html=True)
        st.download_button(
            label="📊 Transmit Enterprise Relational Database Array (All Channels)",
            data=df[["Section", "Day", "Period", "Subject", "Teacher", "Room"]].reset_index(drop=True).to_csv(index=False),
            file_name="complete_enterprise_master_timetable.csv",
            mime="text/csv", key="dl_v2_all_master", use_container_width=True
        )

# Footer Graphic Accents
st.markdown(f"""<br><p align="center"><img src="https://capsule-render.vercel.app/api?type=rect&color={THEME['accent'].replace('#', '')}&height=6&section=footer&radius=2" width="100%" /></p>""", unsafe_allow_html=True)