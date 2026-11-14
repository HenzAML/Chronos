"""Shared request/response plumbing for the REST API."""

from functools import wraps

from flask import jsonify, request

from app.extensions import db


class ApiError(Exception):
    """Raised anywhere in a view to produce a structured error response."""

    def __init__(self, message, status=400, details=None):
        super().__init__(message)
        self.message = message
        self.status = status
        self.details = details or []


def register_error_handlers(app):
    @app.errorhandler(ApiError)
    def _api_error(e):
        return jsonify(error={"message": e.message, "details": e.details}), e.status

    @app.errorhandler(404)
    def _not_found(e):
        return jsonify(error={"message": "Not found", "details": []}), 404

    @app.errorhandler(405)
    def _not_allowed(e):
        return jsonify(error={"message": "Method not allowed", "details": []}), 405

    @app.errorhandler(500)
    def _server_error(e):  # pragma: no cover - defensive
        db.session.rollback()
        return jsonify(error={"message": "Internal server error", "details": []}), 500


def body():
    """Parsed JSON object body, or a clear error."""
    data = request.get_json(silent=True)
    if data is None:
        raise ApiError("Request body must be JSON.", 400)
    if not isinstance(data, dict):
        raise ApiError("Request body must be a JSON object.", 400)
    return data


def require(data, *fields):
    missing = [f for f in fields if data.get(f) is None]
    if missing:
        raise ApiError(
            "Missing required field(s).", 422,
            [f"'{f}' is required." for f in missing],
        )


def get_or_404(model, pk, label=None):
    obj = db.session.get(model, pk)
    if obj is None:
        raise ApiError(f"{label or model.__name__} {pk} not found.", 404)
    return obj


def as_int(data, field, minimum=None, default=None, required=False):
    raw = data.get(field, default)
    if raw is None:
        if required:
            raise ApiError("Missing required field(s).", 422, [f"'{field}' is required."])
        return None
    try:
        value = int(raw)
    except (TypeError, ValueError):
        raise ApiError("Invalid value.", 422, [f"'{field}' must be an integer."])
    if minimum is not None and value < minimum:
        raise ApiError("Invalid value.", 422, [f"'{field}' must be >= {minimum}."])
    return value


def as_bool(data, field, default=None):
    raw = data.get(field, default)
    if raw is None:
        return None
    if isinstance(raw, bool):
        return raw
    raise ApiError("Invalid value.", 422, [f"'{field}' must be true or false."])


def as_id_list(data, field):
    raw = data.get(field)
    if raw is None:
        return None
    if not isinstance(raw, list) or any(not isinstance(v, int) for v in raw):
        raise ApiError("Invalid value.", 422, [f"'{field}' must be a list of integers."])
    return raw


def commit():
    """Commit, converting DB constraint failures into 409/422 responses."""
    from sqlalchemy.exc import IntegrityError

    try:
        db.session.commit()
    except IntegrityError as e:
        db.session.rollback()
        detail = str(getattr(e, "orig", e)).splitlines()[0]
        if "duplicate key" in detail:
            raise ApiError("That record already exists.", 409, [detail])
        raise ApiError("The database rejected this change.", 422, [detail])


def handle_errors(fn):
    """Views raise ApiError freely; SQLAlchemy sessions get rolled back on failure."""

    @wraps(fn)
    def wrapper(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except ApiError:
            db.session.rollback()
            raise

    return wrapper


# ---------------------------------------------------------------------------
# Serializers
# ---------------------------------------------------------------------------

def slot_json(s):
    return {"id": s.id, "day": s.day, "hour": s.hour, "label": s.label}


def equipment_json(e):
    return {"id": e.id, "code": e.code, "name": e.name}


def room_json(r, deep=True):
    out = {
        "id": r.id, "code": r.code, "name": r.name, "capacity": r.capacity,
        "supports_lecture": r.supports_lecture, "supports_lab": r.supports_lab,
        "supports_group": r.supports_group, "supports_seminar": r.supports_seminar,
        "supports_meeting": r.supports_meeting,
    }
    if deep:
        out["equipment"] = sorted(
            (equipment_json(link.equipment) for link in r.equipment_links),
            key=lambda e: e["code"],
        )
    return out


def instructor_json(i, deep=True):
    out = {
        "id": i.id, "name": i.name, "email": i.email,
        "prefer_morning": i.prefer_morning,
        "preferred_days": list(i.preferred_days or []),
    }
    if deep:
        out["availability_slot_ids"] = sorted(i.available_slot_ids)
        out["course_count"] = len(i.courses)
    return out


def course_json(c, deep=True):
    out = {
        "id": c.id, "code": c.code, "name": c.name,
        "instructor_id": c.instructor_id,
        "duration_hours": c.duration_hours,
        "classes_per_week": c.classes_per_week,
        "expected_students": c.expected_students,
        "session_type": c.session_type,
    }
    if deep:
        out["instructor"] = instructor_json(c.instructor, deep=False) if c.instructor else None
        out["equipment_requirements"] = [
            {
                "equipment_id": r.equipment_id,
                "code": r.equipment.code,
                "name": r.equipment.name,
                "is_essential": r.is_essential,
            }
            for r in sorted(c.equipment_requirements, key=lambda r: r.equipment.code)
        ]
    return out


def config_json(cfg):
    return {
        "enable_h2_room_conflict": cfg.enable_h2_room_conflict,
        "enable_h3_instructor_conflict": cfg.enable_h3_instructor_conflict,
        "enable_h4_capacity": cfg.enable_h4_capacity,
        "enable_h5_availability": cfg.enable_h5_availability,
        "enable_h6_essential_equipment": cfg.enable_h6_essential_equipment,
        "w1_morning": cfg.w1_morning,
        "w2_preferred_day": cfg.w2_preferred_day,
        "w3_equipment": cfg.w3_equipment,
        "w4_room_type": cfg.w4_room_type,
        "solver_time_limit_seconds": cfg.solver_time_limit_seconds,
    }


def schedule_json(s, deep=False):
    out = {
        "id": s.id, "name": s.name, "algorithm": s.algorithm, "status": s.status,
        "hard_violations": s.hard_violations, "soft_score": s.soft_score,
        "optimality_gap": s.optimality_gap, "solve_seconds": s.solve_seconds,
        "weights": {
            "w1_morning": s.w1_morning, "w2_preferred_day": s.w2_preferred_day,
            "w3_equipment": s.w3_equipment, "w4_room_type": s.w4_room_type,
        },
        "message": s.message,
        "created_at": s.created_at.isoformat() if s.created_at else None,
        "assignment_count": len(s.assignments),
        "unscheduled_count": len(s.unscheduled or []),
        "class_count": len(s.assignments) + len(s.unscheduled or []),
    }
    if deep:
        out["unscheduled"] = list(s.unscheduled or [])
        out["assignments"] = [assignment_json(a) for a in sorted(
            s.assignments, key=lambda a: (a.time_slot.day, a.time_slot.hour, a.room.code))]
    return out


def assignment_json(a):
    return {
        "id": a.id,
        "class_index": a.class_index,
        "duration_hours": a.duration_hours,
        "end_hour": a.time_slot.hour + a.duration_hours,
        "course": {"id": a.course.id, "code": a.course.code, "name": a.course.name,
                   "session_type": a.course.session_type,
                   "classes_per_week": a.course.classes_per_week,
                   "expected_students": a.course.expected_students,
                   "instructor": a.course.instructor.name if a.course.instructor else None},
        "room": {"id": a.room.id, "code": a.room.code, "capacity": a.room.capacity},
        "time_slot": slot_json(a.time_slot),
    }
