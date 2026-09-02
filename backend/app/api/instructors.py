from flask import Blueprint, jsonify

from app.extensions import db
from app.models import Instructor, InstructorAvailability, TimeSlot
from app.api.helpers import (
    ApiError, as_bool, as_id_list, body, commit, get_or_404, instructor_json, require,
)

bp = Blueprint("instructors", __name__, url_prefix="/api/instructors")


def _apply(inst, data):
    if "name" in data:
        inst.name = str(data["name"]).strip()
    if "email" in data:
        inst.email = str(data["email"]).strip() if data["email"] else None
    if "prefer_morning" in data:
        inst.prefer_morning = as_bool(data, "prefer_morning")
    if "preferred_days" in data:
        days = as_id_list(data, "preferred_days") or []
        bad = [d for d in days if d < 0 or d > 6]
        if bad:
            raise ApiError("Invalid value.", 422,
                           ["'preferred_days' entries must be between 0 and 6."])
        inst.preferred_days = sorted(set(days))


def _set_availability(inst, slot_ids):
    known = {s.id for s in db.session.query(TimeSlot).all()}
    unknown = [i for i in slot_ids if i not in known]
    if unknown:
        raise ApiError("Unknown time slot.", 422,
                       [f"No time slot with id {i}." for i in unknown])
    inst.availabilities.clear()
    db.session.flush()
    for sid in sorted(set(slot_ids)):
        db.session.add(InstructorAvailability(instructor_id=inst.id, time_slot_id=sid))


@bp.get("")
def list_instructors():
    items = db.session.query(Instructor).order_by(Instructor.name).all()
    return jsonify([instructor_json(i) for i in items])


@bp.get("/<int:instructor_id>")
def get_instructor(instructor_id):
    return jsonify(instructor_json(get_or_404(Instructor, instructor_id, "Instructor")))


@bp.post("")
def create_instructor():
    data = body()
    require(data, "name")
    inst = Instructor(name=str(data["name"]).strip(), preferred_days=[])
    _apply(inst, data)
    db.session.add(inst)
    db.session.flush()
    if data.get("availability_slot_ids") is not None:
        _set_availability(inst, as_id_list(data, "availability_slot_ids"))
    commit()
    return jsonify(instructor_json(inst)), 201


@bp.patch("/<int:instructor_id>")
def update_instructor(instructor_id):
    inst = get_or_404(Instructor, instructor_id, "Instructor")
    data = body()
    _apply(inst, data)
    if data.get("availability_slot_ids") is not None:
        _set_availability(inst, as_id_list(data, "availability_slot_ids"))
    commit()
    return jsonify(instructor_json(inst))


@bp.get("/<int:instructor_id>/availability")
def get_availability(instructor_id):
    inst = get_or_404(Instructor, instructor_id, "Instructor")
    from app.api.helpers import slot_json
    slots = sorted((a.time_slot for a in inst.availabilities),
                   key=lambda s: (s.day, s.hour))
    return jsonify([slot_json(s) for s in slots])


@bp.put("/<int:instructor_id>/availability")
def set_availability(instructor_id):
    inst = get_or_404(Instructor, instructor_id, "Instructor")
    data = body()
    ids = as_id_list(data, "slot_ids")
    if ids is None:
        raise ApiError("Missing required field(s).", 422, ["'slot_ids' is required."])
    _set_availability(inst, ids)
    commit()
    return jsonify(instructor_json(inst))


@bp.delete("/<int:instructor_id>")
def delete_instructor(instructor_id):
    inst = get_or_404(Instructor, instructor_id, "Instructor")
    if inst.courses:
        raise ApiError(
            "Cannot delete an instructor who still teaches courses.", 409,
            [f"{len(inst.courses)} course(s) reference this instructor."],
        )
    db.session.delete(inst)
    commit()
    return "", 204
