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

# Clean, unpopulated system memory structures (No dummy data rows)
INITIAL_STATES = {
    "timetable": None, 
    "violations": [], 
    "dark_mode": True, 
    "page": "home",
    "teachers": [], 
    "rooms": [], 
    "sections": [],
    "simulation_headroom": 3
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
    div[data-testid="stFileUploader"] {{background-color: {THEME['card']}; border: 2px dashed {THEME['accent']}50!important; border-radius: 14px; padding: 20px; text-align: center;}}
    div[data-testid="stButton"]>button[kind="primary"] {{ background: linear-gradient(135deg, {THEME['accent']} 0%, #0051B3 100%)!important; color: #FFFFFF!important; border: none!important; border-radius: 10px!important; font-size: 15px!important; font-weight: 700!important; padding: 0.9rem 2.5rem!important; letter-spacing: .05em!important; text-transform: uppercase; box-shadow: 0 4px 20px rgba({THEME['accent_rgb']}, 0.25)!important; transition: all 0.2s!important; width: 100%;}}
    div[data-testid="stButton"]>button:not([kind="primary"]) {{ font-size: 12px!important; border-radius: 8px!important; border: 1px solid {THEME['border']}!important; background: {THEME['card2']}!important; color: {THEME['text']}!important; font-weight: 600!important; transition: all 0.2s!important;}}
</style>
<div class="grid-bg"></div>
""", unsafe_allow_html=True)

# ── HEADER ENGINE NAVIGATION LINKS ──────────────────────
col_tl, col_tr = st.columns([4, 2])
with col_tl:
    if logo_b64:
        st.markdown(f'<div class="topbar"><div><img class="logo-img" src="data:image/png;base64,{logo_b64}" alt="Slotra"/></div></div>', unsafe_allow_html=True)
    else:
        st.markdown(f'<div class="topbar"><div style="font-size:24px; font-weight:900; color:{THEME["accent"]}; font-family:\'JetBrains Mono\'">Slotra</div></div>', unsafe_allow_html=True)
        
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

# ────────────────────────────────────────────────────────
#  HOME PROFILE SECTION (AUTOMATED SPREADSHEET INGESTION)
# ────────────────────────────────────────────────────────
if st.session_state.page == "home":
    st.markdown(f"""
    <div class="hero-section">
      <div class="hero-title">SLOTRA</div>
      <div class="hero-sub">Automated Combinatorial Timetable Engine</div>
    </div>
    """, unsafe_allow_html=True)

    _, center_panel, _ = st.columns([1, 2, 1])
    
    with center_panel:
        st.markdown(f"<div style='background:{THEME['card']}; border:1px solid {THEME['border']}; border-radius:16px; padding:2rem; box-shadow:0 12px 40px rgba(0,0,0,0.15);'>", unsafe_allow_html=True)
        st.markdown("<h3 style='margin-top:0; font-size:18px; text-align:center;'>Upload Resource Matrix</h3>", unsafe_allow_html=True)
        st.markdown("<p style='font-size:12px; color:#9CA3AF; text-align:center; margin-bottom:1.5rem;'>Your spreadsheet should contain columns for <b>Name</b> and <b>Subjects</b>.</p>", unsafe_allow_html=True)
        
        uploaded_file = st.file_uploader("Select spreadsheet file", type=["xlsx", "xls", "csv"], label_visibility="collapsed")
        st.markdown("<br>", unsafe_allow_html=True)
        
        # Trigger Execution Matrix Button
        generate_matrix = st.button("Generate Optimized Timetable", type="primary", use_container_width=True)
        st.markdown("</div>", unsafe_allow_html=True)

    if generate_matrix:
        if uploaded_file is None:
            st.error("Engine Blocked: Please drop an Excel or CSV file first to seed the optimization bounds.")
        else:
            with st.spinner("Parsing Spreadsheet Vectors & Triggering Constraint Solver..."):
                try:
                    # 1. Parse Excel / CSV dataset records
                    if uploaded_file.name.endswith('.csv'):
                        df_input = pd.read_csv(uploaded_file)
                    else:
                        df_input = pd.read_excel(uploaded_file)
                    
                    # Standardize structural column targets
                    df_input.columns = [str(c).strip().lower() for c in df_input.columns]
                    
                    if 'name' not in df_input.columns or 'subjects' not in df_input.columns:
                        st.error("Matrix Structure Error: File needs 'Name' and 'Subjects' column configurations.")
                    else:
                        teachers_list = []
                        all_discovered_subjects = set()
                        
                        # Loop data into backend models directly
                        for idx, row in df_input.iterrows():
                            if pd.isna(row['name']) or str(row['name']).strip() == "":
                                continue
                            
                            teacher_name = str(row['name']).strip()
                            subjects_raw = str(row['subjects']).strip()
                            subjs = [s.strip() for s in subjects_raw.split(",") if s.strip()]
                            
                            for s in subjs: 
                                all_discovered_subjects.add(s)
                            
                            # Auto-extract custom matrix constraints if present, fallback to uniform standards
                            max_days = int(row['max days']) if 'max days' in df_input.columns and not pd.isna(row['max days']) else 5
                            max_periods = int(row['max periods']) if 'max periods' in df_input.columns and not pd.isna(row['max periods']) else 20
                            raw_unavail = str(row['exclusions']).strip() if 'exclusions' in df_input.columns and not pd.isna(row['exclusions']) else ""
                            
                            parsed_exclusions = []
                            if raw_unavail:
                                for block in raw_unavail.split(","):
                                    if ":" in block:
                                        try:
                                            d_idx, p_idx = block.strip().split(":")
                                            parsed_exclusions.append((int(d_idx), int(p_idx)))
                                        except ValueError: pass
                                        
                            t_obj = Teacher(id=f"T{idx+1:03d}", name=teacher_name, subjects=subjs, unavailable=parsed_exclusions)
                            t_obj.max_days = max_days
                            t_obj.max_periods = max_periods
                            teachers_list.append(t_obj)

                        # 2. Dynamic Structural Footprint Synthesizer (Auto-generate Rooms/Sections based on input payload)
                        rooms_list = [
                            Room(id="R101", name="Main Auditorium", capacity=60),
                            Room(id="R102", name="Lab Facility Alpha", capacity=40),
                            Room(id="R103", name="Standard Suite 103", capacity=45)
                        ]
                        
                        # Distribute unique discovered file parameters into curriculum maps
                        curriculum_load_map = {subj: 4 for subj in list(all_discovered_subjects)[:5]}
                        sections_list = [
                            Section(id="SEC_A", name="Cohort Cluster Alpha", strength=35, subject_periods=curriculum_load_map),
                            Section(id="SEC_B", name="Cohort Cluster Beta", strength=32, subject_periods=curriculum_load_map)
                        ]

                        if not teachers_list:
                            st.error("Compilation Fault: Active records count evaluates to zero inside the uploaded scope.")
                        else:
                            # 3. Compile backend linear solver arrays
                            solver = TimetableSolver(teachers_list, rooms_list, sections_list)
                            solver.create_variables()
                            solver.add_coverage_constraint()
                            solver.add_section_no_clash()
                            solver.add_teacher_no_clash()
                            solver.add_room_no_clash()
                            
                            generated_tt = solver.solve()
                            calculated_violations = check_hard_constraints(generated_tt, teachers_list, rooms_list)
                            
                            # Pipeline states onto Dashboard panel layout
                            st.session_state.update({
                                "timetable": generated_tt, "violations": calculated_violations,
                                "teachers": teachers_list, "rooms": rooms_list, "sections": sections_list,
                                "page": "dashboard"
                            })
                            st.rerun()
                except Exception as e:
                    st.error(f"Backend Compilation Engine Exception: {e}")

# ────────────────────────────────────────────────────────
#  EXECUTIVE MANAGEMENT DASHBOARD PANELS
# ────────────────────────────────────────────────────────
else:
    teachers, rooms = st.session_state.teachers, st.session_state.rooms
    sections, timetable = st.session_state.sections, st.session_state.timetable
    violations = st.session_state.violations

    if st.button("← Upload Another Spreadsheet Matrix"):
        st.session_state.page = "home"
        st.rerun()

    st.markdown("<br>", unsafe_allow_html=True)
    
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

    stress_df = calculate_system_stress_matrix(timetable, len(rooms), len(teachers))
    fatigue_df = analyze_subject_fatigue_index(df)
    gini_val = calculate_workload_inequality_gini(df, teachers)

    # Performance Monitoring KPIs
    c1, c2, c3, c4 = st.columns(4)
    metrics_schema = [
        (len(timetable), "Total Load Placements"),
        (len(violations), "Conflict Anomalies"),
        (f"{gini_val:.3f}", "Workload Gini Coefficient"),
        (f"{stress_df['Composite Stress Index'].mean():.1f}%" if not stress_df.empty else "0.0%", "Mean System Stress Index")
    ]
    for idx, (metric, label) in enumerate(metrics_schema):
        with [c1, c2, c3, c4][idx]:
            color = "color: #FF5252;" if (idx == 1 and len(violations) > 0) or (idx == 2 and gini_val > 0.4) else f"color: {THEME['accent']};"
            st.markdown(f"<div style='background:{THEME['card']}; border:1px solid {THEME['border']}; border-radius:12px; padding:1.2rem; text-align:center;'><div style=\"font-size:32px; font-weight:800; font-family:'JetBrains Mono'; {color}\">{metric}</div><div style='font-size:10px; color:{THEME['sub']}; text-transform:uppercase; font-weight:600; margin-top:4px;'>{label}</div></div>", unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)
    if not violations: st.success("Enterprise Status Validation Check: PASS (100% Conflict-Free Structural Integrity)")
    else:
        st.error(f"Anomaly Alert: {len(violations)} Hard-Overlap Violations found inside solver bounds.")
        for v in violations: st.caption(f"⚠ {v}")

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
        st.dataframe(fatigue_df, use_container_width=True)

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
                "Status Flag": "✓ OPTIMAL" if sim_headroom >= 0 else "🚨 OVERLOAD RISK"
            })
        st.dataframe(pd.DataFrame(sim_records), use_container_width=True)

    with t6:
        st.markdown("### Export Hub")
        if not df.empty:
            csv_data = df.to_csv(index=False).encode('utf-8')
            st.download_button(label="📥 Download Master Timetable CSV Array", data=csv_data, file_name="slotra_master_schedule.csv", mime="text/csv")
