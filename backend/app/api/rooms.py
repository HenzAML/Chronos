from flask import Blueprint, jsonify

from app.extensions import db
from app.models import Equipment, Room, RoomEquipment
from app.api.helpers import (
    ApiError, as_bool, as_id_list, as_int, body, commit, get_or_404, require, room_json,
)

bp = Blueprint("rooms", __name__, url_prefix="/api/rooms")

CAPABILITIES = (
    "supports_lecture", "supports_lab", "supports_group",
    "supports_seminar", "supports_meeting",
)


def _apply(room, data):
    if "code" in data:
        room.code = str(data["code"]).strip()
    if "name" in data:
        room.name = str(data["name"]).strip() if data["name"] else None
    if "capacity" in data:
        room.capacity = as_int(data, "capacity", minimum=1)
    for cap in CAPABILITIES:
        if cap in data:
            setattr(room, cap, as_bool(data, cap))


def _set_equipment(room, equipment_ids):
    known = {e.id for e in db.session.query(Equipment).all()}
    unknown = [i for i in equipment_ids if i not in known]
    if unknown:
        raise ApiError("Unknown equipment.", 422,
                       [f"No equipment with id {i}." for i in unknown])
    room.equipment_links.clear()
    db.session.flush()
    for eid in sorted(set(equipment_ids)):
        db.session.add(RoomEquipment(room_id=room.id, equipment_id=eid))


@bp.get("")
def list_rooms():
    rooms = db.session.query(Room).order_by(Room.code).all()
    return jsonify([room_json(r) for r in rooms])


@bp.get("/<int:room_id>")
def get_room(room_id):
    return jsonify(room_json(get_or_404(Room, room_id, "Room")))


@bp.post("")
def create_room():
    data = body()
    require(data, "code", "capacity")
    room = Room(code=str(data["code"]).strip(), capacity=as_int(data, "capacity", minimum=1))
    _apply(room, data)
    db.session.add(room)
    db.session.flush()
    if data.get("equipment_ids") is not None:
        _set_equipment(room, as_id_list(data, "equipment_ids"))
    commit()
    return jsonify(room_json(room)), 201


@bp.patch("/<int:room_id>")
def update_room(room_id):
    room = get_or_404(Room, room_id, "Room")
    data = body()
    _apply(room, data)
    if data.get("equipment_ids") is not None:
        _set_equipment(room, as_id_list(data, "equipment_ids"))
    commit()
    return jsonify(room_json(room))


@bp.put("/<int:room_id>/equipment")
def set_room_equipment(room_id):
    room = get_or_404(Room, room_id, "Room")
    data = body()
    ids = as_id_list(data, "equipment_ids")
    if ids is None:
        raise ApiError("Missing required field(s).", 422, ["'equipment_ids' is required."])
    _set_equipment(room, ids)
    commit()
    return jsonify(room_json(room))


@bp.delete("/<int:room_id>")
def delete_room(room_id):
    room = get_or_404(Room, room_id, "Room")
    db.session.delete(room)
    commit()
    return "", 204
