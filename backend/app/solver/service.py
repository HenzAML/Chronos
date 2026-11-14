"""Orchestration: load -> solve -> persist.

This is what POST /generate will call.
"""

from typing import Optional

from app.extensions import db
from app.models import ConstraintConfig, CourseAssignment, Schedule
from app.solver.cpsat import SolveResult, solve
from app.solver.problem import Toggles, Weights, load_problem


def generate_schedule(
    name: Optional[str] = None,
    time_limit_seconds: Optional[int] = None,
    weights: Optional[Weights] = None,
    toggles: Optional[Toggles] = None,
    persist: bool = True,
) -> Schedule:
    """Run the solver and record the outcome as a Schedule row.

    Classes that cannot fit are left out and listed in Schedule.unscheduled with
    a reason each (status "partial"). A failed run is still persisted with a
    message, so the coordinator never gets silence.
    """
    cfg = ConstraintConfig.get()
    weights = weights or Weights.from_config(cfg)
    toggles = toggles or Toggles.from_config(cfg)
    limit = time_limit_seconds or cfg.solver_time_limit_seconds

    problem = load_problem(db.session)

    schedule = Schedule(
        name=name,
        algorithm="ortools_cpsat",
        status="pending",
        w1_morning=weights.w1_morning,
        w2_preferred_day=weights.w2_preferred_day,
        w3_equipment=weights.w3_equipment,
        w4_room_type=weights.w4_room_type,
    )

    try:
        result = solve(problem, weights=weights, toggles=toggles, time_limit_seconds=limit)
    except Exception as e:  # a solver crash is recorded as a failed run, never a 500
        result = SolveResult(status="failed", message=f"The solver crashed: {e}")

    schedule.status = result.status
    schedule.solve_seconds = result.solve_seconds
    schedule.message = result.message

    if result.ok:
        schedule.soft_score = result.soft_score
        schedule.optimality_gap = result.optimality_gap
        schedule.hard_violations = 0
        schedule.unscheduled = [u.as_dict() for u in result.unscheduled]
        schedule.assignments = [
            CourseAssignment(
                course_id=p.course_id, class_index=p.class_index, room_id=p.room_id,
                time_slot_id=p.slot_id, duration_hours=p.duration_hours,
            )
            for p in result.placements
        ]

    if persist:
        db.session.add(schedule)
        db.session.commit()

    # Attach non-persisted diagnostics for the caller (API response, CLI output).
    schedule.last_result = result  # type: ignore[attr-defined]
    return schedule
