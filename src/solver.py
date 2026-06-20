from src.models import TimeSlot, Assignment
import random


class TimetableSolver:

    def __init__(self, teachers, rooms, sections):
        self.teachers = teachers
        self.rooms = rooms
        self.sections = sections
        self.teacher_map = {t.id: t for t in teachers}
        self.room_map = {r.id: r for r in rooms}
        print(f"Solver ready: {len(teachers)} teachers, {len(rooms)} rooms")

    def create_variables(self):
        print("Variables ready (custom solver)")

    def add_coverage_constraint(self):
        print("Rule 1 noted: coverage")

    def add_section_no_clash(self):
        print("Rule 2 noted: section no clash")

    def add_teacher_no_clash(self):
        print("Rule 3 noted: teacher no clash")

    def add_room_no_clash(self):
        print("Rule 4 noted: room no clash")

    def solve(self, time_limit=30):
        print("Building timetable using greedy assignment...")

        all_slots = [
            (day, period)
            for day in range(5)
            for period in range(8)
        ]

        timetable = []
        used_teacher_slots = set()
        used_section_slots = set()
        used_room_slots = set()

        for section in self.sections:
            for subject, count in section.subject_periods.items():

                eligible = [t for t in self.teachers
                            if subject in t.subjects]

                if not eligible:
                    print(f"WARNING: No teacher for {subject}!")
                    continue

                assigned = 0
                random.shuffle(all_slots)

                for day, period in all_slots:
                    if assigned >= count:
                        break

                    for teacher in eligible:
                        if (teacher.id, day, period) in used_teacher_slots:
                            continue
                        if (section.id, day, period) in used_section_slots:
                            continue

                        for room in self.rooms:
                            if (room.id, day, period) in used_room_slots:
                                continue

                            timetable.append(Assignment(
                                section_id=section.id,
                                subject=subject,
                                teacher_id=teacher.id,
                                room_id=room.id,
                                timeslot=TimeSlot(day=day, period=period)
                            ))
                            used_teacher_slots.add((teacher.id, day, period))
                            used_section_slots.add((section.id, day, period))
                            used_room_slots.add((room.id, day, period))
                            assigned += 1
                            break
                        if assigned >= count:
                            break

                if assigned < count:
                    print(f"WARNING: Only assigned {assigned}/{count} "
                          f"periods for {subject} in {section.id}")
                else:
                    print(f"OK: {section.id} {subject} = {assigned} periods")

        print(f"\nTimetable built: {len(timetable)} assignments")
        return timetable

    def print_timetable(self, timetable):
        days = ["Mon", "Tue", "Wed", "Thu", "Fri"]
        for section in self.sections:
            print(f"\n{'='*45}")
            print(f"  TIMETABLE: {section.name}")
            print(f"{'='*45}")
            for day_idx, day_name in enumerate(days):
                slots = sorted(
                    [a for a in timetable
                     if a.section_id == section.id
                     and a.timeslot.day == day_idx],
                    key=lambda x: x.timeslot.period
                )
                if slots:
                    print(f"\n  {day_name}:")
                    for a in slots:
                        teacher = self.teacher_map[a.teacher_id]
                        print(f"    P{a.timeslot.period+1}: "
                              f"{a.subject:<15} "
                              f"{teacher.name:<15} "
                              f"{a.room_id}")
