from flask import Blueprint, jsonify

from app.extensions import db
from app.models import Equipment
from app.api.helpers import (
    ApiError, body, commit, equipment_json, get_or_404, require,
)

bp = Blueprint("equipment", __name__, url_prefix="/api/equipment")


@bp.get("")
def list_equipment():
    items = db.session.query(Equipment).order_by(Equipment.code).all()
    return jsonify([equipment_json(e) for e in items])


@bp.get("/<int:equipment_id>")
def get_equipment(equipment_id):
    return jsonify(equipment_json(get_or_404(Equipment, equipment_id, "Equipment")))


@bp.post("")
def create_equipment():
    data = body()
    require(data, "code", "name")
    e = Equipment(code=str(data["code"]).strip(), name=str(data["name"]).strip())
    db.session.add(e)
    commit()
    return jsonify(equipment_json(e)), 201


@bp.patch("/<int:equipment_id>")
def update_equipment(equipment_id):
    e = get_or_404(Equipment, equipment_id, "Equipment")
    data = body()
    if "code" in data:
        e.code = str(data["code"]).strip()
    if "name" in data:
        e.name = str(data["name"]).strip()
    commit()
    return jsonify(equipment_json(e))


@bp.delete("/<int:equipment_id>")
def delete_equipment(equipment_id):
    e = get_or_404(Equipment, equipment_id, "Equipment")
    db.session.delete(e)
    commit()
    return "", 204
