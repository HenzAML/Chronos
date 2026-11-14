"""Why a class was left out of the schedule.

Two kinds of reason:

  structural  the class has no possible placement at all (no room big enough,
              instructor has no window long enough, ...). Fatal whatever the
              other classes do.
  contention  placements exist, but in the schedule found each one is held by
              another class - in the room, or in the instructor's time.

Contention reasons describe what blocks the class in *this* schedule. They do
not prove which single change would fix it - that needs a what-if re-solve.
"""

from dataclasses import dataclass, field
from typing import Dict, List

from app.solver.problem import Problem, Slot, SolverCourse, Toggles

DAYS = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")
MAX_NAMED = 4       # blockers spelled out in a message; the rest are counted


@dataclass
class Unscheduled:
    course_id: int
    course_code: str
    course_name: str
    class_index: int
    code: str               # machine-readable reason
    message: str            # human-readable, safe to show in the UI
    blockers: List[dict] = field(default_factory=list)

    def as_dict(self) -> dict:
        return dict(self.__dict__)


def _when(day: int, hour: int, hours: int) -> str:
    return f"{DAYS[day]} {hour:02d}:00-{hour + hours:02d}:00"


def _names(problem: Problem, equipment_ids) -> str:
    return ", ".join(sorted(problem.equipment_names.get(e, f"#{e}") for e in equipment_ids))


def _label(c: SolverCourse, class_index: int) -> str:
    return c.code if c.classes_per_week == 1 else f"{c.code} class {class_index}"


def explain(problem: Problem, toggles: Toggles, course: SolverCourse, class_index: int,
            options, placements, proven_optimal: bool) -> Unscheduled:
    """options = (rooms, blocks) the class could use; placements = the schedule."""
    rooms, blocks = options
    if rooms and blocks:
        code, message, blockers = _contention(
            problem, toggles, course, class_index, rooms, blocks, placements, proven_optimal)
    else:
        code, message = _structural(problem, toggles, course, class_index, rooms)
        blockers = []
    return Unscheduled(
        course_id=course.id, course_code=course.code, course_name=course.name,
        class_index=class_index, code=code, message=message, blockers=blockers,
    )


def _structural(problem, toggles, c, class_index, rooms):
    who = _label(c, class_index)
    inst = problem.instructors.get(c.instructor_id)
    if inst is None:
        return "no_instructor", f"{who} has no instructor assigned."

    if not rooms:
        by_capacity = [r for r in problem.rooms
                       if not toggles.h4_capacity or r.capacity >= c.expected_students]
        by_equipment = [r for r in problem.rooms
                        if not toggles.h6_essential_equipment
                        or c.essential_equipment_ids <= r.equipment_ids]
        if not by_capacity:
            biggest = max(problem.rooms, key=lambda r: r.capacity)
            return "capacity", (
                f"{who} expects {c.expected_students} students but the largest room "
                f"({biggest.code}) seats {biggest.capacity}. Use a bigger room or "
                f"split the course into sections.")
        if not by_equipment:
            available = set().union(*(r.equipment_ids for r in problem.rooms))
            missing = c.essential_equipment_ids - available
            if missing:
                detail = f"needs {_names(problem, missing)}, which no room provides"
            else:
                detail = (f"needs {_names(problem, c.essential_equipment_ids)} together, "
                          f"and no single room has that combination")
            return "essential_equipment", (
                f"{who} {detail}. Add the equipment to a room or mark it as preferred.")
        return "capacity_and_equipment", (
            f"{who} needs {_names(problem, c.essential_equipment_ids)} and seating for "
            f"{c.expected_students}. Rooms satisfy each requirement separately, but "
            f"none satisfies both.")

    hours = c.duration_hours
    if not any(problem.block(s, hours) for s in problem.slots):
        return "no_block", (
            f"{who} needs {hours} consecutive hours, but no day in the timetable has "
            f"{hours} time slots in a row.")
    if not inst.available_slot_ids:
        return "availability", (
            f"{who} is taught by {inst.name}, who has no available time slots.")
    return "availability", (
        f"{who} needs {hours} consecutive hours, but {inst.name} is never available "
        f"for {hours} hours in a row. Widen their availability or shorten the class.")


def _contention(problem, toggles, c, class_index, rooms, blocks, placements, proven):
    who = _label(c, class_index)
    inst = problem.instructors[c.instructor_id]
    courses = {x.id: x for x in problem.courses}
    room_codes = {r.id: r.code for r in problem.rooms}
    slot_of = {s.id: s for s in problem.slots}

    # Who holds each room-hour and instructor-hour in the schedule found.
    room_busy: Dict[tuple, object] = {}
    inst_busy: Dict[tuple, object] = {}
    own_days = set()
    for p in placements:
        start = slot_of[p.slot_id]
        if p.course_id == c.id:
            own_days.add(start.day)
        for s in problem.block(start, p.duration_hours):
            room_busy[(p.room_id, s.id)] = p
            inst_busy[(courses[p.course_id].instructor_id, s.id)] = p

    hits: Dict[tuple, int] = {}     # (kind, placement identity) -> candidates blocked
    seen = {}
    free = False
    # Per block: is the *time* itself impossible (instructor busy / same day)?
    # If not, the block fails only because every room is held.
    time_kinds, room_only_blocks = set(), 0

    def others(busy, owner_id, block):
        # The course's own classes are covered by the different-day rule.
        return {id(p): p for s in block
                if (p := busy.get((owner_id, s.id))) is not None and p.course_id != c.id}

    def record(kind, found):
        for pid, p in found.items():
            seen[(kind, pid)] = p
            hits[(kind, pid)] = hits.get((kind, pid), 0) + 1

    for block in blocks:
        teaching = others(inst_busy, inst.id, block) if toggles.h3_instructor_conflict else {}
        same_day = block[0].day in own_days
        if same_day:
            time_kinds.add("same_course_day")
        if teaching:
            time_kinds.add("instructor")
            record("instructor", teaching)
        if same_day or teaching:
            continue
        room_only_blocks += 1
        for r in rooms:
            holding = others(room_busy, r.id, block) if toggles.h2_room_conflict else {}
            if holding:
                record("room", holding)
            else:
                free = True

    kinds = set(time_kinds)
    if room_only_blocks:
        kinds.add("room")

    blockers = []
    for (kind, pid), count in sorted(hits.items(), key=lambda kv: -kv[1]):
        p = seen[(kind, pid)]
        start = slot_of[p.slot_id]
        other = courses[p.course_id]
        blockers.append({
            "kind": kind, "course_id": other.id, "course_code": other.code,
            "class_index": p.class_index, "room_code": room_codes[p.room_id],
            "day": start.day, "hour": start.hour, "duration_hours": p.duration_hours,
            "blocks": count,
        })

    def listed(kind):
        mine = [b for b in blockers if b["kind"] == kind]
        text = ", ".join(
            f"{b['course_code']} ({b['room_code']}, "
            f"{_when(b['day'], b['hour'], b['duration_hours'])})"
            for b in mine[:MAX_NAMED])
        more = len(mine) - MAX_NAMED
        return text + (f" and {more} more" if more > 0 else "")

    need = f"a {c.duration_hours}-hour block" if c.duration_hours > 1 else "one hour"
    room_list = ", ".join(r.code for r in rooms[:MAX_NAMED]) + (
        f" and {len(rooms) - MAX_NAMED} more" if len(rooms) > MAX_NAMED else "")
    fits = f"{len(rooms)} room{'s' if len(rooms) != 1 else ''} fit{'s' if len(rooms) == 1 else ''} ({room_list})"

    if free and not proven:
        return "time_limit", (
            f"{who} still has a free room and time, but the solver ran out of time "
            f"before placing it. Raise the solver time limit and generate again."
        ), blockers

    if kinds == {"same_course_day"}:
        return "same_course_day", (
            f"{who} must be on a different day from the course's other class, and "
            f"{inst.name} has no free time for it on another day. Widen their "
            f"availability to a second day."), blockers
    if kinds == {"room"}:
        return "room_contention", (
            f"{who} needs {need} for {c.expected_students} students. {fits}, but "
            f"whenever {inst.name} is available they are taken by: {listed('room')}. "
            f"Free one of these rooms, add a suitable room, or widen "
            f"{inst.name}'s availability."), blockers
    if kinds == {"instructor"}:
        return "instructor_contention", (
            f"{who} needs {need}, but {inst.name} is already teaching in every window "
            f"that fits: {listed('instructor')}. Widen their availability or assign "
            f"another instructor."), blockers

    parts = []
    if "room" in kinds:
        parts.append(f"the rooms are taken by {listed('room')}")
    if "instructor" in kinds:
        parts.append(f"{inst.name} is teaching {listed('instructor')}")
    if "same_course_day" in kinds:
        parts.append("the course's other class is already on that day")
    return "contention", (
        f"{who} needs {need} for {c.expected_students} students. {fits}, but in "
        f"every window {inst.name} could teach it, " + "; or ".join(parts) + "."
    ), blockers
