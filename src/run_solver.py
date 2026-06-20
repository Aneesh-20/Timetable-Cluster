import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.sample_data import get_sample_school
from src.solver import TimetableSolver
from src.constraints import check_hard_constraints

teachers, rooms, sections, constraints = get_sample_school()

solver = TimetableSolver(teachers, rooms, sections)
solver.create_variables()

solver.add_coverage_constraint()
solver.add_section_no_clash()
solver.add_teacher_no_clash()
solver.add_room_no_clash()

timetable = solver.solve(time_limit=30)

if timetable:
    solver.print_timetable(timetable)
    print("\n=== Verifying ===")
    violations = check_hard_constraints(timetable, teachers, rooms)
    if violations:
        for v in violations:
            print(f"  ! {v}")
    else:
        print("PERFECT: Zero hard constraint violations!")
else:
    print("No solution found.")