from flask import Blueprint, jsonify, request

from app.extensions import db
from app.models import Schedule
from app.api.helpers import (
    ApiError, as_bool, as_int, assignment_json, body, commit, get_or_404, schedule_json,
)
from app.solver import generate_schedule
from app.solver.problem import Toggles, Weights
from app.models import ConstraintConfig

bp = Blueprint("schedules", __name__, url_prefix="/api")


@bp.post("/generate")
def generate():
    """Run the solver.

    Always returns 200 with the persisted Schedule. Check `status`:
    optimal | feasible (every class placed), partial (best schedule found, with
    `unscheduled` listing each class left out and why), failed (no data).
    """
    data = request.get_json(silent=True) or {}
    if not isinstance(data, dict):
        raise ApiError("Request body must be a JSON object.", 400)

    cfg = ConstraintConfig.get()
    weights = Weights(
        w1_morning=as_int(data, "w1_morning", minimum=0, default=cfg.w1_morning),
        w2_preferred_day=as_int(data, "w2_preferred_day", minimum=0, default=cfg.w2_preferred_day),
        w3_equipment=as_int(data, "w3_equipment", minimum=0, default=cfg.w3_equipment),
        w4_room_type=as_int(data, "w4_room_type", minimum=0, default=cfg.w4_room_type),
    )
    toggles = Toggles(
        h2_room_conflict=_flag(data, "enable_h2_room_conflict", cfg.enable_h2_room_conflict),
        h3_instructor_conflict=_flag(data, "enable_h3_instructor_conflict", cfg.enable_h3_instructor_conflict),
        h4_capacity=_flag(data, "enable_h4_capacity", cfg.enable_h4_capacity),
        h5_availability=_flag(data, "enable_h5_availability", cfg.enable_h5_availability),
        h6_essential_equipment=_flag(data, "enable_h6_essential_equipment", cfg.enable_h6_essential_equipment),
    )
    limit = as_int(data, "time_limit_seconds", minimum=1,
                   default=cfg.solver_time_limit_seconds)

    schedule = generate_schedule(
        name=(str(data["name"]).strip() if data.get("name") else None),
        time_limit_seconds=limit,
        weights=weights,
        toggles=toggles,
    )

    payload = schedule_json(schedule, deep=True)
    result = getattr(schedule, "last_result", None)
    if result is not None and result.ok:
        payload["diagnostics"] = {
            "num_variables": result.num_variables,
            "pruned_triples": result.pruned_triples,
            "penalty_breakdown": result.penalty_breakdown,
        }
    return jsonify(payload)


def _flag(data, name, fallback):
    value = as_bool(data, name)
    return fallback if value is None else value


@bp.get("/schedules")
def list_schedules():
    limit = request.args.get("limit", type=int) or 50
    items = (db.session.query(Schedule)
             .order_by(Schedule.created_at.desc(), Schedule.id.desc())
             .limit(min(limit, 200)).all())
    return jsonify([schedule_json(s) for s in items])


@bp.get("/schedules/<int:schedule_id>")
def get_schedule(schedule_id):
    return jsonify(schedule_json(get_or_404(Schedule, schedule_id, "Schedule"), deep=True))


@bp.get("/schedules/<int:schedule_id>/assignments")
def get_assignments(schedule_id):
    s = get_or_404(Schedule, schedule_id, "Schedule")
    rows = sorted(s.assignments, key=lambda a: (a.time_slot.day, a.time_slot.hour, a.room.code))
    return jsonify([assignment_json(a) for a in rows])


@bp.get("/schedules/<int:schedule_id>/grid")
def get_grid(schedule_id):
    """Timetable shaped for the weekly grid view: day -> hour -> assignments."""
    s = get_or_404(Schedule, schedule_id, "Schedule")
    grid = {}
    for a in s.assignments:
        day = str(a.time_slot.day)
        hour = str(a.time_slot.hour)
        grid.setdefault(day, {}).setdefault(hour, []).append(assignment_json(a))
    # A block is listed under its start hour; hours covers every hour it touches.
    hours = sorted({a.time_slot.hour + k for a in s.assignments
                    for k in range(a.duration_hours)})
    return jsonify({
        "schedule": schedule_json(s),
        "hours": hours,
        "days": sorted({a.time_slot.day for a in s.assignments}),
        "grid": grid,
    })


@bp.delete("/schedules/<int:schedule_id>")
def delete_schedule(schedule_id):
    s = get_or_404(Schedule, schedule_id, "Schedule")
    db.session.delete(s)
    commit()
    return "", 204
