import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st
import pandas as pd
from src.sample_data import get_sample_school
from src.solver import TimetableSolver
from src.constraints import check_hard_constraints

st.set_page_config(page_title="Timetable Optimizer", layout="wide")
st.title("Intelligent Timetable Optimizer")
st.caption("Automatic conflict-free school timetable generator")

teachers, rooms, sections, constraints = get_sample_school()

if "timetable" not in st.session_state:
    st.session_state.timetable = None
    st.session_state.violations = []

if st.button("Generate Timetable", type="primary"):
    with st.spinner("Building timetable..."):
        solver = TimetableSolver(teachers, rooms, sections)
        solver.create_variables()
        solver.add_coverage_constraint()
        solver.add_section_no_clash()
        solver.add_teacher_no_clash()
        solver.add_room_no_clash()
        st.session_state.timetable = solver.solve()
        st.session_state.violations = check_hard_constraints(
            st.session_state.timetable, teachers, rooms)

if st.session_state.timetable:
    timetable = st.session_state.timetable
    violations = st.session_state.violations

    col1, col2, col3 = st.columns(3)
    col1.metric("Total Assignments", len(timetable))
    col2.metric("Hard Violations", len(violations))
    col3.metric("Sections Scheduled", len(sections))

    if len(violations) == 0:
        st.success("PERFECT timetable — zero conflicts!")
    else:
        st.error(f"{len(violations)} conflicts found")
        for v in violations:
            st.write(f"- {v}")

    days = ["Monday","Tuesday","Wednesday","Thursday","Friday"]
    selected = st.selectbox("Select class to view",
                            [s.id for s in sections])

    rows = []
    for a in timetable:
        if a.section_id == selected:
            teacher = next(t for t in teachers
                           if t.id == a.teacher_id)
            rows.append({
                "Day": days[a.timeslot.day],
                "Period": f"P{a.timeslot.period+1}",
                "Subject": a.subject,
                "Teacher": teacher.name,
                "Room": a.room_id
            })

    if rows:
        df = pd.DataFrame(rows).sort_values(["Day","Period"])
        st.dataframe(df.reset_index(drop=True),
                     use_container_width=True)
        st.download_button(
            "Download CSV",
            df.to_csv(index=False),
            f"timetable_{selected}.csv",
            "text/csv"
        )