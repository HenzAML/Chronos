from flask import Blueprint, jsonify

from app.models import ConstraintConfig
from app.api.helpers import ApiError, as_bool, as_int, body, commit, config_json

bp = Blueprint("constraints", __name__, url_prefix="/api/constraints")

TOGGLES = (
    "enable_h2_room_conflict", "enable_h3_instructor_conflict",
    "enable_h4_capacity", "enable_h5_availability",
    "enable_h6_essential_equipment",
)
WEIGHTS = ("w1_morning", "w2_preferred_day", "w3_equipment", "w4_room_type")


@bp.get("")
def get_constraints():
    return jsonify(config_json(ConstraintConfig.get()))


@bp.put("")
def update_constraints():
    cfg = ConstraintConfig.get()
    data = body()
    unknown = set(data) - set(TOGGLES) - set(WEIGHTS) - {"solver_time_limit_seconds"}
    if unknown:
        raise ApiError("Unknown field(s).", 422,
                       [f"'{f}' is not a constraint setting." for f in sorted(unknown)])
    for name in TOGGLES:
        if name in data:
            setattr(cfg, name, as_bool(data, name))
    for name in WEIGHTS:
        if name in data:
            setattr(cfg, name, as_int(data, name, minimum=0))
    if "solver_time_limit_seconds" in data:
        cfg.solver_time_limit_seconds = as_int(
            data, "solver_time_limit_seconds", minimum=1)
    commit()
    return jsonify(config_json(cfg))
