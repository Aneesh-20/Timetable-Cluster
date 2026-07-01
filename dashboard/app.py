import sys, os
# Corrected: Used __file__ with double underscores
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import streamlit as st
import pandas as pd
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
if "splash_done" not in st.session_state: st.session_state.splash_done = False
if "manual_instructors" not in st.session_state: 
    st.session_state.manual_instructors = [{"name": "", "subjects": "", "max_days": 5, "max_periods": 20, "exclusions": ""}]

D = st.session_state.dark_mode
THEME = {
    "bg": "#0B0E14" if D else "#F5F7FA",
    "card": "rgba(22, 28, 45, 0.65)" if D else "rgba(255, 255, 255, 0.9)",
    "accent": "#14A8B7" if D else "#0070F3",
    "text": "#F3F4F6" if D else "#111827",
    "sub": "#9CA3AF" if D else "#4B5563",
    "border": "rgba(20,168,183,0.18)",
    "grid": "rgba(255,255,255,0.02)"
}

# ── ASSET LOGO IMAGE RESOLUTION ENGINE ──────────
logo_filename = "slotra_logo.png"
logo_src = ""
if os.path.exists(logo_filename):
    with open(logo_filename, "rb") as image_file:
        logo_src = f"data:image/png;base64,{base64.b64encode(image_file.read()).decode()}"

# ── GLOBAL STYLES ──────────────────────────────
st.markdown(f"""
<style>
    .stApp {{background-color: {THEME['bg']}!important; color: {THEME['text']}!important;}}
    .brand-header-center-layer {{
        display: flex; align-items: center; justify-content: center; gap: 15px;
        margin: 0 auto 2rem auto; padding: 15px; background: #0E131F;
        border: 2px solid {THEME['accent']}; border-radius: 16px; width: fit-content;
    }}
    .brand-title {{color: #FFF; font-size: 24px; font-weight: 900; letter-spacing: 3px;}}
    .brand-tagline {{color: {THEME['sub']}; font-size: 8px; font-weight: 700; letter-spacing: 1px;}}
</style>
""", unsafe_allow_html=True)

# ── HEADER: DATE & TOGGLE (Top Right) ───────────
col_top1, col_top2 = st.columns([4, 1])
with col_top2:
    st.markdown(f"**{datetime.now().strftime('%b %d, %Y')}**")
    if st.button("🌓 Toggle Theme"):
        st.session_state.dark_mode = not st.session_state.dark_mode
        st.rerun()

# ── MAIN BODY ──────────────────────────────────
if st.session_state.page == "home":
    # Centered Logo
    st.markdown(f"""
    <div class="brand-header-center-layer">
        <img src="{logo_src}" style="width:40px; height:40px; border-radius:8px;">
        <div style="display:flex; flex-direction:column;">
            <div class="brand-title">SLOTRA</div>
            <div class="brand-tagline">PLAN SMART. ACHIEVE MORE.</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # Insert your functional code (Buttons, Uploader, Logic) here below
    st.write("System Ready. Add your UI components here.")
