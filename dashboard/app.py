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
    if df_records.empty: return 0.0
    counts_map = df_records.groupby("Teacher").size().to_dict()
    all_workloads = [counts_map.get(t.name, 0) for t in total_teachers_list]
    array = np.array(all_workloads, dtype=float)
    if len(array) == 0 or array.sum() == 0: return 0.0
    array = np.sort(array)
    index = np.arange(1, array.shape[0] + 1)
    n = array.shape[0]
    return round(((np.sum((2 * index - n - 1) * array)) / (n * np.sum(array))), 3)

# ── APP INITIALIZATION ─────────────────────────────────
st.set_page_config(page_title="Slotra", layout="wide", initial_sidebar_state="expanded")

INITIAL_STATES = {
    "timetable": None, "violations": [], "dark_mode": True, "page": "home",
    "teachers": [], "simulation_headroom": 3
}
for key, val in INITIAL_STATES.items():
    if key not in st.session_state: st.session_state[key] = val

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
    .stApp {{background-color: {THEME['bg']}!important; color: {THEME['text']}!important; font-family: 'Inter', sans-serif;}}
    .block-container {{padding: 1rem 3rem 3rem !important; max-width: 1400px;}}
    .grid-bg {{position:fixed; inset:0; pointer-events:none; z-index:0; background-image: linear-gradient({THEME['grid']} 1px, transparent 1px), linear-gradient(90deg, {THEME['grid']} 1px, transparent 1px); background-size: 32px 32px;}}
    div[data-testid="stFileUploader"] {{background-color: {THEME['card']}; border: 2px dashed {THEME['accent']}50!important; border-radius: 14px;}}
    div[data-testid="stButton"]>button[kind="primary"] {{ background: linear-gradient(135deg, {THEME['accent']} 0%, #0051B3 100%)!important; color: #FFFFFF!important; border: none!important; font-weight: 700!important; border-radius: 10px!important; width: 100%;}}
</style>
<div class="grid-bg"></div>
""", unsafe_allow_html=True)

# ── SIDEBAR SPATIAL INFRASTRUCTURE CONFIGURATOR ──────────
with st.sidebar:
    st.markdown("### 🎛️ Spatial & Cohort Setup")
    
    # 1. Dynamic Rooms / Classrooms Configurator
    st.markdown("#### 🏫 Rooms / Classrooms")
    num_rooms = st.number_input("Number of Rooms Available", min_value=1, max_value=10, value=3)
    rooms_list = []
    for i in range(num_rooms):
        col_r1, col_r2 = st.columns([2, 1])
        with col_r1:
            r_name = st.text_input(f"Room {i+1} Name", value=f"Room {101+i}", key=f"rname_{i}")
        with col_r2:
            r_cap = st.number_input(f"Cap", min_value=10, max_value=200, value=40, key=f"rcap_{i}")
        rooms_list.append(Room(id=f"R{i+1}", name=r_name, capacity=r_cap))
        
    st.markdown("---")
    
    # 2. Dynamic Sections & Weekly Curricular Load Requirements
    st.markdown("#### 👥 Student Cohort Sections")
    num_sections = st.number_input("Number of Sections", min_value=1, max_value=5, value=2)
    
    st.markdown("##### 📚 Weekly Load Allocation Per Section")
    weekly_math = st.slider("Math Periods", 1, 8, 4)
    weekly_physics = st.slider("Physics Periods", 1, 8, 4)
    weekly_chem = st.slider("Chemistry Periods", 1, 8, 3)
    weekly_english = st.slider("English Periods", 1, 8, 3)
    
    curriculum_load_map = {
        "Math": weekly_math,
        "Physics": weekly_physics,
        "Chemistry": weekly_chem,
        "English": weekly_english
    }
    
    sections_list = []
    for j in range(num_sections):
        sec_char = chr(65 + j) # Generates A, B, C, etc.
        s_name = st.text_input(f"Section {sec_char} Name", value=f"Grade 10-{sec_char}", key=f"sname_{j}")
        sections_list.append(Section(id=f"SEC_{sec_char}", name=s_name, strength=35, subject_periods=curriculum_load_map))

# ── MAIN PANEL INTERFACE ─────────────────────────────────
if st.session_state.page == "home":
    st.markdown("<div style='text-align:center; padding: 2rem 0;'><h1 style='font-size: 50px; font-weight: 800; font-family:\"JetBrains Mono\";'>SLOTRA</h1><p style='color:#4FC3F7; text-transform:uppercase; letter-spacing:0.1em;'>Automated Infrastructure Scheduler</p></div>", unsafe_allow_html=True)

    _, center_panel, _ = st.columns([1, 2, 1])
    with center_panel:
        st.markdown(f"<div style='background:{THEME['card']}; border:1px solid {THEME['border']}; border-radius:16px; padding:2rem;'>", unsafe_allow_html=True)
        st.markdown("<h3 style='margin-top:0; text-align:center;'>1. Upload Roster Spreadsheet</h3>", unsafe_allow_html=True)
        
        uploaded_file = st.file_uploader("Upload matrix details", type=["xlsx", "xls", "csv"], label_visibility="collapsed")
        
        st.markdown("<h3 style='margin-top:1.5rem; text-align:center;'>2. Execute Constraint Solver</h3>", unsafe_allow_html=True)
        generate_matrix = st.button("Generate Optimized Timetable", type="primary")
        st.markdown("</div>", unsafe_allow_html=True)

    if generate_matrix:
        if uploaded_file is None:
            st.error("Engine Fault: Please drag and drop your instructor roster sheet before executing the solver.")
        else:
            with st.spinner("Compiling Spatial Infrastructure Arrays & Resolving Constraints..."):
                try:
                    if uploaded_file.name.endswith('.csv'): df_input = pd.read_csv(uploaded_file)
                    else: df_input = pd.read_excel(uploaded_file)
                    
                    df_input.columns = [str(c).strip().lower() for c in df_input.columns]
                    
                    if 'name' not in df_input.columns or 'subjects' not in df_input.columns:
                        st.error("Matrix Template Mismatch: File must contain 'Name' and 'Subjects' columns.")
                    else:
                        teachers_list = []
                        for idx, row in df_input.iterrows():
                            if pd.isna(row['name']) or str(row['name']).strip() == "": continue
                            t_name = str(row['name']).strip()
                            subjs = [s.strip() for s in str(row['subjects']).split(",") if s.strip()]
                            
                            max_days = int(row['max days']) if 'max days' in df_input.columns and not pd.isna(row['max days']) else 5
                            max_periods = int(row['max periods']) if 'max periods' in df_input.columns and not pd.isna(row['max periods']) else 20
                            
                            t_obj = Teacher(id=f"T{idx+1:03d}", name=t_name, subjects=subjs, unavailable=[])
                            t_obj.max_days = max_days
                            t_obj.max_periods = max_periods
                            teachers_list.append(t_obj)

                        # Pipeline components into our core scheduling solver engine
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
                    st.error(f"Solver Engine Crash Vector: {e}")

# ── EXECUTIVE ANALYTICS RENDERING GRID ──────────────────
else:
    teachers, rooms = st.session_state.teachers, st.session_state.rooms
    sections, timetable = st.session_state.sections, st.session_state.timetable
    violations = st.session_state.violations

    if st.button("← Upload Another Dataset Matrix"):
        st.session_state.page = "home"
        st.rerun()

    days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
    processed_records = []
    for allocation in timetable:
        matched_t = next((t for t in teachers if t.id == allocation.teacher_id), None)
        matched_r = next((r for r in rooms if r.id == allocation.room_id), None)
        processed_records.append({
            "Section": allocation.section_id, "Subject": allocation.subject,
            "Teacher": matched_t.name if matched_t else allocation.teacher_id,
            "Room": matched_r.name if matched_r else allocation.room_id, 
            "Day": days[allocation.timeslot.day], "DayN": allocation.timeslot.day, 
            "PerN": allocation.timeslot.period + 1, "Period": f"Period {allocation.timeslot.period + 1}"
        })
    df = pd.DataFrame(processed_records)
    if not df.empty: df = df.sort_values(["DayN", "PerN"])

    stress_df = calculate_system_stress_matrix(timetable, len(rooms), len(teachers))
    fatigue_df = analyze_subject_fatigue_index(df)
    gini_val = calculate_workload_inequality_gini(df, teachers)

    # Rendering Metrics Display Cards
    c1, c2, c3, c4 = st.columns(4)
    metrics_schema = [
        (len(timetable), "Total Placed Classes"),
        (len(violations), "Conflict Violations"),
        (f"{gini_val:.3f}", "Staff Workload Gini"),
        (f"{stress_df['Composite Stress Index'].mean():.1f}%" if not stress_df.empty else "0%", "Mean System Stress")
    ]
    for idx, (m, lbl) in enumerate(metrics_schema):
        with [c1, c2, c3, c4][idx]:
            st.markdown(f"<div style='background:{THEME['card']}; border:1px solid {THEME['border']}; border-radius:12px; padding:1.2rem; text-align:center;'><div style=\"font-size:32px; font-weight:800; color:{THEME['accent']};\">{m}</div><div style='font-size:10px; color:{THEME['sub']};'>{lbl}</div></div>", unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)
    t1, t2, t3 = st.tabs(["📅 Master Schedule Matrix Grid", "📊 Infrastructure Stress", "🧠 Curricular Distribution Health"])
    
    with t1:
        chosen_section = st.selectbox("Select Target Cohort View", [s.id for s in sections])
        f_df = df[df["Section"] == chosen_section] if not df.empty else pd.DataFrame()
        if not f_df.empty:
            grid = {d: {f"P{p}": "" for p in range(1, 9)} for d in days}
            for _, row in f_df.iterrows():
                grid[row["Day"]][f"P{row['PerN']}"] = f"{row['Subject']} \n ({row['Teacher']} // {row['Room']})"
            st.dataframe(pd.DataFrame(grid, index=[f"P{p}" for p in range(1, 9)]), use_container_width=True)
            
    with t2:
        st.dataframe(stress_df, use_container_width=True)
    with t3:
        st.dataframe(fatigue_df, use_container_width=True)
