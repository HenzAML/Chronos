"""Verified fixes for classes left out of a schedule.

For each unplaced class: pick a few single changes that fit its reason, apply
each to a copy of the problem, solve again, and keep the change only if the
class is placed and more classes are placed in total than before - a change
that places it by dropping another class is not a fix.
"""

from dataclasses import replace
from typing import List

from app.solver.cpsat import SolveResult, solve
from app.solver.explain import Unscheduled, _names
from app.solver.problem import Problem, SolverCourse, SolverRoom, Toggles, Weights

MAX_CANDIDATES = 4      # re-solves per class
TIME_LIMIT_SECONDS = 3  # per re-solve; a solve cut short only hides a fix, never invents one

NO_ROOM = ("capacity", "essential_equipment", "capacity_and_equipment")
ROOMS_HELD = ("room_contention", "contention")
WIDEN = ("availability", "instructor_contention", "same_course_day") + ROOMS_HELD
SHORTEN = ("no_block", "availability", "instructor_contention") + ROOMS_HELD


def find_fixes(problem: Problem, previous: SolveResult, weights: Weights = Weights(),
               toggles: Toggles = Toggles()) -> List[dict]:
    """One entry per verified fix; a class with none gets one entry of kind "none"."""
    before = len(previous.placements)
    courses = {c.id: c for c in problem.courses}
    placed_after = {}       # (kind, what changed) -> classes placed; classes can share a change
    out = []
    for u in previous.unscheduled:
        entry = {"course_id": u.course_id, "course_code": u.course_code,
                 "class_index": u.class_index}
        c = courses.get(u.course_id)    # None if the course was deleted since the schedule
        found = False
        for kind, target, message, changed in (_candidates(problem, c, u) if c else []):
            if (kind, target) not in placed_after:
                placed_after[(kind, target)] = {
                    (p.course_id, p.class_index) for p in solve(
                        changed, weights, toggles,
                        time_limit_seconds=TIME_LIMIT_SECONDS).placements}
            placed = placed_after[(kind, target)]
            if (u.course_id, u.class_index) in placed and len(placed) > before:
                found = True
                out.append({**entry, "kind": kind, "message": message, "placed": len(placed)})
        if not found:
            out.append({**entry, "kind": "none", "message": "No single change fixes this",
                        "placed": before})
    return out


def _candidates(problem: Problem, c: SolverCourse, u: Unscheduled) -> list:
    """(kind, id of the thing changed, message, changed copy of the problem)."""
    out = []

    def add_room(kind, target, message, room):
        new_id = max(r.id for r in problem.rooms) + 1
        out.append((kind, target, message,
                    replace(problem, rooms=problem.rooms + [replace(room, id=new_id)])))

    if u.code in NO_ROOM:
        message = f"Add a room with at least {c.expected_students} seats"
        if c.essential_equipment_ids:
            message += f" and {_names(problem, c.essential_equipment_ids)}"
        add_room("new_room", c.id, message, SolverRoom(
            id=0, code="NEW", capacity=c.expected_students,
            equipment_ids=c.essential_equipment_ids,
            capabilities=frozenset({c.session_type})))

    if u.code in ROOMS_HELD:
        # Blockers come sorted by how many placements they block: try the top two rooms.
        held = dict.fromkeys(b["room_code"] for b in u.blockers if b["kind"] == "room")
        for r in [r for code in held for r in problem.rooms if r.code == code][:2]:
            detail = ", ".join(filter(None, [f"{r.capacity} seats",
                                             _names(problem, r.equipment_ids)]))
            add_room("room_like", r.id, f"Add a room like {r.code} ({detail})",
                     replace(r, code=f"{r.code} (2)"))

    inst = problem.instructors.get(c.instructor_id)
    every_slot = frozenset(s.id for s in problem.slots)
    if u.code in WIDEN and inst and inst.available_slot_ids != every_slot:
        out.append(("widen_availability", inst.id,
                    f"Make {inst.name} available on more slots",
                    replace(problem, instructors={
                        **problem.instructors,
                        inst.id: replace(inst, available_slot_ids=every_slot)})))

    if u.code in SHORTEN and c.duration_hours > 1:
        hours = c.duration_hours - 1
        out.append(("shorten", c.id,
                    f"Shorten {c.code} from {c.duration_hours} to {hours} "
                    f"hour{'s' if hours != 1 else ''}",
                    replace(problem, courses=[
                        replace(x, duration_hours=hours) if x.id == c.id else x
                        for x in problem.courses])))

    return out[:MAX_CANDIDATES]
