from flask import Blueprint, jsonify, request

from app.extensions import db
from app.models import SESSION_TYPES, Course, CourseEquipmentRequirement, Equipment, Instructor
from app.api.helpers import (
    ApiError, as_int, body, commit, course_json, get_or_404, require,
)

bp = Blueprint("courses", __name__, url_prefix="/api/courses")


def _apply(course, data):
    if "code" in data:
        course.code = str(data["code"]).strip()
    if "name" in data:
        course.name = str(data["name"]).strip()
    if "expected_students" in data:
        course.expected_students = as_int(data, "expected_students", minimum=1)
    if "duration_hours" in data:
        course.duration_hours = as_int(data, "duration_hours", minimum=1)
    if "classes_per_week" in data:
        course.classes_per_week = as_int(data, "classes_per_week", minimum=1)
    if "session_type" in data:
        st = str(data["session_type"]).strip()
        if st not in SESSION_TYPES:
            raise ApiError("Invalid value.", 422,
                           [f"'session_type' must be one of: {', '.join(SESSION_TYPES)}."])
        course.session_type = st
    if "instructor_id" in data:
        iid = as_int(data, "instructor_id", minimum=1)
        get_or_404(Instructor, iid, "Instructor")
        course.instructor_id = iid


def _set_requirements(course, items):
    """items: [{equipment_id, is_essential}]"""
    if not isinstance(items, list):
        raise ApiError("Invalid value.", 422,
                       ["'equipment_requirements' must be a list."])
    known = {e.id for e in db.session.query(Equipment).all()}
    parsed = []
    for item in items:
        if not isinstance(item, dict) or "equipment_id" not in item:
            raise ApiError("Invalid value.", 422,
                           ["each requirement needs an 'equipment_id'."])
        eid = item["equipment_id"]
        if eid not in known:
            raise ApiError("Unknown equipment.", 422, [f"No equipment with id {eid}."])
        parsed.append((eid, bool(item.get("is_essential", False))))

    course.equipment_requirements.clear()
    db.session.flush()
    seen = set()
    for eid, essential in parsed:
        if eid in seen:
            continue
        seen.add(eid)
        db.session.add(CourseEquipmentRequirement(
            course_id=course.id, equipment_id=eid, is_essential=essential))


@bp.get("")
def list_courses():
    q = db.session.query(Course)
    session_type = request.args.get("session_type")
    if session_type:
        q = q.filter(Course.session_type == session_type)
    instructor_id = request.args.get("instructor_id", type=int)
    if instructor_id:
        q = q.filter(Course.instructor_id == instructor_id)
    return jsonify([course_json(c) for c in q.order_by(Course.code).all()])


@bp.get("/<int:course_id>")
def get_course(course_id):
    return jsonify(course_json(get_or_404(Course, course_id, "Course")))


@bp.post("")
def create_course():
    data = body()
    require(data, "code", "name", "instructor_id", "expected_students")
    course = Course(
        code=str(data["code"]).strip(),
        name=str(data["name"]).strip(),
        instructor_id=as_int(data, "instructor_id", minimum=1),
        expected_students=as_int(data, "expected_students", minimum=1),
    )
    _apply(course, data)
    db.session.add(course)
    db.session.flush()
    if data.get("equipment_requirements") is not None:
        _set_requirements(course, data["equipment_requirements"])
    commit()
    return jsonify(course_json(course)), 201


@bp.patch("/<int:course_id>")
def update_course(course_id):
    course = get_or_404(Course, course_id, "Course")
    data = body()
    _apply(course, data)
    if data.get("equipment_requirements") is not None:
        _set_requirements(course, data["equipment_requirements"])
    commit()
    return jsonify(course_json(course))


@bp.put("/<int:course_id>/requirements")
def set_requirements(course_id):
    course = get_or_404(Course, course_id, "Course")
    data = body()
    items = data.get("equipment_requirements")
    if items is None:
        raise ApiError("Missing required field(s).", 422,
                       ["'equipment_requirements' is required."])
    _set_requirements(course, items)
    commit()
    return jsonify(course_json(course))


@bp.delete("/<int:course_id>")
def delete_course(course_id):
    course = get_or_404(Course, course_id, "Course")
    db.session.delete(course)
    commit()
    return "", 204
