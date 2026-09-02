"""REST API blueprints.

No authentication - deferred out of v1 per the supervisor meeting. Every
endpoint is open; add an auth guard here when the User model lands.
"""

from app.api import (
    constraints, courses, equipment, instructors, rooms, schedules, timeslots,
)
from app.api.helpers import register_error_handlers

BLUEPRINTS = (
    courses.bp, instructors.bp, rooms.bp, equipment.bp,
    timeslots.bp, constraints.bp, schedules.bp,
)


def register_api(app):
    for bp in BLUEPRINTS:
        app.register_blueprint(bp)
    register_error_handlers(app)
