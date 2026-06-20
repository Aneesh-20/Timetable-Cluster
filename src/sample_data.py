from src.models import Teacher, Room, Section, Constraint

def get_sample_school():
    teachers = [
        Teacher(id="T001", name="Mr. Kumar", subjects=["Math"], unavailable=[]),
        Teacher(id="T002", name="Ms. Priya", subjects=["English"], unavailable=[]),
        Teacher(id="T003", name="Mr. Rajan", subjects=["Science"], unavailable=[]),
        Teacher(id="T004", name="Ms. Deepa", subjects=["Computer Science"], unavailable=[]),
        Teacher(id="T005", name="Mr. Arjun", subjects=["History", "Geography"], unavailable=[]),
    ]
    rooms = [
        Room(id="R101", name="Room 101", capacity=40),
        Room(id="R102", name="Room 102", capacity=40),
        Room(id="R103", name="Room 103", capacity=35),
    ]
    sections = [
        Section(id="10A", name="Class 10 A", strength=35,
            subject_periods={"Math":5,"English":5,"Science":4,"History":3,"Geography":3}),
        Section(id="10B", name="Class 10 B", strength=33,
            subject_periods={"Math":5,"English":5,"Science":4,"History":3,"Geography":3}),
        Section(id="11A", name="Class 11 A", strength=30,
            subject_periods={"Math":5,"English":4,"Science":4,"Computer Science":4,"History":3}),
    ]
    constraints = [
        Constraint(type="hard", name="No teacher clash"),
        Constraint(type="hard", name="No room clash"),
    ]
    return teachers, rooms, sections, constraints
