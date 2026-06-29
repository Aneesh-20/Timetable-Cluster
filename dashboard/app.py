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

st.set_page_config(page_title="Slotra", layout="wide", page_icon="S")

if "timetable"    not in st.session_state: st.session_state.timetable    = None
if "violations"   not in st.session_state: st.session_state.violations   = []
if "dark_mode"    not in st.session_state: st.session_state.dark_mode    = True
if "page"         not in st.session_state: st.session_state.page         = "splash"
if "teachers"     not in st.session_state: st.session_state.teachers     = []
if "rooms"        not in st.session_state: st.session_state.rooms        = []
if "sections"     not in st.session_state: st.session_state.sections     = []
if "teacher_rows" not in st.session_state:
    st.session_state.teacher_rows = [
        {"name":"Mr. Kumar",   "subjects":"Math,Physics",     "unavailable":""},
        {"name":"Ms. Priya",   "subjects":"English",          "unavailable":""},
        {"name":"Mr. Rajan",   "subjects":"Science",          "unavailable":""},
        {"name":"Ms. Deepa",   "subjects":"Computer Science", "unavailable":""},
        {"name":"Mr. Arjun",   "subjects":"History,Geography","unavailable":""},
    ]
if "room_rows" not in st.session_state:
    st.session_state.room_rows = [
        {"id":"R101","name":"Room 101","capacity":40},
        {"id":"R102","name":"Room 102","capacity":40},
        {"id":"R103","name":"Room 103","capacity":35},
    ]
if "section_rows" not in st.session_state:
    st.session_state.section_rows = [
        {"id":"10A","name":"Class 10 A","strength":35,
         "subjects":"Math:5,English:5,Science:4,History:3,Geography:3"},
        {"id":"10B","name":"Class 10 B","strength":33,
         "subjects":"Math:5,English:5,Science:4,History:3,Geography:3"},
        {"id":"11A","name":"Class 11 A","strength":30,
         "subjects":"Math:5,English:4,Science:4,Computer Science:4,History:3"},
    ]

D       = st.session_state.dark_mode
bg      = "#0E1117" if D else "#F4F6FA"
card    = "#151929" if D else "#FFFFFF"
card2   = "#1C2136" if D else "#F0F4FF"
accent  = "#4FC3F7" if D else "#1565C0"
text    = "#FFFFFF" if D else "#111827"
sub     = "#8892A4" if D else "#6B7280"
border  = "rgba(79,195,247,0.15)" if D else "rgba(21,101,192,0.15)"
grid_c  = "rgba(255,255,255,0.04)" if D else "rgba(0,0,0,0.04)"
row_bg  = "#0D1320" if D else "#F8FAFF"
plot_bg = "rgba(0,0,0,0)"
t_icon  = "☀️" if D else "🌙"
t_lbl   = "Light" if D else "Dark"

logo_b64 = ""
logo_path = os.path.join(os.path.dirname(__file__), "slotra_logo.png")
if os.path.exists(logo_path):
    with open(logo_path, "rb") as f:
        logo_b64 = base64.b64encode(f.read()).decode()

today    = datetime.now().strftime("%d %b %Y")
day_name = datetime.now().strftime("%A")

st.markdown(f"""
<style>
section[data-testid="stSidebar"]{{display:none;}}
#MainMenu{{visibility:hidden;}}footer{{visibility:hidden;}}header{{visibility:hidden;}}
.stApp{{background-color:{bg}!important;}}
.block-container{{padding-top:.75rem!important;padding-bottom:2rem!important;}}
*{{cursor:crosshair!important;}}
.grid-bg{{position:fixed;inset:0;pointer-events:none;z-index:0;
    background-image:linear-gradient({grid_c} 1px,transparent 1px),
    linear-gradient(90deg,{grid_c} 1px,transparent 1px);
    background-size:44px 44px;}}
.topbar{{display:flex;align-items:center;justify-content:space-between;
    padding:.5rem 0 .75rem;border-bottom:0.5px solid {border};
    margin-bottom:1rem;position:relative;z-index:10;}}
.logo-img{{width:52px;height:52px;border-radius:12px;object-fit:cover;}}
.hero-section{{text-align:center;padding:2rem 1rem .75rem;position:relative;z-index:1;}}
.hero-title{{font-size:64px;font-weight:900;color:{accent};
    letter-spacing:-3px;line-height:1;margin-bottom:.3rem;font-family:Georgia,serif;}}
.hero-sub{{font-size:15px;color:{sub};font-style:italic;margin:0 auto 1.25rem;}}
.stat-row{{display:grid;grid-template-columns:repeat(3,1fr);
    gap:1px;background:{border};border:0.5px solid {border};
    border-radius:14px;overflow:hidden;max-width:380px;margin:0 auto 1.5rem;}}
.stat-cell{{background:{card};padding:.9rem;text-align:center;}}
.stat-num{{font-size:26px;font-weight:800;color:{accent};line-height:1;}}
.stat-lbl{{font-size:9px;color:{sub};text-transform:uppercase;
    letter-spacing:.07em;margin-top:3px;}}
.feat-grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(148px,1fr));
    gap:10px;margin-bottom:1.5rem;position:relative;z-index:1;}}
.fc{{background:{card};border:0.5px solid {border};border-radius:12px;
    padding:.9rem;transition:border-color .2s,transform .15s;}}
.fc:hover{{border-color:{accent}80;transform:translateY(-3px);}}
.fi{{font-size:18px;margin-bottom:7px;display:block;}}
.ft{{font-size:12px;font-weight:700;color:{text};margin-bottom:2px;}}
.fd{{font-size:11px;color:{sub};line-height:1.45;}}
.sec-lbl{{font-size:11px;font-weight:700;color:{sub};
    text-transform:uppercase;letter-spacing:.09em;margin:1.25rem 0 .5rem;}}
.row-badge{{font-size:10px;font-weight:700;padding:2px 8px;
    border-radius:999px;background:{accent}20;color:{accent};
    display:inline-block;margin-bottom:6px;letter-spacing:.05em;}}
.field-label{{font-size:10px;font-weight:600;color:{sub};
    text-transform:uppercase;letter-spacing:.07em;margin-bottom:3px;}}
.hint-tag{{font-size:10px;color:{accent};background:{accent}15;
    padding:2px 8px;border-radius:999px;display:inline-block;margin-left:6px;}}
.mc{{background:{card2};border:0.5px solid {border};
    border-radius:12px;padding:1.1rem;text-align:center;margin:3px;}}
.mv{{font-size:34px;font-weight:800;color:{accent};line-height:1;}}
.ml{{font-size:10px;color:{sub};text-transform:uppercase;
    letter-spacing:.06em;margin-top:3px;}}
div[data-testid="stButton"]>button[kind="primary"]{{
    background:linear-gradient(135deg,{accent} 0%,#1565C0 100%)!important;
    color:#FFFFFF!important;border:none!important;border-radius:10px!important;
    font-size:15px!important;font-weight:700!important;
    padding:.65rem 2rem!important;letter-spacing:.03em!important;
    box-shadow:0 4px 18px {accent}50!important;}}
div[data-testid="stButton"]>button[kind="primary"]:hover{{
    opacity:.88!important;transform:translateY(-1px)!important;}}
div[data-testid="stButton"]>button:not([kind="primary"]){{
    font-size:12px!important;padding:4px 10px!important;
    min-height:0!important;height:auto!important;
    border-radius:8px!important;border:0.5px solid {border}!important;
    background:{card2}!important;color:{text}!important;}}
div[data-testid="stExpander"]{{background:{card}!important;
    border:0.5px solid {border}!important;border-radius:12px!important;}}
#splash{{position:fixed;inset:0;z-index:99999;background:#0A0E1A;
    display:flex;flex-direction:column;align-items:center;
    justify-content:center;animation:splashFade 0.6s ease 1.6s forwards;}}
@keyframes splashFade{{0%{{opacity:1;transform:scale(1);}}
    100%{{opacity:0;transform:scale(1.06);pointer-events:none;}}}}
.splash-logo{{width:120px;height:120px;border-radius:28px;object-fit:cover;
    animation:splashPop 0.5s cubic-bezier(.34,1.56,.64,1) 0.2s both;
    box-shadow:0 0 60px #4FC3F780;}}
@keyframes splashPop{{0%{{opacity:0;transform:scale(0.5);}}
    100%{{opacity:1;transform:scale(1);}}}}
.splash-name{{font-size:42px;font-weight:900;color:#4FC3F7;
    letter-spacing:-2px;font-family:Georgia,serif;margin-top:18px;
    animation:splashSlide 0.5s ease 0.6s both;}}
@keyframes splashSlide{{0%{{opacity:0;transform:translateY(14px);}}
    100%{{opacity:1;transform:translateY(0);}}}}
.splash-bar{{width:60px;height:3px;border-radius:999px;
    background:linear-gradient(90deg,#4FC3F7,#1565C0);margin-top:16px;
    animation:splashBar 0.6s ease 0.9s both;}}
@keyframes splashBar{{0%{{width:0;opacity:0;}}100%{{width:60px;opacity:1;}}}}
</style>
<div class="grid-bg"></div>
""", unsafe_allow_html=True)

# ── SPLASH ───────────────────────────────────────────────
if st.session_state.page == "splash":
    if logo_b64:
        st.markdown(f"""
        <div id="splash">
          <img class="splash-logo"
               src="data:image/png;base64,{logo_b64}" alt="Slotra"/>
          <div class="splash-name">Slotra</div>
          <div class="splash-bar"></div>
        </div>
        <script>
          setTimeout(function(){{
            var s=document.getElementById('splash');
            if(s)s.style.display='none';
          }},2300);
        </script>""", unsafe_allow_html=True)
    st.session_state.page = "home"
    import time; time.sleep(1.8)
    st.rerun()

# ── TOP BAR ──────────────────────────────────────────────
logo_html = (f'<img class="logo-img" src="data:image/png;base64,{logo_b64}" alt="Slotra"/>'
             if logo_b64 else '<div style="font-size:32px;">S</div>')

tl, tr = st.columns([4, 2])
with tl:
    st.markdown(f"""
    <div class="topbar">
      <div>{logo_html}</div>
    </div>""", unsafe_allow_html=True)
with tr:
    st.markdown(f"""
    <div style="display:flex;align-items:center;justify-content:flex-end;
                gap:10px;padding-top:.4rem;">
      <div style="text-align:right;border-right:1.5px solid {accent}40;
                  padding-right:12px;margin-right:2px;">
        <div style="font-size:13px;font-weight:700;color:{accent};
                    line-height:1.2;">{day_name}</div>
        <div style="font-size:10px;color:{sub};">{today}</div>
      </div>
    </div>""", unsafe_allow_html=True)
    if st.button(f"{t_icon}", key="theme"):
        st.session_state.dark_mode = not st.session_state.dark_mode
        st.rerun()

# ════════════════════════════════════════════════════════
#  HOME PAGE
# ════════════════════════════════════════════════════════
if st.session_state.page == "home":
    tt         = st.session_state.timetable
    viol       = st.session_state.violations
    secs       = st.session_state.sections
    n_assign   = len(tt)   if tt   else 0
    n_viol     = len(viol) if viol else 0
    n_sections = len(secs) if secs else len(st.session_state.section_rows)

    st.markdown(f"""
    <div class="hero-section">
      <div class="hero-title">Slotra</div>
      <div class="hero-sub">Smart Timetables Through Clustering</div>
    </div>
    <div class="stat-row">
      <div class="stat-cell">
        <div class="stat-num">{n_assign}</div>
        <div class="stat-lbl">Assignments</div>
      </div>
      <div class="stat-cell">
        <div class="stat-num">{n_viol}</div>
        <div class="stat-lbl">Violations</div>
      </div>
      <div class="stat-cell">
        <div class="stat-num">{n_sections}</div>
        <div class="stat-lbl">Sections</div>
      </div>
    </div>
    <div class="feat-grid">
      <div class="fc"><span class="fi">⚡</span>
        <div class="ft">Instant generation</div>
        <div class="fd">Full week timetable in under 1 second.</div></div>
      <div class="fc"><span class="fi">✅</span>
        <div class="ft">Zero conflicts</div>
        <div class="fd">No teacher or room ever double-booked.</div></div>
      <div class="fc"><span class="fi">🏫</span>
        <div class="ft">Any school</div>
        <div class="fd">Input your own teachers, rooms and sections.</div></div>
      <div class="fc"><span class="fi">📊</span>
        <div class="ft">Live analytics</div>
        <div class="fd">Charts, heatmaps and workload views.</div></div>
      <div class="fc"><span class="fi">🧬</span>
        <div class="ft">GA solver</div>
        <div class="fd">300-generation genetic algorithm.</div></div>
      <div class="fc"><span class="fi">📥</span>
        <div class="ft">CSV export</div>
        <div class="fd">Download any class timetable instantly.</div></div>
    </div>""", unsafe_allow_html=True)

    st.markdown("<div class='sec-lbl'>Configure your school</div>",
                unsafe_allow_html=True)

    # ── TEACHERS ─────────────────────────────────────────
    st.markdown(f"""<div style='background:{card2};border:0.5px solid {border};
        border-radius:12px;padding:12px 16px 4px;margin-bottom:6px;'>
      <span style='font-size:14px;font-weight:700;color:{text};'>Teachers</span>
      <span style='font-size:11px;color:{sub};margin-left:10px;'>
        Name · Subjects they teach</span>
    </div>""", unsafe_allow_html=True)

    for i, row in enumerate(st.session_state.teacher_rows):
        st.markdown(
            f"<div style='background:{row_bg};border:0.5px solid {border}50;"
            f"border-radius:8px;padding:6px 10px 0;margin-bottom:6px;'>"
            f"<span class='row-badge'>Teacher {i+1}</span></div>",
            unsafe_allow_html=True)
        c1, c2, c3 = st.columns([2, 2, .35])
        with c1:
            st.markdown("<div class='field-label'>Full name</div>",
                        unsafe_allow_html=True)
            st.session_state.teacher_rows[i]["name"] = st.text_input(
                "name", value=row["name"], key=f"tn{i}",
                placeholder="e.g. Mr. Kumar",
                label_visibility="collapsed")
        with c2:
            st.markdown(
                "<div class='field-label'>Subjects "
                "<span class='hint-tag'>comma separated</span></div>",
                unsafe_allow_html=True)
            st.session_state.teacher_rows[i]["subjects"] = st.text_input(
                "subjects", value=row["subjects"], key=f"ts{i}",
                placeholder="e.g. Math,Physics",
                label_visibility="collapsed")
        with c3:
            st.markdown("<br><br>", unsafe_allow_html=True)
            if st.button("X", key=f"td{i}"):
                st.session_state.teacher_rows.pop(i)
                st.rerun()

    if st.button("+ Add teacher", key="add_teacher"):
        st.session_state.teacher_rows.append(
            {"name": "", "subjects": "", "unavailable": ""})
        st.rerun()

    st.markdown("<br>", unsafe_allow_html=True)

    # ── ROOMS ────────────────────────────────────────────
    st.markdown(f"""<div style='background:{card2};border:0.5px solid {border};
        border-radius:12px;padding:12px 16px 4px;margin-bottom:6px;'>
      <span style='font-size:14px;font-weight:700;color:{text};'>Rooms</span>
      <span style='font-size:11px;color:{sub};margin-left:10px;'>
        Room ID · Name · Capacity</span>
    </div>""", unsafe_allow_html=True)

    for i, row in enumerate(st.session_state.room_rows):
        st.markdown(
            f"<div style='background:{row_bg};border:0.5px solid {border}50;"
            f"border-radius:8px;padding:6px 10px 0;margin-bottom:6px;'>"
            f"<span class='row-badge'>Room {i+1}</span></div>",
            unsafe_allow_html=True)
        c1, c2, c3, c4 = st.columns([1.5, 2.5, 1.2, .35])
        with c1:
            st.markdown("<div class='field-label'>Room ID</div>",
                        unsafe_allow_html=True)
            st.session_state.room_rows[i]["id"] = st.text_input(
                "rid", value=row["id"], key=f"ri{i}",
                placeholder="e.g. R101",
                label_visibility="collapsed")
        with c2:
            st.markdown("<div class='field-label'>Room name</div>",
                        unsafe_allow_html=True)
            st.session_state.room_rows[i]["name"] = st.text_input(
                "rname", value=row["name"], key=f"rn{i}",
                placeholder="e.g. Room 101",
                label_visibility="collapsed")
        with c3:
            st.markdown(
                "<div class='field-label'>Capacity "
                "<span class='hint-tag'>max students</span></div>",
                unsafe_allow_html=True)
            st.session_state.room_rows[i]["capacity"] = st.number_input(
                "cap", value=row["capacity"], min_value=1,
                key=f"rc{i}", label_visibility="collapsed")
        with c4:
            st.markdown("<br><br>", unsafe_allow_html=True)
            if st.button("X", key=f"rd{i}"):
                st.session_state.room_rows.pop(i)
                st.rerun()

    if st.button("+ Add room", key="add_room"):
        st.session_state.room_rows.append(
            {"id": "", "name": "", "capacity": 30})
        st.rerun()

    st.markdown("<br>", unsafe_allow_html=True)

    # ── SECTIONS ─────────────────────────────────────────
    st.markdown(f"""<div style='background:{card2};border:0.5px solid {border};
        border-radius:12px;padding:12px 16px 4px;margin-bottom:6px;'>
      <span style='font-size:14px;font-weight:700;color:{text};'>Sections</span>
      <span style='font-size:11px;color:{sub};margin-left:10px;'>
        ID · Name · Students · Subjects:periods e.g. Math:5,English:4</span>
    </div>""", unsafe_allow_html=True)

    for i, row in enumerate(st.session_state.section_rows):
        st.markdown(
            f"<div style='background:{row_bg};border:0.5px solid {border}50;"
            f"border-radius:8px;padding:6px 10px 0;margin-bottom:6px;'>"
            f"<span class='row-badge'>Section {i+1}</span></div>",
            unsafe_allow_html=True)
        c1, c2, c3, c4, c5 = st.columns([1, 1.5, .8, 3, .35])
        with c1:
            st.markdown("<div class='field-label'>Section ID</div>",
                        unsafe_allow_html=True)
            st.session_state.section_rows[i]["id"] = st.text_input(
                "sid", value=row["id"], key=f"si{i}",
                placeholder="e.g. 10A",
                label_visibility="collapsed")
        with c2:
            st.markdown("<div class='field-label'>Name</div>",
                        unsafe_allow_html=True)
            st.session_state.section_rows[i]["name"] = st.text_input(
                "sname", value=row["name"], key=f"sn{i}",
                placeholder="e.g. Class 10 A",
                label_visibility="collapsed")
        with c3:
            st.markdown("<div class='field-label'>Students</div>",
                        unsafe_allow_html=True)
            st.session_state.section_rows[i]["strength"] = st.number_input(
                "str", value=row["strength"], min_value=1,
                key=f"ss{i}", label_visibility="collapsed")
        with c4:
            st.markdown(
                "<div class='field-label'>Subjects "
                "<span class='hint-tag'>Math:5,English:4</span></div>",
                unsafe_allow_html=True)
            st.session_state.section_rows[i]["subjects"] = st.text_input(
                "ssubj", value=row["subjects"], key=f"sb{i}",
                placeholder="e.g. Math:5,English:5,Science:4",
                label_visibility="collapsed")
        with c5:
            st.markdown("<br><br>", unsafe_allow_html=True)
            if st.button("X", key=f"sd{i}"):
                st.session_state.section_rows.pop(i)
                st.rerun()

    if st.button("+ Add section", key="add_section"):
        st.session_state.section_rows.append(
            {"id": "", "name": "", "strength": 30, "subjects": ""})
        st.rerun()

    st.markdown("<br>", unsafe_allow_html=True)
    c1, c2, c3 = st.columns([1.2, 2, 1.2])
    with c2:
        generate = st.button("Generate Timetable",
                             type="primary", use_container_width=True)

    if generate:
        teachers_list = []
        for i, row in enumerate(st.session_state.teacher_rows):
            if not row["name"].strip():
                continue
            subjs = [s.strip() for s in row["subjects"].split(",")
                     if s.strip()]
            teachers_list.append(Teacher(
                id=f"T{i+1:03d}", name=row["name"].strip(),
                subjects=subjs, unavailable=[]))
        rooms_list = []
        for row in st.session_state.room_rows:
            if not row["id"].strip():
                continue
            rooms_list.append(Room(
                id=row["id"].strip(), name=row["name"].strip(),
                capacity=int(row["capacity"])))
        sections_list = []
        for row in st.session_state.section_rows:
            if not row["id"].strip():
                continue
            sp = {}
            for item in row["subjects"].split(","):
                item = item.strip()
                if ":" in item:
                    p = item.rsplit(":", 1)
                    try:
                        sp[p[0].strip()] = int(p[1].strip())
                    except:
                        pass
            sections_list.append(Section(
                id=row["id"].strip(), name=row["name"].strip(),
                strength=int(row["strength"]), subject_periods=sp))

        if not teachers_list:
            st.error("Add at least one teacher.")
        elif not rooms_list:
            st.error("Add at least one room.")
        elif not sections_list:
            st.error("Add at least one section.")
        else:
            with st.spinner("Building conflict-free timetable..."):
                try:
                    solver = TimetableSolver(
                        teachers_list, rooms_list, sections_list)
                    solver.create_variables()
                    solver.add_coverage_constraint()
                    solver.add_section_no_clash()
                    solver.add_teacher_no_clash()
                    solver.add_room_no_clash()
                    tt = solver.solve()
                    viol = check_hard_constraints(
                        tt, teachers_list, rooms_list)
                    st.session_state.timetable  = tt
                    st.session_state.violations = viol
                    st.session_state.teachers   = teachers_list
                    st.session_state.rooms      = rooms_list
                    st.session_state.sections   = sections_list
                    st.session_state.page       = "dashboard"
                    st.rerun()
                except Exception as e:
                    st.error(f"Error: {e}")

# ════════════════════════════════════════════════════════
#  DASHBOARD
# ════════════════════════════════════════════════════════
else:
    teachers  = st.session_state.teachers
    rooms     = st.session_state.rooms
    sections  = st.session_state.sections
    timetable = st.session_state.timetable
    violations = st.session_state.violations

    cb, cr2 = st.columns([1, 1])
    with cb:
        if st.button("← Back to home"):
            st.session_state.page = "home"
            st.rerun()
    with cr2:
        if st.button("🔄 Regenerate", type="primary"):
            with st.spinner("Regenerating..."):
                try:
                    solver = TimetableSolver(teachers, rooms, sections)
                    solver.create_variables()
                    solver.add_coverage_constraint()
                    solver.add_section_no_clash()
                    solver.add_teacher_no_clash()
                    solver.add_room_no_clash()
                    tt = solver.solve()
                    viol = check_hard_constraints(tt, teachers, rooms)
                    st.session_state.timetable  = tt
                    st.session_state.violations = viol
                    timetable = tt
                    violations = viol
                    st.rerun()
                except Exception as e:
                    st.error(f"Error: {e}")

    st.markdown("<br>", unsafe_allow_html=True)
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.markdown(f"<div class='mc'><div class='mv'>{len(timetable)}</div>"
                    f"<div class='ml'>Assignments</div></div>",
                    unsafe_allow_html=True)
    with c2:
        st.markdown(f"<div class='mc'><div class='mv'>{len(violations)}</div>"
                    f"<div class='ml'>Violations</div></div>",
                    unsafe_allow_html=True)
    with c3:
        st.markdown(f"<div class='mc'><div class='mv'>{len(sections)}</div>"
                    f"<div class='ml'>Sections</div></div>",
                    unsafe_allow_html=True)
    with c4:
        st.markdown(f"<div class='mc'><div class='mv'>{len(teachers)}</div>"
                    f"<div class='ml'>Teachers</div></div>",
                    unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)
    if len(violations) == 0:
        st.success("✅ PERFECT timetable — zero conflicts!")
    else:
        st.error(f"❌ {len(violations)} conflicts found")
        for v in violations:
            st.caption(f"• {v}")
    st.markdown("---")

    days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
    rows = []
    for a in timetable:
        teacher = next((t for t in teachers if t.id == a.teacher_id), None)
        rows.append({
            "Section": a.section_id, "Subject": a.subject,
            "Teacher": teacher.name if teacher else a.teacher_id,
            "Room": a.room_id, "Day": days[a.timeslot.day],
            "DayN": a.timeslot.day,
            "PerN": a.timeslot.period + 1,
            "Period": f"P{a.timeslot.period + 1}"
        })
    df = pd.DataFrame(rows).sort_values(["DayN", "PerN"])

    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "📅 Class Timetable", "👨‍🏫 Teacher View",
        "🏠 Room Utilization", "📊 Charts", "📥 Download"])

    with tab1:
        sel = st.selectbox("Select class",
                           [s.id for s in sections], key="sec")
        dfs = df[df["Section"] == sel].copy()
        subjs = dfs["Subject"].unique().tolist()
        clrs = px.colors.qualitative.Set2
        sc = {s: clrs[i % len(clrs)] for i, s in enumerate(subjs)}
        grid = {}
        for day in days:
            grid[day] = {}
            for p in range(1, 9):
                m = dfs[(dfs["Day"] == day) & (dfs["PerN"] == p)]
                grid[day][f"P{p}"] = (
                    f"{m.iloc[0]['Subject']} | "
                    f"{m.iloc[0]['Teacher']} | {m.iloc[0]['Room']}"
                    if not m.empty else "")
        gdf = pd.DataFrame(grid,
                           index=[f"P{p}" for p in range(1, 9)])
        def cc(v):
            if not v: return ""
            s = v.split(" | ")[0]
            return (f"background-color:{sc.get(s, '#888')};"
                    f"color:black;font-weight:500")
        st.dataframe(gdf.style.map(cc),
                     use_container_width=True, height=320)
        leg = st.columns(max(len(subjs), 1))
        for i, s in enumerate(subjs):
            leg[i].markdown(
                f"<span style='background:{sc[s]};padding:3px 10px;"
                f"border-radius:6px;color:black;font-size:11px'>{s}</span>",
                unsafe_allow_html=True)
        st.markdown("<br>", unsafe_allow_html=True)
        st.dataframe(
            dfs[["Day", "Period", "Subject", "Teacher", "Room"]]
            .reset_index(drop=True), use_container_width=True)

    with tab2:
        sel_t = st.selectbox("Select teacher",
                             [t.name for t in teachers], key="tch")
        dft = df[df["Teacher"] == sel_t].copy()
        st.markdown(f"**{sel_t}** — **{len(dft)} periods** this week")
        ppd = dft.groupby("Day").size().reset_index(name="Periods")
        fig_t = px.bar(ppd, x="Day", y="Periods",
                       title=f"{sel_t} — periods per day",
                       color="Periods", color_continuous_scale="Blues",
                       category_orders={"Day": days})
        fig_t.update_layout(plot_bgcolor=plot_bg,
                            paper_bgcolor=plot_bg, font_color=text)
        st.plotly_chart(fig_t, use_container_width=True)
        st.dataframe(
            dft[["Day", "Period", "Section", "Subject", "Room"]]
            .reset_index(drop=True), use_container_width=True)

    with tab3:
        total = 5 * 8
        ru = df.groupby("Room").size().reset_index(name="Used")
        ru["Free"] = total - ru["Used"]
        ru["Utilization %"] = (ru["Used"] / total * 100).round(1)
        fig_r = px.bar(ru, x="Room", y=["Used", "Free"],
                       title="Room utilization", barmode="stack",
                       color_discrete_map={"Used": accent,
                                           "Free": "#444444"})
        fig_r.update_layout(plot_bgcolor=plot_bg,
                            paper_bgcolor=plot_bg, font_color=text)
        st.plotly_chart(fig_r, use_container_width=True)
        st.dataframe(ru, use_container_width=True)

    with tab4:
        cl, cr = st.columns(2)
        with cl:
            sc2 = df.groupby("Subject").size().reset_index(name="Periods")
            fig_pie = px.pie(sc2, names="Subject", values="Periods",
                             title="Subject distribution",
                             color_discrete_sequence=
                             px.colors.qualitative.Set2)
            fig_pie.update_layout(paper_bgcolor=plot_bg, font_color=text)
            st.plotly_chart(fig_pie, use_container_width=True)
        with cr:
            tl = df.groupby("Teacher").size().reset_index(
                name="Total Periods")
            fig_bar = px.bar(tl, x="Teacher", y="Total Periods",
                             title="Teacher workload",
                             color="Total Periods",
                             color_continuous_scale="Teal")
            fig_bar.update_layout(plot_bgcolor=plot_bg,
                                  paper_bgcolor=plot_bg, font_color=text)
            st.plotly_chart(fig_bar, use_container_width=True)
        ss = df.groupby(["Section", "Subject"]).size().reset_index(
            name="Periods")
        fig_h = px.density_heatmap(
            ss, x="Subject", y="Section", z="Periods",
            title="Periods per subject per class",
            color_continuous_scale="Blues")
        fig_h.update_layout(plot_bgcolor=plot_bg,
                            paper_bgcolor=plot_bg, font_color=text)
        st.plotly_chart(fig_h, use_container_width=True)

    with tab5:
        for section in sections:
            ds = (df[df["Section"] == section.id]
                  [["Day", "Period", "Subject", "Teacher", "Room"]]
                  .reset_index(drop=True))
            st.download_button(
                label=f"📥 Download {section.id} (CSV)",
                data=ds.to_csv(index=False),
                file_name=f"timetable_{section.id}.csv",
                mime="text/csv", key=f"dl_{section.id}")
        st.download_button(
            label="📥 Download ALL classes (CSV)",
            data=df[["Section", "Day", "Period",
                      "Subject", "Teacher", "Room"]]
            .reset_index(drop=True).to_csv(index=False),
            file_name="timetable_all.csv",
            mime="text/csv", key="dl_all")