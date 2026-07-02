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

def build_teacher_safe(idx, name, subjects, max_days, max_periods, exclusions):
    """
    Constructs a Teacher object without assuming an exact constructor signature
    (src/models.py wasn't available at edit time). Tries the most common field
    names first; falls back to a plain dict + on-screen warning so the app
    never crashes on a mismatched Teacher(...) signature. Adjust the kwargs
    below to match your real Teacher class if the warning appears.
    """
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
    st.warning(f"Couldn't match Teacher(...) constructor for '{name}' — using a plain record instead. Update build_teacher_safe to match your Teacher model's real fields.")
    return {"id": f"T{idx+1}", "name": name, "subjects": subj_list, "max_days": max_days, "max_periods": max_periods, "exclusions": excl_list}

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

# ══════════════════════════════════════════════════════════
# PREMIUM DESIGN TOKEN SYSTEM
# Palette: instrument-panel obsidian + brass, not generic SaaS teal.
# Display face: Fraunces (serif, plaque-like gravitas)
# UI face: Inter (dense-data legibility)
# Numeric face: JetBrains Mono (precision-instrument readouts)
# ══════════════════════════════════════════════════════════
THEME = {
    "bg": "#07090D" if D else "#F6F4EF",
    "bg_grad_a": "#0A0D14" if D else "#FBFAF7",
    "bg_grad_b": "#07090D" if D else "#F1EEE6",
    "panel": "rgba(16, 20, 31, 0.72)" if D else "rgba(255, 255, 255, 0.86)",
    "panel_solid": "#10141F" if D else "#FFFFFF",
    "accent": "#C9A15A" if D else "#A7793B",
    "accent_bright": "#E4C077" if D else "#C9A15A",
    "accent_dim": "rgba(201,161,90,0.14)" if D else "rgba(167,121,59,0.10)",
    "text": "#ECE9E2" if D else "#1A1712",
    "text_dim": "#8B8D97" if D else "#6B6558",
    "sub": "#63656F" if D else "#948C7C",
    "border": "rgba(201,161,90,0.22)" if D else "rgba(167,121,59,0.24)",
    "border_soft": "rgba(255,255,255,0.06)" if D else "rgba(26,23,18,0.08)",
    "grid": "rgba(255,255,255,0.03)" if D else "rgba(0,0,0,0.04)",
    "danger": "#E5675F",
    "success": "#5FBF8A",
    "warning": "#D9A84E",
}

PLOTLY_FONT = "Inter, -apple-system, sans-serif"
PLOTLY_MONO = "JetBrains Mono, monospace"

# ── LOGO ENGINE & CINEMATIC SPLASH ──────────────────────
logo_filename = "slotra_logo.png"
logo_src = f"data:image/png;base64,{base64.b64encode(open(logo_filename, 'rb').read()).decode()}" if os.path.exists(logo_filename) else ""

if not st.session_state.splash_done:
    st.markdown(f"""
    <div class='slotra-preloader'>
        <div class='slotra-preloader-inner'>
            <div class='slotra-preloader-ring'></div>
            <img src='{logo_src}' class='slotra-preloader-logo'>
            <div class='slotra-preloader-word'>SLOTRA</div>
            <div class='slotra-preloader-tag'>CALIBRATING INSTRUMENT</div>
        </div>
    </div>
    <style>
        .slotra-preloader {{
            position:fixed; inset:0; z-index:999;
            background: radial-gradient(ellipse at 50% 40%, #12161F 0%, #07090D 70%);
            display:flex; justify-content:center; align-items:center;
        }}
        .slotra-preloader-inner {{ position:relative; display:flex; flex-direction:column; align-items:center; gap:14px; }}
        .slotra-preloader-ring {{
            position:absolute; width:132px; height:132px; border-radius:50%;
            border: 1px solid rgba(201,161,90,0.35);
            border-top-color: #C9A15A;
            animation: slotra-spin 1.4s linear infinite;
        }}
        .slotra-preloader-logo {{ width:96px; border-radius:14px; box-shadow: 0 0 40px rgba(201,161,90,0.25); }}
        .slotra-preloader-word {{
            font-family:'Fraunces', Georgia, serif; font-size:22px; font-weight:600;
            letter-spacing:0.28em; color:#ECE9E2; margin-top:4px;
        }}
        .slotra-preloader-tag {{
            font-family:'Inter', sans-serif; font-size:9.5px; letter-spacing:0.32em;
            color:#8B8D97; text-transform:uppercase;
        }}
        @keyframes slotra-spin {{ 100% {{ transform: rotate(360deg); }} }}
    </style>
    """, unsafe_allow_html=True)
    time.sleep(2.0)
    st.session_state.splash_done = True
    st.rerun()

# ══════════════════════════════════════════════════════════
# GLOBAL CSS STYLES — premium instrument-panel design system
# ══════════════════════════════════════════════════════════
st.markdown(f"""
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,400;9..144,500;9..144,600;9..144,700&family=Inter:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>
    html, body, [class*="css"] {{ font-family: 'Inter', -apple-system, sans-serif; }}

    .stApp {{
        background: radial-gradient(ellipse 1200px 700px at 15% -10%, {THEME['bg_grad_a']} 0%, transparent 60%),
                    radial-gradient(ellipse 1000px 800px at 100% 110%, {THEME['bg_grad_a']} 0%, transparent 55%),
                    {THEME['bg_grad_b']} !important;
        color: {THEME['text']} !important;
    }}

    /* Subtle film-grain texture overlay for material depth */
    .stApp::before {{
        content: ""; position: fixed; inset: 0; pointer-events: none; z-index: 0; opacity: {"0.035" if D else "0.02"};
        background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='140' height='140'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='2' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)'/%3E%3C/svg%3E");
    }}

    h1, h2, h3 {{ font-family: 'Fraunces', Georgia, serif !important; color: {THEME['text']} !important; letter-spacing: -0.01em; }}
    p, span, div, label {{ letter-spacing: 0.003em; }}

    ::selection {{ background: {THEME['accent_dim']}; color: {THEME['accent_bright']}; }}

    /* ── Brand header ── */
    .brand-header-center-layer {{
        display: flex; align-items: center; justify-content: center; gap: 20px;
        margin: 0 auto 2.6rem auto; padding: 18px 36px;
        background: linear-gradient(180deg, {THEME['panel']} 0%, rgba(16,20,31,0.4) 100%);
        border: 1px solid {THEME['border']}; border-radius: 18px; max-width: fit-content;
        backdrop-filter: blur(18px); -webkit-backdrop-filter: blur(18px);
        box-shadow: 0 12px 40px rgba(0,0,0,0.35), inset 0 1px 0 rgba(255,255,255,0.04);
        position: relative;
    }}
    .brand-header-center-layer::before, .brand-header-center-layer::after {{
        content: ""; position: absolute; width: 10px; height: 10px;
        border-top: 1.5px solid {THEME['accent']}; border-left: 1.5px solid {THEME['accent']};
        top: 8px; left: 8px; opacity: 0.7;
    }}
    .brand-header-center-layer::after {{
        left: auto; right: 8px; top: auto; bottom: 8px;
        border-left: none; border-right: 1.5px solid {THEME['accent']};
        border-top: none; border-bottom: 1.5px solid {THEME['accent']};
    }}
    .brand-word {{
        font-family: 'Fraunces', Georgia, serif; font-size: 30px; font-weight: 700;
        letter-spacing: 0.09em; background: linear-gradient(135deg, {THEME['accent_bright']} 0%, {THEME['accent']} 60%, #B8935A 100%);
        -webkit-background-clip: text; -webkit-text-fill-color: transparent; background-clip: text;
    }}
    .brand-tag {{
        color: {THEME['sub']}; font-size: 9.5px; letter-spacing: 0.32em; font-weight: 600;
        text-transform: uppercase; margin-top: 3px; font-family: 'Inter', sans-serif;
    }}

    /* ── Instructor / content cards ── */
    .instructor-card {{
        background: linear-gradient(160deg, {THEME['panel']} 0%, rgba(16,20,31,0.35) 100%);
        border: 1px solid {THEME['border_soft']}; border-left: 2px solid {THEME['accent']};
        border-radius: 14px; padding: 1.3rem 1.4rem; margin-bottom: 1rem;
        backdrop-filter: blur(14px); -webkit-backdrop-filter: blur(14px);
        box-shadow: 0 6px 24px rgba(0,0,0,0.22);
        transition: border-color 0.25s ease, box-shadow 0.25s ease;
    }}
    .instructor-card:hover {{ border-color: {THEME['border']}; box-shadow: 0 8px 32px rgba(0,0,0,0.3); }}

    /* ── Top corner bar ── */
    .topbar-row {{ display:flex; align-items:center; justify-content:space-between; margin-bottom: 0.9rem; }}
    .date-badge {{
        display:flex; align-items:center; gap:11px;
        background: {THEME['panel']}; border: 1px solid {THEME['border_soft']};
        border-radius: 999px; padding: 9px 20px; width: fit-content;
        font-family: 'JetBrains Mono', monospace; color: {THEME['text']}; font-size: 12.5px;
        backdrop-filter: blur(14px); -webkit-backdrop-filter: blur(14px);
        box-shadow: 0 4px 18px rgba(0,0,0,0.22);
    }}
    .date-badge .dot {{ width:7px; height:7px; border-radius:50%; background:{THEME['success']}; box-shadow: 0 0 10px {THEME['success']}; animation: pulse-dot 1.8s infinite; }}
    @keyframes pulse-dot {{ 0%{{opacity:1}} 50%{{opacity:0.3}} 100%{{opacity:1}} }}

    /* ── Buttons: mechanical, pressed, brass-accented ── */
    .stButton>button {{
        border-radius: 10px !important;
        border: 1px solid {THEME['border']} !important;
        background: linear-gradient(180deg, rgba(201,161,90,0.08) 0%, rgba(201,161,90,0.02) 100%) !important;
        color: {THEME['text']} !important;
        font-weight: 600 !important; font-family: 'Inter', sans-serif !important;
        letter-spacing: 0.02em !important;
        padding: 0.55rem 1.3rem !important;
        transition: all 0.18s cubic-bezier(0.4, 0, 0.2, 1) !important;
        box-shadow: 0 2px 8px rgba(0,0,0,0.18), inset 0 1px 0 rgba(255,255,255,0.03) !important;
    }}
    .stButton>button:hover {{
        border-color: {THEME['accent']} !important; color: {THEME['accent_bright']} !important;
        background: linear-gradient(180deg, rgba(201,161,90,0.16) 0%, rgba(201,161,90,0.05) 100%) !important;
        transform: translateY(-1px) !important;
        box-shadow: 0 6px 18px rgba(201,161,90,0.15), inset 0 1px 0 rgba(255,255,255,0.05) !important;
    }}
    .stButton>button:active {{ transform: translateY(0px) !important; box-shadow: 0 1px 4px rgba(0,0,0,0.2) !important; }}
    .stButton>button[kind="primary"] {{
        background: linear-gradient(180deg, {THEME['accent_bright']} 0%, {THEME['accent']} 100%) !important;
        color: #14100A !important; border: 1px solid {THEME['accent_bright']} !important;
        font-weight: 700 !important;
        box-shadow: 0 6px 22px rgba(201,161,90,0.28), inset 0 1px 0 rgba(255,255,255,0.25) !important;
    }}
    .stButton>button[kind="primary"]:hover {{
        filter: brightness(1.08) !important; transform: translateY(-1px) !important;
        box-shadow: 0 10px 30px rgba(201,161,90,0.4), inset 0 1px 0 rgba(255,255,255,0.3) !important;
    }}
    div[data-testid="stHorizontalBlock"] .stButton>button {{ border-radius: 999px !important; padding: 6px 18px !important; }}

    /* ── Radio (segmented control feel) ── */
    div[role="radiogroup"] {{ gap: 6px !important; }}
    div[role="radiogroup"] label {{
        background: {THEME['panel']} !important; border: 1px solid {THEME['border_soft']} !important;
        border-radius: 9px !important; padding: 7px 16px !important; transition: all 0.18s ease !important;
    }}
    div[role="radiogroup"] label:hover {{ border-color: {THEME['border']} !important; }}

    /* ── Inputs ── */
    .stTextInput input, .stNumberInput input, .stSelectbox > div, .stTextArea textarea {{
        background: {THEME['panel']} !important; border: 1px solid {THEME['border_soft']} !important;
        border-radius: 9px !important; color: {THEME['text']} !important;
        font-family: 'Inter', sans-serif !important;
        transition: border-color 0.18s ease, box-shadow 0.18s ease !important;
    }}
    .stTextInput input:focus, .stNumberInput input:focus, .stTextArea textarea:focus {{
        border-color: {THEME['accent']} !important; box-shadow: 0 0 0 3px {THEME['accent_dim']} !important;
    }}
    .stTextInput label, .stNumberInput label, .stSelectbox label, .stTextArea label, .stFileUploader label {{
        color: {THEME['text_dim']} !important; font-weight: 600 !important; font-size: 12.5px !important;
        letter-spacing: 0.03em !important; text-transform: uppercase !important;
    }}

    /* ── File uploader ── */
    [data-testid="stFileUploaderDropzone"] {{
        background: {THEME['panel']} !important; border: 1.5px dashed {THEME['border']} !important;
        border-radius: 12px !important;
    }}

    /* ── Metrics ── */
    [data-testid="stMetric"] {{
        background: linear-gradient(160deg, {THEME['panel']} 0%, rgba(16,20,31,0.3) 100%);
        border: 1px solid {THEME['border_soft']}; border-radius: 14px; padding: 1rem 1.2rem;
        backdrop-filter: blur(14px); -webkit-backdrop-filter: blur(14px);
        box-shadow: 0 6px 20px rgba(0,0,0,0.2);
        position: relative;
    }}
    [data-testid="stMetric"]::before {{
        content:""; position:absolute; top:0; left:0; right:0; height:2px; border-radius: 14px 14px 0 0;
        background: linear-gradient(90deg, transparent, {THEME['accent']}, transparent); opacity:0.6;
    }}
    [data-testid="stMetricLabel"] {{ color: {THEME['text_dim']} !important; font-size: 11.5px !important; letter-spacing: 0.05em !important; text-transform: uppercase !important; font-weight: 700 !important; }}
    [data-testid="stMetricValue"] {{ font-family: 'JetBrains Mono', monospace !important; color: {THEME['accent_bright']} !important; font-weight: 700 !important; }}

    /* ── Dataframes ── */
    [data-testid="stDataFrame"] {{
        border: 1px solid {THEME['border_soft']} !important; border-radius: 12px !important; overflow: hidden !important;
    }}

    /* ── Sidebar ── */
    section[data-testid="stSidebar"] {{
        background: linear-gradient(180deg, #0A0D14 0%, #07090D 100%) !important;
        border-right: 1px solid {THEME['border_soft']} !important;
    }}
    section[data-testid="stSidebar"] h3 {{
        font-family: 'Fraunces', Georgia, serif !important; letter-spacing: 0.02em !important;
        border-left: 2px solid {THEME['accent']}; padding-left: 10px; font-size: 1.05rem !important;
    }}

    /* ── Section titles ── */
    .section-title {{
        font-family: 'Fraunces', Georgia, serif;
        font-size: 1.15rem; font-weight: 600; color: {THEME['text']};
        margin: 1.8rem 0 0.6rem 0; padding-left: 14px;
        border-left: 3px solid {THEME['accent']};
        position: relative;
    }}

    /* ── Analytics cards ── */
    .analytics-card {{
        background: linear-gradient(160deg, {THEME['panel']} 0%, rgba(16,20,31,0.3) 100%);
        border: 1px solid {THEME['border_soft']}; border-radius: 16px; padding: 1.1rem 1.3rem; margin-bottom: 0.7rem;
        backdrop-filter: blur(14px); -webkit-backdrop-filter: blur(14px);
        box-shadow: 0 8px 28px rgba(0,0,0,0.25);
    }}

    /* ── Captions & dividers ── */
    .stCaption, [data-testid="stCaptionContainer"] {{ color: {THEME['text_dim']} !important; font-style: italic; }}
    hr {{ border-color: {THEME['border_soft']} !important; }}

    /* ── Alerts ── */
    [data-testid="stAlert"] {{ border-radius: 12px !important; border: 1px solid {THEME['border_soft']} !important; backdrop-filter: blur(10px); }}

    /* ── Expander / plotly container polish ── */
    .js-plotly-plot {{ border-radius: 12px; overflow: hidden; }}
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
        display:flex; align-items:center; gap:11px;
        background:{THEME['panel_solid']}; border:1px solid {THEME['border_soft']};
        border-radius:999px; padding:9px 20px; width:fit-content;
        font-family:'JetBrains Mono',monospace; color:{THEME['text']}; font-size:12.5px;
        box-shadow:0 4px 18px rgba(0,0,0,0.22);">
        <span style="width:7px;height:7px;border-radius:50%;background:{THEME['success']};
            box-shadow:0 0 10px {THEME['success']};"></span>
        <span id="slotra-date-text" style="font-weight:500; letter-spacing:0.01em;"></span>
    </div>
    <script>
        function renderSlotraDate() {{
            const el = document.getElementById('slotra-date-text');
            if (!el) return;
            const now = new Date();
            const opts = {{ weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' }};
            const timeOpts = {{ hour: '2-digit', minute: '2-digit' }};
            el.innerText = now.toLocaleDateString(undefined, opts) + '  ·  ' + now.toLocaleTimeString(undefined, timeOpts);
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
    st.markdown(f"""<div class='brand-header-center-layer'>
        <img src='{logo_src}' style='width:54px; border-radius:9px;'>
        <div style='display:flex; flex-direction:column;'>
            <div class='brand-word'>SLOTRA</div>
            <div class='brand-tag'>Plan Smart. Achieve More.</div>
        </div>
    </div>""", unsafe_allow_html=True)

    # ══════════════════════════════════════════════════════
    # INSTRUCTOR DATA INPUT — Excel/CSV upload OR manual setup
    # ══════════════════════════════════════════════════════
    st.markdown("### 👩‍🏫 Instructor Data Input")
    mode_choice = st.radio(
        "Choose input method",
        options=["📄 Excel / CSV Upload", "✍️ Manual Setup"],
        horizontal=True,
        index=0 if st.session_state.input_mode == "excel" else 1,
        label_visibility="collapsed",
    )
    st.session_state.input_mode = "excel" if "Excel" in mode_choice else "manual"

    # ── MODE 1: Excel / CSV upload ──────────────────────
    if st.session_state.input_mode == "excel":
        st.caption("Expected columns: **Name, Subjects, Max Days, Max Periods, Exclusions** (Subjects/Exclusions comma-separated)")
        uploaded_file = st.file_uploader("Upload instructor sheet", type=["xlsx", "xls", "csv"], label_visibility="collapsed")

        if uploaded_file is not None:
            try:
                if uploaded_file.name.lower().endswith(".csv"):
                    raw_df = pd.read_csv(uploaded_file)
                else:
                    raw_df = pd.read_excel(uploaded_file)

                raw_df.columns = [str(c).strip() for c in raw_df.columns]
                required_cols = {"Name", "Subjects", "Max Days", "Max Periods", "Exclusions"}
                missing = required_cols - set(raw_df.columns)

                if missing:
                    st.error(f"Missing column(s): {', '.join(sorted(missing))}. Please match the expected template.")
                else:
                    st.success(f"Loaded {len(raw_df)} instructor record(s).")
                    st.dataframe(raw_df, use_container_width=True, hide_index=True)

                    parsed_teachers = []
                    for i, row in raw_df.iterrows():
                        parsed_teachers.append(build_teacher_safe(
                            idx=i,
                            name=row["Name"],
                            subjects=row["Subjects"],
                            max_days=int(row["Max Days"]) if pd.notna(row["Max Days"]) else 5,
                            max_periods=int(row["Max Periods"]) if pd.notna(row["Max Periods"]) else 20,
                            exclusions=row["Exclusions"] if pd.notna(row["Exclusions"]) else "",
                        ))
                    st.session_state.teachers = parsed_teachers
            except Exception as e:
                st.error(f"Couldn't parse the uploaded file: {e}")
        else:
            st.info("Upload a .xlsx, .xls or .csv file to load instructors, or switch to Manual Setup.")

    # ── MODE 2: Manual instructor setup ─────────────────
    else:
        st.caption("Add instructors one by one. Subjects and Exclusions accept comma-separated values.")

        for i, instr in enumerate(st.session_state.manual_instructors):
            with st.container():
                st.markdown("<div class='instructor-card'>", unsafe_allow_html=True)
                row1_c1, row1_c2, row1_c3 = st.columns([2, 2, 1])
                with row1_c1:
                    instr["name"] = st.text_input("Instructor Name", instr["name"], key=f"mi_name_{i}")
                with row1_c2:
                    instr["subjects"] = st.text_input("Subjects (comma-separated)", instr["subjects"], key=f"mi_subj_{i}")
                with row1_c3:
                    st.write("")
                    st.write("")
                    if st.button("🗑️ Remove", key=f"mi_remove_{i}") and len(st.session_state.manual_instructors) > 1:
                        st.session_state.manual_instructors.pop(i)
                        st.rerun()

                row2_c1, row2_c2, row2_c3 = st.columns(3)
                with row2_c1:
                    instr["max_days"] = st.number_input("Max Days / Week", 1, 6, instr["max_days"], key=f"mi_days_{i}")
                with row2_c2:
                    instr["max_periods"] = st.number_input("Max Periods / Week", 1, 40, instr["max_periods"], key=f"mi_periods_{i}")
                with row2_c3:
                    instr["exclusions"] = st.text_input("Exclusions (comma-separated)", instr["exclusions"], key=f"mi_excl_{i}")
                st.markdown("</div>", unsafe_allow_html=True)

        add_col, _ = st.columns([1, 4])
        with add_col:
            if st.button("➕ Add Instructor"):
                st.session_state.manual_instructors.append(
                    {"name": "", "subjects": "", "max_days": 5, "max_periods": 20, "exclusions": ""}
                )
                st.rerun()

        # Build Teacher objects live from the manual form so the count below is accurate
        st.session_state.teachers = [
            build_teacher_safe(i, instr["name"], instr["subjects"], instr["max_days"], instr["max_periods"], instr["exclusions"])
            for i, instr in enumerate(st.session_state.manual_instructors) if instr["name"].strip()
        ]

    st.markdown(f"**{len(st.session_state.teachers)} instructor(s) ready** for scheduling.")
    st.divider()

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

    # Shared premium Plotly layout polish — applied on top of the existing
    # template so palettes/behavior are unchanged, only typography/chrome.
    PLOTLY_LAYOUT_EXTRAS = dict(
        font=dict(family=PLOTLY_FONT, color=THEME["text_dim"], size=12),
        title_font=dict(family="Fraunces, Georgia, serif", color=THEME["text"], size=16),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(t=56, l=10, r=10, b=10),
    )

    with col_a:
        fig_a = px.pie(df.groupby("Teacher").size().reset_index(name="Classes"), values='Classes', names='Teacher', title='Workload Distribution', template=template)
        fig_a.update_layout(**PLOTLY_LAYOUT_EXTRAS)
        st.plotly_chart(fig_a, use_container_width=True)
    with col_b:
        fig_b = px.bar(df.groupby("Teacher").size().reset_index(name="Classes"), x='Teacher', y='Classes', title='Class Count per Instructor', template=template)
        fig_b.update_traces(marker_color=THEME["accent"])
        fig_b.update_layout(**PLOTLY_LAYOUT_EXTRAS)
        st.plotly_chart(fig_b, use_container_width=True)
    with col_c:
        fig_c = px.box(pd.DataFrame([{"Period": s.timeslot.period + 1} for s in st.session_state.timetable]), y="Period", title="Period Density Analysis", template=template)
        fig_c.update_traces(marker_color=THEME["accent_bright"])
        fig_c.update_layout(**PLOTLY_LAYOUT_EXTRAS)
        st.plotly_chart(fig_c, use_container_width=True)

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
        fig_infra1 = px.bar(
            infra_day_df, x="Day", y="Total Rooms Used",
            color="Avg Room Saturation %", color_continuous_scale="Tealgrn" if D else "Blues",
            title="Infrastructure Workload by Day", template=template
        )
        fig_infra1.update_layout(**PLOTLY_LAYOUT_EXTRAS)
        st.plotly_chart(fig_infra1, use_container_width=True)

    with infra_col2:
        fig_infra2 = px.bar(
            room_workload_df, x="Room", y="Classes Scheduled",
            color="Utilization %", color_continuous_scale="Oranges",
            title="Room-wise Utilization", template=template
        )
        fig_infra2.update_layout(**PLOTLY_LAYOUT_EXTRAS)
        st.plotly_chart(fig_infra2, use_container_width=True)

    # Composite stress heatmap — Day x Period pressure map
    if not stress_df.empty:
        heat_pivot = stress_df.pivot(index="Period", columns="Day", values="Composite Stress Index")
        day_order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
        heat_pivot = heat_pivot[[d for d in day_order if d in heat_pivot.columns]]
        fig_heat = px.imshow(
            heat_pivot, text_auto=True, aspect="auto",
            color_continuous_scale="Inferno" if D else "YlOrRd",
            title="Composite Stress Heatmap (Day × Period)", template=template
        )
        fig_heat.update_layout(**PLOTLY_LAYOUT_EXTRAS)
        st.plotly_chart(fig_heat, use_container_width=True)

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
            fig_sun = px.sunburst(
                df, path=["Section", "Subject"], title="Subject Load Breakdown by Section",
                template=template
            )
            fig_sun.update_layout(**PLOTLY_LAYOUT_EXTRAS)
            st.plotly_chart(fig_sun, use_container_width=True)
        else:
            st.caption("Subject breakdown will appear once a timetable is generated.")

    if st.button("← Modify Constraints / Inputs"):
        st.session_state.page = "home"
        st.rerun()
