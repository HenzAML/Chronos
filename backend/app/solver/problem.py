"""Plain-data view of a timetabling instance.

The solver deliberately does not touch SQLAlchemy objects. Loading happens once,
up front, into these dataclasses - which keeps the CP-SAT code free of lazy-load
surprises and lets the solver be unit-tested against hand-built instances.
"""

from dataclasses import dataclass, field
from typing import Dict, FrozenSet, List, Sequence, Tuple

from app.models import (
    ConstraintConfig,
    Course,
    Instructor,
    Room,
    TimeSlot,
)


@dataclass(frozen=True)
class Slot:
    id: int
    day: int
    hour: int

    @property
    def label(self):
        return f"{('Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun')[self.day]} {self.hour:02d}:00"


@dataclass(frozen=True)
class SolverInstructor:
    id: int
    name: str
    prefer_morning: bool
    preferred_days: FrozenSet[int]
    available_slot_ids: FrozenSet[int]


@dataclass(frozen=True)
class SolverRoom:
    id: int
    code: str
    capacity: int
    equipment_ids: FrozenSet[int]
    capabilities: FrozenSet[str]

    def supports(self, session_type: str) -> bool:
        return session_type in self.capabilities


@dataclass(frozen=True)
class SolverCourse:
    id: int
    code: str
    name: str
    instructor_id: int
    expected_students: int
    session_type: str
    duration_hours: int
    essential_equipment_ids: FrozenSet[int]
    preferred_equipment_ids: FrozenSet[int]


@dataclass(frozen=True)
class Weights:
    """Soft-constraint weights (see CHRONOS_CONTEXT.md)."""

    w1_morning: int = 10        # S1 - class after 12:00 vs morning preference
    w2_preferred_day: int = 5   # S2 - class on a non-preferred day
    w3_equipment: int = 3       # S3 - per missing *preferred* equipment item
    w4_room_type: int = 4       # S4 - room does not support the session type

    @classmethod
    def from_config(cls, cfg: ConstraintConfig) -> "Weights":
        return cls(
            w1_morning=cfg.w1_morning,
            w2_preferred_day=cfg.w2_preferred_day,
            w3_equipment=cfg.w3_equipment,
            w4_room_type=cfg.w4_room_type,
        )


@dataclass(frozen=True)
class Toggles:
    """Hard-constraint switches. H1 is structural and cannot be disabled."""

    h2_room_conflict: bool = True
    h3_instructor_conflict: bool = True
    h4_capacity: bool = True
    h5_availability: bool = True
    h6_essential_equipment: bool = True

    @classmethod
    def from_config(cls, cfg: ConstraintConfig) -> "Toggles":
        return cls(
            h2_room_conflict=cfg.enable_h2_room_conflict,
            h3_instructor_conflict=cfg.enable_h3_instructor_conflict,
            h4_capacity=cfg.enable_h4_capacity,
            h5_availability=cfg.enable_h5_availability,
            h6_essential_equipment=cfg.enable_h6_essential_equipment,
        )


@dataclass
class Problem:
    courses: List[SolverCourse]
    instructors: Dict[int, SolverInstructor]
    rooms: List[SolverRoom]
    slots: List[Slot]
    equipment_names: Dict[int, str] = field(default_factory=dict)

    def instructor_of(self, course: SolverCourse) -> SolverInstructor:
        return self.instructors[course.instructor_id]

    @property
    def size(self) -> Tuple[int, int, int, int]:
        return len(self.courses), len(self.instructors), len(self.rooms), len(self.slots)


_CAPABILITY_FIELDS = {
    "lecture": "supports_lecture",
    "lab": "supports_lab",
    "group": "supports_group",
    "seminar": "supports_seminar",
    "meeting": "supports_meeting",
}


def load_problem(session) -> Problem:
    """Read the whole instance out of the database in a handful of queries."""
    slots = [
        Slot(id=s.id, day=s.day, hour=s.hour)
        for s in session.query(TimeSlot).order_by(TimeSlot.day, TimeSlot.hour).all()
    ]

    instructors = {}
    for i in session.query(Instructor).all():
        instructors[i.id] = SolverInstructor(
            id=i.id,
            name=i.name,
            prefer_morning=i.prefer_morning,
            preferred_days=frozenset(i.preferred_days or ()),
            available_slot_ids=frozenset(i.available_slot_ids),
        )

    rooms = []
    for r in session.query(Room).order_by(Room.code).all():
        caps = {name for name, attr in _CAPABILITY_FIELDS.items() if getattr(r, attr)}
        rooms.append(SolverRoom(
            id=r.id, code=r.code, capacity=r.capacity,
            equipment_ids=frozenset(r.equipment_ids),
            capabilities=frozenset(caps),
        ))

    courses = []
    for c in session.query(Course).order_by(Course.code).all():
        courses.append(SolverCourse(
            id=c.id, code=c.code, name=c.name,
            instructor_id=c.instructor_id,
            expected_students=c.expected_students,
            session_type=c.session_type,
            duration_hours=c.duration_hours,
            essential_equipment_ids=frozenset(c.essential_equipment_ids),
            preferred_equipment_ids=frozenset(c.preferred_equipment_ids),
        ))

    from app.models import Equipment
    equipment_names = {e.id: e.name for e in session.query(Equipment).all()}

    return Problem(
        courses=courses, instructors=instructors, rooms=rooms,
        slots=slots, equipment_names=equipment_names,
    )
