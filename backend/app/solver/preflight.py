"""Infeasibility diagnostics.

CP-SAT reports INFEASIBLE without saying why. Because H6 (essential equipment)
is a hard constraint, an ordinary data-entry mistake - a lab course whose kit no
room has - silently kills the whole run. This module finds the common causes
first and names the offending course, so the API can return something a
coordinator can act on.

It is a *necessary* conditions check, not a proof: passing does not guarantee
feasibility (room contention can still make an instance unsolvable), but any
failure here is definitely fatal.
"""

from dataclasses import dataclass
from typing import List

from app.solver.problem import Problem, Toggles


@dataclass
class Issue:
    code: str        # machine-readable reason
    course_code: str
    message: str     # human-readable, safe to show in the UI

    def __str__(self):
        return self.message


def _describe(problem: Problem, equipment_ids) -> str:
    names = sorted(problem.equipment_names.get(e, f"#{e}") for e in equipment_ids)
    return ", ".join(names)


def diagnose(problem: Problem, toggles: Toggles = Toggles()) -> List[Issue]:
    """Return every reason this instance cannot be solved. Empty list = looks OK."""
    issues: List[Issue] = []

    if not problem.rooms:
        issues.append(Issue("no_rooms", "-", "No rooms defined."))
    if not problem.slots:
        issues.append(Issue("no_slots", "-", "No time slots defined."))
    if not problem.courses:
        issues.append(Issue("no_courses", "-", "No courses to schedule."))
    if issues:
        return issues

    for c in problem.courses:
        if c.duration_hours != 1:
            issues.append(Issue(
                "multi_hour_unsupported", c.code,
                f"{c.code} has duration_hours={c.duration_hours}; the solver "
                f"currently schedules one-hour sessions only.",
            ))

        # Which rooms survive each hard filter, in isolation?
        by_capacity = [r for r in problem.rooms
                       if not toggles.h4_capacity or r.capacity >= c.expected_students]
        by_equipment = [r for r in problem.rooms
                        if not toggles.h6_essential_equipment
                        or c.essential_equipment_ids <= r.equipment_ids]
        both = [r for r in by_capacity if r in by_equipment]

        if not by_capacity:
            biggest = max(problem.rooms, key=lambda r: r.capacity)
            issues.append(Issue(
                "capacity", c.code,
                f"{c.code} expects {c.expected_students} students but the largest "
                f"room ({biggest.code}) seats {biggest.capacity}. (H4)",
            ))
        elif not by_equipment:
            # Name only the items genuinely unavailable, not the whole wish list.
            available = set().union(*(r.equipment_ids for r in problem.rooms))
            missing = c.essential_equipment_ids - available
            if missing:
                detail = (f"needs {_describe(problem, missing)}, which no room "
                          f"provides")
            else:
                detail = (f"needs {_describe(problem, c.essential_equipment_ids)} "
                          f"together, and no single room has that combination")
            issues.append(Issue("essential_equipment", c.code, f"{c.code} {detail}. (H6)"))
        elif not both:
            issues.append(Issue(
                "capacity_and_equipment", c.code,
                f"{c.code} needs {_describe(problem, c.essential_equipment_ids)} "
                f"and seating for {c.expected_students}. Rooms satisfy each "
                f"requirement separately, but none satisfies both. (H4 + H6)",
            ))

        # H5: does the instructor have any slot at all?
        inst = problem.instructors.get(c.instructor_id)
        if inst is None:
            issues.append(Issue("no_instructor", c.code,
                                f"{c.code} has no instructor assigned."))
        elif toggles.h5_availability and not inst.available_slot_ids:
            issues.append(Issue(
                "availability", c.code,
                f"{c.code} is taught by {inst.name}, who has no available "
                f"time slots. (H5)",
            ))

    # H1 + H3: an instructor cannot teach more courses than they have slots.
    if toggles.h5_availability and toggles.h3_instructor_conflict:
        load = {}
        for c in problem.courses:
            load[c.instructor_id] = load.get(c.instructor_id, 0) + 1
        for inst_id, n in load.items():
            inst = problem.instructors.get(inst_id)
            if inst and n > len(inst.available_slot_ids):
                issues.append(Issue(
                    "overloaded_instructor", "-",
                    f"{inst.name} teaches {n} courses but is available for only "
                    f"{len(inst.available_slot_ids)} slots. (H3 + H5)",
                ))

    return issues
