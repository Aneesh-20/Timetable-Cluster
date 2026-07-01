import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))) if '__file__' in locals() else os.getcwd())
import streamlit as st
import pandas as pd
import plotly.express as px
import base64
import numpy as np
import time
from datetime import datetime
from src.models import Teacher, Room, Section, Constraint
from src.solver import TimetableSolver
from src.constraints import check_hard_constraints

# ── DATA ANALYTICS BACKEND LOGIC ENGINES ────────────────
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

# ── APP INITIALIZATION & THEME ──────────────────────────
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
    "border": "rgba(20,168,183,0.18)",
    "grid": "rgba(255,255,255,0.02)"
}

# ── LOGO ENGINE & CINEMATIC SPLASH ──────────────────────
logo_filename = "slotra_logo.png"
logo_src = f"data:image/png;base64,{base64.b64encode(open(logo_filename, 'rb').read()).decode()}" if os.path.exists(logo_filename) else ""

if not st.session_state.splash_done:
    st.markdown(f"<div class='netflix-preloader' style='position:fixed; inset:0; background:#0B0E14; display:flex; justify-content:center; align-items:center; z-index:999;'><img src='{logo_src}' style='width:200px; border-radius:20px; border:2px solid {THEME['accent']}; animation: pulse 1.8s infinite;'></div>", unsafe_allow_html=True)
    time.sleep(2.0)
    st.session_state.splash_done = True
    st.rerun()

# ── GLOBAL CSS STYLES ──────────────────────────────────
st.markdown(f"""<style>
    .stApp {{background-color: {THEME['bg']}!important; color: {THEME['text']}!important;}}
    .brand-header-center-layer {{display: flex; align-items: center; justify-content: center; gap: 18px; margin: 0 auto 2.5rem auto; padding: 14px 28px; background: #0E131F; border: 2px solid {THEME['accent']}; border-radius: 16px; max-width: fit-content;}}
    .instructor-card {{background: {THEME['card']}; border: 1px solid {THEME['border']}; border-radius: 12px; padding: 1.2rem; margin-bottom: 1rem;}}
</style>""", unsafe_allow_html=True)

# ── SIDEBAR & MAIN FLOW ────────────────────────────────
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
    # ── EXECUTIVE ANALYTICS RENDERING ──
    st.header("📊 Executive Analytics Suite")
    df = pd.DataFrame(...) # (Your processed timetable data)
    
    # 1. METRICS
    c1, c2, c3, c4 = st.columns(4)
    # ... (Your metric cards here)
    
    # 2. NEW VISUALIZATIONS (PREMIUM ANALYTICS)
    st.markdown("### 📈 Performance & Load Analytics")
    col_a, col_b, col_c = st.columns(3)
    template = "plotly_dark" if D else "plotly"
    
    with col_a: st.plotly_chart(px.pie(df.groupby("Teacher").size().reset_index(name="Classes"), values='Classes', names='Teacher', title='Workload Distribution', template=template), use_container_width=True)
    with col_b: st.plotly_chart(px.bar(df.groupby("Teacher").size().reset_index(name="Classes"), x='Teacher', y='Classes', title='Class Count per Instructor', template=template), use_container_width=True)
    with col_c: st.plotly_chart(px.box(pd.DataFrame([{"Period": s.timeslot.period + 1} for s in st.session_state.timetable]), y="Period", title="Period Density Analysis", template=template), use_container_width=True)
    
    if st.button("← Modify Constraints / Inputs"):
        st.session_state.page = "home"
        st.rerun()
