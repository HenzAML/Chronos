"""CP-SAT timetabling model.

A course meets `classes_per_week` times; each class is one continuous block of
`duration_hours` in one room on one day.

Decision variable
    x[class, r, t] in {0, 1}   the class starts in room r at slot t

Hard
    H1  sum_r sum_t x[class,r,t] <= 1                each class placed at most once
    H2  per room and hour, at most one covering block
    H3  per instructor and hour, at most one covering block
    H4  capacity(r) >= students(c)                   enforced by pruning
    H5  instructor available for the whole block     enforced by pruning
    H6  essential(c) subset-of equipment(r)          enforced by pruning
    --  classes of one course fall on different days

H1 is "at most once", not "exactly once": the solver never answers INFEASIBLE.
Classes that cannot fit are left out and explained (see explain.py).

Objective (one solve)
    maximise sum (BIG - penalty) * x
BIG exceeds the sum of every class's worst penalty, so placing one more class
always beats any preference gain. Among schedules placing the same number of
classes the lowest soft score wins.

    penalty = w1*S1(c,t) + w2*S2(c,t) + w3*S3(c,r) + w4*S4(c,r)
"""

import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from ortools.sat.python import cp_model

from app.solver.explain import Unscheduled, explain
from app.solver.problem import Problem, Slot, SolverCourse, SolverRoom, Toggles, Weights

MORNING_END_HOUR = 12


@dataclass
class Placement:
    course_id: int
    class_index: int        # 1-based
    room_id: int
    slot_id: int            # start of the block
    duration_hours: int
    penalty: int


@dataclass
class SolveResult:
    status: str                     # optimal | feasible | partial | failed
    placements: List[Placement] = field(default_factory=list)
    unscheduled: List[Unscheduled] = field(default_factory=list)
    class_count: int = 0
    soft_score: Optional[int] = None
    optimality_gap: Optional[float] = None
    solve_seconds: float = 0.0
    message: Optional[str] = None
    # Diagnostics for the report.
    num_variables: int = 0
    pruned_triples: int = 0
    penalty_breakdown: Dict[str, int] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return self.status != "failed"


def _time_penalty(problem: Problem, c: SolverCourse, block: List[Slot]) -> Tuple[int, int]:
    """(S1, S2) for a class in this block. S1 is charged once per class if any
    hour of the block is at noon or later."""
    inst = problem.instructor_of(c)
    s1 = 1 if (inst.prefer_morning and block[-1].hour >= MORNING_END_HOUR) else 0
    s2 = 1 if (inst.preferred_days and block[0].day not in inst.preferred_days) else 0
    return s1, s2


def _room_penalty(c: SolverCourse, room: SolverRoom) -> Tuple[int, int]:
    """(S3, S4): missing preferred items (counted), unsuitable room type."""
    s3 = len(c.preferred_equipment_ids - room.equipment_ids)
    s4 = 0 if room.supports(c.session_type) else 1
    return s3, s4


def solve(
    problem: Problem,
    weights: Weights = Weights(),
    toggles: Toggles = Toggles(),
    time_limit_seconds: int = 30,
    num_workers: int = 8,
) -> SolveResult:
    for missing, what in ((problem.courses, "courses"), (problem.rooms, "rooms"),
                          (problem.slots, "time slots")):
        if not missing:
            return SolveResult(status="failed",
                               message=f"Nothing to schedule: no {what} defined.")

    model = cp_model.CpModel()
    courses = {c.id: c for c in problem.courses}

    # ---- variables, with H4/H5/H6 applied as pruning --------------------
    # key = (course_id, class_index, room_id, start_slot_id)
    x: Dict[Tuple[int, int, int, int], cp_model.IntVar] = {}
    penalties: Dict[Tuple[int, int, int, int], int] = {}
    blocks: Dict[Tuple[int, int], List[Slot]] = {}      # (course_id, start) -> slots
    options = {}                                        # course_id -> (rooms, blocks)
    class_count = 0
    total = 0

    for c in problem.courses:
        rooms = problem.rooms_for(c, toggles)
        course_blocks = problem.blocks_for(c, toggles)
        options[c.id] = (rooms, course_blocks)
        class_count += c.classes_per_week
        total += c.classes_per_week * len(problem.rooms) * len(problem.slots)
        for block in course_blocks:
            blocks[(c.id, block[0].id)] = block
            s1, s2 = _time_penalty(problem, c, block)
            time_cost = weights.w1_morning * s1 + weights.w2_preferred_day * s2
            for r in rooms:
                s3, s4 = _room_penalty(c, r)
                cost = time_cost + weights.w3_equipment * s3 + weights.w4_room_type * s4
                for k in range(1, c.classes_per_week + 1):
                    key = (c.id, k, r.id, block[0].id)
                    x[key] = model.NewBoolVar(f"x_{c.code}_{k}_{r.code}_{block[0].id}")
                    penalties[key] = cost

    by_class: Dict[Tuple[int, int], list] = {}
    by_room_slot: Dict[Tuple[int, int], list] = {}
    by_instructor_slot: Dict[Tuple[int, int], list] = {}
    by_course_day: Dict[Tuple[int, int], list] = {}
    for (cid, k, rid, tid), var in x.items():
        by_class.setdefault((cid, k), []).append(var)
        block = blocks[(cid, tid)]
        by_course_day.setdefault((cid, block[0].day), []).append(var)
        for s in block:
            by_room_slot.setdefault((rid, s.id), []).append(var)
            by_instructor_slot.setdefault((courses[cid].instructor_id, s.id), []).append(var)

    def at_most_one(groups):
        for group in groups.values():
            if len(group) > 1:
                model.AddAtMostOne(group)

    at_most_one(by_class)                                # H1 (relaxed)
    if toggles.h2_room_conflict:
        at_most_one(by_room_slot)                        # H2
    if toggles.h3_instructor_conflict:
        at_most_one(by_instructor_slot)                  # H3
    at_most_one({k: v for k, v in by_course_day.items()
                 if courses[k[0]].classes_per_week > 1})  # different days

    # ---- objective: most classes first, then preferences ----------------
    worst: Dict[Tuple[int, int], int] = {}
    for (cid, k, _, _), p in penalties.items():
        worst[(cid, k)] = max(worst.get((cid, k), 0), p)
    big = sum(worst.values()) + 1
    model.Maximize(cp_model.LinearExpr.WeightedSum(
        list(x.values()), [big - penalties[key] for key in x]))

    # ---- solve ----------------------------------------------------------
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = float(time_limit_seconds)
    solver.parameters.num_search_workers = num_workers

    start = time.perf_counter()
    status = solver.Solve(model) if x else cp_model.OPTIMAL
    elapsed = time.perf_counter() - start

    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return SolveResult(
            status="failed", class_count=class_count, solve_seconds=elapsed,
            num_variables=len(x), pruned_triples=total - len(x),
            message=f"Solver stopped without a schedule (status={solver.StatusName(status)}). "
                    f"Try a longer time limit.",
        )

    chosen = [key for key, var in x.items() if solver.Value(var) == 1]
    placements = _number_classes(chosen, blocks, penalties, courses)

    proven = status == cp_model.OPTIMAL
    placed_count: Dict[int, int] = {}
    for p in placements:
        placed_count[p.course_id] = placed_count.get(p.course_id, 0) + 1
    unscheduled = [
        explain(problem, toggles, c, k, options[c.id], placements, proven)
        for c in problem.courses
        for k in range(placed_count.get(c.id, 0) + 1, c.classes_per_week + 1)
    ]

    if unscheduled:
        result_status = "partial"
    else:
        result_status = "optimal" if proven else "feasible"

    return SolveResult(
        status=result_status,
        placements=placements,
        unscheduled=unscheduled,
        class_count=class_count,
        soft_score=sum(p.penalty for p in placements),
        optimality_gap=0.0 if proven else _gap(solver),
        solve_seconds=elapsed,
        num_variables=len(x),
        pruned_triples=total - len(x),
        penalty_breakdown=_breakdown(problem, placements, weights),
        message=(f"{len(unscheduled)} of {class_count} classes could not be scheduled."
                 if unscheduled else None),
    )


def _number_classes(chosen, blocks, penalties, courses) -> List[Placement]:
    """Classes of a course are interchangeable in the model, so number the placed
    ones 1..n in week order. Unplaced classes then take the numbers after."""
    per_course: Dict[int, list] = {}
    for key in chosen:
        per_course.setdefault(key[0], []).append(key)
    out = []
    for cid, keys in per_course.items():
        keys.sort(key=lambda k: (blocks[(cid, k[3])][0].day, blocks[(cid, k[3])][0].hour))
        for index, key in enumerate(keys, start=1):
            out.append(Placement(
                course_id=cid, class_index=index, room_id=key[2], slot_id=key[3],
                duration_hours=courses[cid].duration_hours, penalty=penalties[key],
            ))
    out.sort(key=lambda p: (p.slot_id, p.room_id))
    return out


def _gap(solver: cp_model.CpSolver) -> Optional[float]:
    """Relative gap between the schedule found and the best proven bound, on the
    combined objective. 0.0 means provably optimal."""
    z, bound = solver.ObjectiveValue(), solver.BestObjectiveBound()
    return abs(bound - z) / abs(z) if z else None


def _breakdown(problem: Problem, placements: List[Placement], w: Weights) -> Dict[str, int]:
    """Split the soft score into per-term contributions, for the UI and the report."""
    slots = {s.id: s for s in problem.slots}
    rooms = {r.id: r for r in problem.rooms}
    courses = {c.id: c for c in problem.courses}

    out = {"S1_morning": 0, "S2_preferred_day": 0, "S3_equipment": 0, "S4_room_type": 0}
    # Raw violation counts, independent of weight. Without these a zero weight
    # reads identically to zero violations, which is misleading in the UI.
    raw = dict(out)
    for p in placements:
        c, r = courses[p.course_id], rooms[p.room_id]
        s1, s2 = _time_penalty(problem, c, problem.block(slots[p.slot_id], p.duration_hours))
        s3, s4 = _room_penalty(c, r)
        out["S1_morning"] += w.w1_morning * s1
        out["S2_preferred_day"] += w.w2_preferred_day * s2
        out["S3_equipment"] += w.w3_equipment * s3
        out["S4_room_type"] += w.w4_room_type * s4
        raw["S1_morning"] += s1
        raw["S2_preferred_day"] += s2
        raw["S3_equipment"] += s3
        raw["S4_room_type"] += s4
    out.update({f"{k}_count": v for k, v in raw.items()})
    return out
