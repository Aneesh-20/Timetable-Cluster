from dataclasses import dataclass, field
from typing import List, Dict, Tuple


@dataclass
class Teacher:
    id: str
    name: str
    subjects: List[str]
    unavailable: List[Tuple[int, int]] = field(default_factory=list)


@dataclass
class Room:
    id: str
    name: str
    capacity: int
    is_lab: bool = False


@dataclass
class Section:
    id: str
    name: str
    strength: int
    subject_periods: Dict[str, int] = field(default_factory=dict)


@dataclass
class TimeSlot:
    day: int
    period: int

    def label(self):
        days = ["Mon", "Tue", "Wed", "Thu", "Fri"]
        return f"{days[self.day]} P{self.period + 1}"


@dataclass
class Constraint:
    type: str
    name: str
    weight: float = 1.0


@dataclass
class Assignment:
    section_id: str
    subject: str
    teacher_id: str
    room_id: str
    timeslot: TimeSlot