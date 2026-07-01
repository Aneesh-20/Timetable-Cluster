import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import streamlit as st
import pandas as pd
import plotly.express as px
import base64
import numpy as np
import time
from datetime import datetime
from src.models import Teacher, Room, Section
from src.solver import TimetableSolver
from src.constraints import check_hard_constraints

# ── APP INITIALIZATION & THEME CONFIGURATION ────────────
st.set_page_config(page_title="Slotra", layout="wide")

if "dark_mode" not in st.session_state: st.session_state.dark_mode = True
if "page" not in st.session_state: st.session_state.page = "home"
if "input_mode" not in st.session_state: st.session_state.input_mode = "excel"

D = st.session_state.dark_mode
THEME = {
    "bg": "#0B0E14" if D else "#F5F7FA",
    "card": "rgba(22, 28, 45, 0.65)" if D else "rgba(255, 255, 255, 0.9)",
    "accent": "#14A8B7" if D else "#0070F3",
    "text": "#F3F4F6" if D else "#111827",
    "sub": "#9CA3AF" if D else "#4B5563"
}

# ── LOGO ENGINE ──────────
logo_filename = "slotra_logo.png"
logo_src = ""
if os.path.exists(logo_filename):
    with open(logo_filename, "rb") as image_file:
        logo_src = f"data:image/png;base64,{base64.b64encode(image_file.read()).decode()}"

# ── ANALYTICS FUNCTIONS ──
def plot_workload_analytics(timetable_data, teachers_list):
    workload = {t.name: 0 for t in teachers_list}
    for slot in timetable_data:
        t = next((t for t in teachers_list if t.id == slot.teacher_id), None)
        if t: workload[t.name] += 1
    
    df = pd.DataFrame(list(workload.items()), columns=['Teacher', 'Classes'])
    
    fig_pie = px.pie(df, values='Classes', names='Teacher', title='Staff Workload Distribution', template="plotly_dark" if D else "plotly")
    fig_bar = px.bar(df, x='Teacher', y='Classes', color='Classes', title='Class Count per Instructor', template="plotly_dark" if D else "plotly")
    
    return fig_pie, fig_bar

# ── HEADER & UI ──────────
st.markdown(f"<style>.stApp {{background-color: {THEME['bg']}!important;}}</style>", unsafe_allow_html=True)

col_top1, col_top2 = st.columns([4, 1])
with col_top2:
    st.markdown(f"**{datetime.now().strftime('%b %d, %Y')}**")
    if st.button("🌓 Toggle Theme"):
        st.session_state.dark_mode = not st.session_state.dark_mode
        st.rerun()

if st.session_state.page == "home":
    st.markdown(f"""
    <div style="display: flex; align-items: center; justify-content: center; margin-bottom: 2rem;">
        <img src="{logo_src}" style="width:50px; border-radius:8px; margin-right:15px;">
        <div><h1 style="margin:0;">SLOTRA</h1><p>AUTOMATED INFRASTRUCTURE SCHEDULER</p></div>
    </div>
    """, unsafe_allow_html=True)
    st.info("System Ready. Add your scheduling logic here.")

else:
    # ── EXECUTIVE ANALYTICS SUITE ──
    st.header("📊 Executive Analytics Suite")
    timetable = st.session_state.timetable
    teachers = st.session_state.teachers
    
    col_v1, col_v2 = st.columns(2)
    pie_fig, bar_fig = plot_workload_analytics(timetable, teachers)
    
    with col_v1:
        st.plotly_chart(pie_fig, use_container_width=True)
    with col_v2:
        st.plotly_chart(bar_fig, use_container_width=True)
        
    st.subheader("Period Utilization Patterns")
    period_data = [{"Period": slot.timeslot.period + 1} for slot in timetable]
    fig_box = px.box(pd.DataFrame(period_data), y="Period", title="Distribution of Classes across Periods", template="plotly_dark" if D else "plotly")
    st.plotly_chart(fig_box, use_container_width=True)

    if st.button("← Modify Constraints / Inputs"):
        st.session_state.page = "home"
        st.rerun()
