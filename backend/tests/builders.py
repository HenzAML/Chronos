"""Hand-built solver instances. No database."""

from app.solver.problem import Problem, Slot, SolverCourse, SolverInstructor, SolverRoom


def make_slots(spec):
    """spec: {day: [hours]} -> list of Slot with ids 1..n."""
    out = []
    for day in sorted(spec):
        for hour in spec[day]:
            out.append(Slot(id=len(out) + 1, day=day, hour=hour))
    return out


def inst(id, slots, name=None, prefer_morning=False, preferred_days=()):
    """slots: the Slot objects this instructor is available for."""
    return SolverInstructor(
        id=id, name=name or f"Dr. {id}", prefer_morning=prefer_morning,
        preferred_days=frozenset(preferred_days),
        available_slot_ids=frozenset(s.id for s in slots),
    )


def room(id, code=None, capacity=50, equipment=(), caps=("lecture",)):
    return SolverRoom(
        id=id, code=code or f"R{id}", capacity=capacity,
        equipment_ids=frozenset(equipment), capabilities=frozenset(caps),
    )


def course(id, code=None, instructor_id=1, students=30, duration=1, per_week=1,
           essential=(), preferred=(), session_type="lecture"):
    return SolverCourse(
        id=id, code=code or f"C{id}", name=f"Course {id}",
        instructor_id=instructor_id, expected_students=students,
        session_type=session_type, duration_hours=duration,
        essential_equipment_ids=frozenset(essential),
        preferred_equipment_ids=frozenset(preferred),
        classes_per_week=per_week,
    )


def problem(courses, rooms, slots, instructors, equipment_names=None):
    return Problem(
        courses=list(courses), instructors={i.id: i for i in instructors},
        rooms=list(rooms), slots=list(slots),
        equipment_names=equipment_names or {},
    )
