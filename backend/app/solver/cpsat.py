"""CP-SAT timetabling model.

Ported from docs/research/experiments/experiment_instructor_constraints.py,
extended with H6 (essential equipment), S3 (preferred equipment) and S4 (room
suitability), and made configurable via Weights/Toggles.

Decision variable
    x[c, r, t] in {0, 1}   course c in room r at slot t

Hard
    H1  sum_r sum_t x[c,r,t] == 1                    every course placed once
    H2  sum_c x[c,r,t] <= 1                          no room double-booked
    H3  sum_{c of i} sum_r x[c,r,t] <= 1             no instructor double-booked
    H4  capacity(r) >= students(c)                   enforced by pruning
    H5  t in availability(instructor(c))             enforced by pruning
    H6  essential(c) subset-of equipment(r)          enforced by pruning

H4/H5/H6 filter which x variables get created at all, rather than adding
constraints over variables that can never be 1. That shrinks the model
substantially - on the 80-course instance it removes ~85% of candidate triples.

Soft (minimised)
    Z = sum over created x[c,r,t] of
        w1*S1(c,t) + w2*S2(c,t) + w3*S3(c,r) + w4*S4(c,r)
"""

import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from ortools.sat.python import cp_model

from app.solver.problem import Problem, Slot, SolverCourse, SolverRoom, Toggles, Weights

MORNING_END_HOUR = 12


@dataclass
class Placement:
    course_id: int
    room_id: int
    slot_id: int
    penalty: int


@dataclass
class SolveResult:
    status: str                     # optimal | feasible | infeasible | failed
    placements: List[Placement] = field(default_factory=list)
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
        return self.status in ("optimal", "feasible")


def _time_penalty(problem: Problem, c: SolverCourse, slot: Slot, w: Weights) -> Tuple[int, int]:
    """(S1, S2) raw indicator values for a (course, slot) pair."""
    inst = problem.instructor_of(c)
    s1 = 1 if (inst.prefer_morning and slot.hour >= MORNING_END_HOUR) else 0
    s2 = 1 if (inst.preferred_days and slot.day not in inst.preferred_days) else 0
    return s1, s2


def _room_penalty(c: SolverCourse, room: SolverRoom) -> Tuple[int, int]:
    """(S3, S4) raw values for a (course, room) pair.

    S3 counts *how many* preferred items are missing, so a room missing three
    nice-to-haves is scored worse than one missing a single item.
    """
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
    model = cp_model.CpModel()

    # ---- variables, with H4/H5/H6 applied as pruning --------------------
    x: Dict[Tuple[int, int, int], cp_model.IntVar] = {}
    penalties: Dict[Tuple[int, int, int], int] = {}
    total_triples = len(problem.courses) * len(problem.rooms) * len(problem.slots)

    for c in problem.courses:
        inst = problem.instructor_of(c)
        for r in problem.rooms:
            if toggles.h4_capacity and r.capacity < c.expected_students:
                continue                                          # H4
            if toggles.h6_essential_equipment and not c.essential_equipment_ids <= r.equipment_ids:
                continue                                          # H6
            s3, s4 = _room_penalty(c, r)
            room_cost = weights.w3_equipment * s3 + weights.w4_room_type * s4
            for t in problem.slots:
                if toggles.h5_availability and t.id not in inst.available_slot_ids:
                    continue                                      # H5
                key = (c.id, r.id, t.id)
                x[key] = model.NewBoolVar(f"x_{c.code}_{r.code}_{t.day}_{t.hour}")
                s1, s2 = _time_penalty(problem, c, t, weights)
                penalties[key] = (
                    weights.w1_morning * s1
                    + weights.w2_preferred_day * s2
                    + room_cost
                )

    if not x:
        return SolveResult(
            status="infeasible",
            message="No feasible (course, room, slot) combination exists under the "
                    "current hard constraints.",
            pruned_triples=total_triples,
        )

    # Index the variables for constraint building.
    by_course: Dict[int, list] = {}
    by_room_slot: Dict[Tuple[int, int], list] = {}
    by_instructor_slot: Dict[Tuple[int, int], list] = {}
    for (cid, rid, tid), var in x.items():
        by_course.setdefault(cid, []).append(var)
        by_room_slot.setdefault((rid, tid), []).append(var)

    course_instructor = {c.id: c.instructor_id for c in problem.courses}
    for (cid, rid, tid), var in x.items():
        by_instructor_slot.setdefault((course_instructor[cid], tid), []).append(var)

    # ---- H1: every course scheduled exactly once ------------------------
    for c in problem.courses:
        vars_for_course = by_course.get(c.id)
        if not vars_for_course:
            return SolveResult(
                status="infeasible",
                message=f"{c.code} has no room/slot combination satisfying the hard "
                        f"constraints, so no timetable exists.",
                pruned_triples=total_triples - len(x),
                num_variables=len(x),
            )
        model.AddExactlyOne(vars_for_course)

    # ---- H2: a room holds at most one course per slot -------------------
    if toggles.h2_room_conflict:
        for vars_here in by_room_slot.values():
            if len(vars_here) > 1:
                model.AddAtMostOne(vars_here)

    # ---- H3: an instructor teaches at most one course per slot ----------
    if toggles.h3_instructor_conflict:
        for vars_here in by_instructor_slot.values():
            if len(vars_here) > 1:
                model.AddAtMostOne(vars_here)

    # ---- objective ------------------------------------------------------
    soft_vars = [x[k] for k, p in penalties.items() if p > 0]
    soft_weights = [p for p in penalties.values() if p > 0]
    if soft_vars:
        model.Minimize(cp_model.LinearExpr.WeightedSum(soft_vars, soft_weights))
    else:
        model.Minimize(0)

    # ---- solve ----------------------------------------------------------
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = float(time_limit_seconds)
    solver.parameters.num_search_workers = num_workers

    start = time.perf_counter()
    status = solver.Solve(model)
    elapsed = time.perf_counter() - start

    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return SolveResult(
            status="infeasible" if status == cp_model.INFEASIBLE else "failed",
            solve_seconds=elapsed,
            num_variables=len(x),
            pruned_triples=total_triples - len(x),
            message=(
                "The hard constraints cannot all be satisfied at once. Every course "
                "has a valid room and slot individually, but they cannot be combined "
                "without a clash - try relaxing instructor availability or adding rooms."
                if status == cp_model.INFEASIBLE
                else f"Solver stopped without a solution (status={solver.StatusName(status)})."
            ),
        )

    placements = [
        Placement(course_id=cid, room_id=rid, slot_id=tid, penalty=penalties[(cid, rid, tid)])
        for (cid, rid, tid), var in x.items()
        if solver.Value(var) == 1
    ]
    placements.sort(key=lambda p: (p.slot_id, p.room_id))

    breakdown = _breakdown(problem, placements, weights)

    return SolveResult(
        status="optimal" if status == cp_model.OPTIMAL else "feasible",
        placements=placements,
        soft_score=int(round(solver.ObjectiveValue())),
        optimality_gap=_gap(solver),
        solve_seconds=elapsed,
        num_variables=len(x),
        pruned_triples=total_triples - len(x),
        penalty_breakdown=breakdown,
    )


def _gap(solver: cp_model.CpSolver) -> Optional[float]:
    """Relative optimality gap. 0.0 means provably optimal.

    CHRONOS_CONTEXT.md defines this as (Z - Z_LP) / Z_LP; for CP-SAT the role of
    Z_LP is played by the best proven lower bound.
    """
    try:
        z = solver.ObjectiveValue()
        bound = solver.BestObjectiveBound()
    except Exception:
        return None
    if z == bound:
        return 0.0
    if bound <= 0:
        return None if z > 0 else 0.0
    return (z - bound) / bound


def _breakdown(problem: Problem, placements: List[Placement], w: Weights) -> Dict[str, int]:
    """Split the objective into per-term contributions, for the UI and the report."""
    slots = {s.id: s for s in problem.slots}
    rooms = {r.id: r for r in problem.rooms}
    courses = {c.id: c for c in problem.courses}

    out = {"S1_morning": 0, "S2_preferred_day": 0, "S3_equipment": 0, "S4_room_type": 0}
    # Raw violation counts, independent of weight. Without these a zero weight
    # reads identically to zero violations, which is misleading in the UI.
    raw = {"S1_morning": 0, "S2_preferred_day": 0, "S3_equipment": 0, "S4_room_type": 0}
    for p in placements:
        c, r, t = courses[p.course_id], rooms[p.room_id], slots[p.slot_id]
        s1, s2 = _time_penalty(problem, c, t, w)
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
