from typing import List
from src.models import Assignment, Teacher, Room


def check_hard_constraints(assignments, teachers, rooms):
    violations = []
    for i, a1 in enumerate(assignments):
        for a2 in assignments[i+1:]:
            same_slot = (a1.timeslot.day == a2.timeslot.day and
                         a1.timeslot.period == a2.timeslot.period)
            if same_slot:
                if a1.teacher_id == a2.teacher_id:
                    violations.append(
                        f"CLASH: Teacher {a1.teacher_id} double-booked "
                        f"at Day{a1.timeslot.day} P{a1.timeslot.period+1}"
                    )
                if a1.section_id == a2.section_id:
                    violations.append(
                        f"CLASH: Section {a1.section_id} double-booked "
                        f"at Day{a1.timeslot.day} P{a1.timeslot.period+1}"
                    )
                if a1.room_id == a2.room_id:
                    violations.append(
                        f"CLASH: Room {a1.room_id} double-booked "
                        f"at Day{a1.timeslot.day} P{a1.timeslot.period+1}"
                    )
    return violations


def score_soft_constraints(assignments, teachers):
    from collections import defaultdict
    penalty = 0.0
    teacher_day = defaultdict(int)
    for a in assignments:
        teacher_day[(a.teacher_id, a.timeslot.day)] += 1
    for count in teacher_day.values():
        if count > 4:
            penalty += (count - 4) * 2.0
    return penalty
