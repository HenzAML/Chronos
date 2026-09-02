from flask import Blueprint, jsonify

from app.extensions import db
from app.models import TimeSlot
from app.api.helpers import (
    ApiError, as_int, body, commit, get_or_404, slot_json,
)

bp = Blueprint("timeslots", __name__, url_prefix="/api/timeslots")


@bp.get("")
def list_slots():
    slots = db.session.query(TimeSlot).order_by(TimeSlot.day, TimeSlot.hour).all()
    return jsonify([slot_json(s) for s in slots])


@bp.post("")
def create_slot():
    data = body()
    day = as_int(data, "day", minimum=0, required=True)
    hour = as_int(data, "hour", minimum=0, required=True)
    if day > 6:
        raise ApiError("Invalid value.", 422, ["'day' must be between 0 and 6."])
    if hour > 23:
        raise ApiError("Invalid value.", 422, ["'hour' must be between 0 and 23."])
    s = TimeSlot(day=day, hour=hour)
    db.session.add(s)
    commit()
    return jsonify(slot_json(s)), 201


@bp.post("/generate")
def generate_grid():
    """Bulk-create a weekly grid, skipping slots that already exist."""
    data = body()
    days = as_int(data, "days", minimum=1, default=5)
    start = as_int(data, "start_hour", minimum=0, default=8)
    end = as_int(data, "end_hour", minimum=1, default=17)
    if days > 7:
        raise ApiError("Invalid value.", 422, ["'days' must be 7 or fewer."])
    if end <= start:
        raise ApiError("Invalid value.", 422, ["'end_hour' must be after 'start_hour'."])

    existing = {(s.day, s.hour) for s in db.session.query(TimeSlot).all()}
    created = []
    for d in range(days):
        for h in range(start, end):
            if (d, h) not in existing:
                s = TimeSlot(day=d, hour=h)
                db.session.add(s)
                created.append(s)
    commit()
    return jsonify({"created": len(created), "slots": [slot_json(s) for s in created]}), 201


@bp.delete("/<int:slot_id>")
def delete_slot(slot_id):
    s = get_or_404(TimeSlot, slot_id, "TimeSlot")
    db.session.delete(s)
    commit()
    return "", 204
