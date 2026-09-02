"""Chronos data model.

Mirrors the schema in CHRONOS_CONTEXT.md. Auth (User) is deliberately absent -
deferred out of v1 per the 2026-09-02 supervisor meeting.
"""

from datetime import datetime, timezone

from sqlalchemy.dialects.postgresql import ARRAY

from app.extensions import db

# Session types double as room capability names: a course with session_type
# "lab" is checked against Room.supports_lab.
SESSION_TYPES = ("lecture", "lab", "group", "seminar", "meeting")

# Schedule.status values.
SCHEDULE_STATUSES = ("pending", "optimal", "feasible", "infeasible", "failed")

DAY_NAMES = ("Mon", "Tue", "Wed", "Thu", "Fri")


def _utcnow():
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Reference data
# ---------------------------------------------------------------------------

class TimeSlot(db.Model):
    __tablename__ = "time_slot"
    __table_args__ = (
        db.UniqueConstraint("day", "hour", name="uq_time_slot_day_hour"),
        db.CheckConstraint("day between 0 and 6", name="ck_time_slot_day"),
        db.CheckConstraint("hour between 0 and 23", name="ck_time_slot_hour"),
    )

    id = db.Column(db.Integer, primary_key=True)
    day = db.Column(db.Integer, nullable=False)   # 0 = Monday
    hour = db.Column(db.Integer, nullable=False)  # 24h, start of the hour

    def as_tuple(self):
        return (self.day, self.hour)

    @property
    def label(self):
        return f"{DAY_NAMES[self.day]} {self.hour:02d}:00"

    def __repr__(self):
        return f"<TimeSlot {self.label}>"


class Equipment(db.Model):
    __tablename__ = "equipment"

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(50), nullable=False, unique=True)
    name = db.Column(db.String(120), nullable=False)

    def __repr__(self):
        return f"<Equipment {self.code}>"


# ---------------------------------------------------------------------------
# Rooms
# ---------------------------------------------------------------------------

class Room(db.Model):
    __tablename__ = "room"
    __table_args__ = (
        db.CheckConstraint("capacity > 0", name="ck_room_capacity_positive"),
    )

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(50), nullable=False, unique=True)
    name = db.Column(db.String(120))
    capacity = db.Column(db.Integer, nullable=False)

    # Capability flags - multi-label, a room may support several.
    supports_lecture = db.Column(db.Boolean, nullable=False, default=True)
    supports_lab = db.Column(db.Boolean, nullable=False, default=False)
    supports_group = db.Column(db.Boolean, nullable=False, default=False)
    supports_seminar = db.Column(db.Boolean, nullable=False, default=False)
    supports_meeting = db.Column(db.Boolean, nullable=False, default=False)

    equipment_links = db.relationship(
        "RoomEquipment", back_populates="room",
        cascade="all, delete-orphan", passive_deletes=True,
    )

    def supports(self, session_type):
        """True if this room is suitable for the given session type (soft S4)."""
        return bool(getattr(self, f"supports_{session_type}", False))

    @property
    def equipment_ids(self):
        return {link.equipment_id for link in self.equipment_links}

    def __repr__(self):
        return f"<Room {self.code} cap={self.capacity}>"


class RoomEquipment(db.Model):
    """What a room actually has."""

    __tablename__ = "room_equipment"

    room_id = db.Column(
        db.Integer, db.ForeignKey("room.id", ondelete="CASCADE"), primary_key=True
    )
    equipment_id = db.Column(
        db.Integer, db.ForeignKey("equipment.id", ondelete="CASCADE"), primary_key=True
    )

    room = db.relationship("Room", back_populates="equipment_links")
    equipment = db.relationship("Equipment")


# ---------------------------------------------------------------------------
# Instructors
# ---------------------------------------------------------------------------

class Instructor(db.Model):
    __tablename__ = "instructor"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(200))

    # Soft preferences.
    prefer_morning = db.Column(db.Boolean, nullable=False, default=False)   # S1
    preferred_days = db.Column(ARRAY(db.Integer), nullable=False, default=list)  # S2

    availabilities = db.relationship(
        "InstructorAvailability", back_populates="instructor",
        cascade="all, delete-orphan", passive_deletes=True,
    )
    courses = db.relationship("Course", back_populates="instructor")

    @property
    def available_slot_ids(self):
        return {a.time_slot_id for a in self.availabilities}

    def __repr__(self):
        return f"<Instructor {self.name}>"


class InstructorAvailability(db.Model):
    """Hard availability (H5): an instructor may only teach in these slots."""

    __tablename__ = "instructor_availability"

    instructor_id = db.Column(
        db.Integer, db.ForeignKey("instructor.id", ondelete="CASCADE"), primary_key=True
    )
    time_slot_id = db.Column(
        db.Integer, db.ForeignKey("time_slot.id", ondelete="CASCADE"), primary_key=True
    )

    instructor = db.relationship("Instructor", back_populates="availabilities")
    time_slot = db.relationship("TimeSlot")


# ---------------------------------------------------------------------------
# Courses
# ---------------------------------------------------------------------------

class Course(db.Model):
    __tablename__ = "course"
    __table_args__ = (
        db.CheckConstraint("expected_students > 0", name="ck_course_students_positive"),
        db.CheckConstraint("duration_hours > 0", name="ck_course_duration_positive"),
        db.CheckConstraint(
            "session_type in ('lecture', 'lab', 'group', 'seminar', 'meeting')",
            name="ck_course_session_type",
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(50), nullable=False, unique=True)
    name = db.Column(db.String(200), nullable=False)
    instructor_id = db.Column(
        db.Integer, db.ForeignKey("instructor.id", ondelete="RESTRICT"), nullable=False
    )
    duration_hours = db.Column(db.Integer, nullable=False, default=1)
    expected_students = db.Column(db.Integer, nullable=False)
    session_type = db.Column(db.String(20), nullable=False, default="lecture")

    instructor = db.relationship("Instructor", back_populates="courses")
    equipment_requirements = db.relationship(
        "CourseEquipmentRequirement", back_populates="course",
        cascade="all, delete-orphan", passive_deletes=True,
    )

    @property
    def essential_equipment_ids(self):
        """Drives hard constraint H6."""
        return {r.equipment_id for r in self.equipment_requirements if r.is_essential}

    @property
    def preferred_equipment_ids(self):
        """Drives soft penalty S3."""
        return {r.equipment_id for r in self.equipment_requirements if not r.is_essential}

    def __repr__(self):
        return f"<Course {self.code}>"


class CourseEquipmentRequirement(db.Model):
    """What a course needs.

    is_essential = True  -> hard constraint H6 (room must have it)
    is_essential = False -> soft penalty S3 (one unit per missing item)
    """

    __tablename__ = "course_equipment_requirement"

    course_id = db.Column(
        db.Integer, db.ForeignKey("course.id", ondelete="CASCADE"), primary_key=True
    )
    equipment_id = db.Column(
        db.Integer, db.ForeignKey("equipment.id", ondelete="CASCADE"), primary_key=True
    )
    is_essential = db.Column(db.Boolean, nullable=False, default=False)

    course = db.relationship("Course", back_populates="equipment_requirements")
    equipment = db.relationship("Equipment")


# ---------------------------------------------------------------------------
# Solver configuration and output
# ---------------------------------------------------------------------------

class ConstraintConfig(db.Model):
    """Singleton (id == 1) backing the Constraints page."""

    __tablename__ = "constraint_config"

    id = db.Column(db.Integer, primary_key=True, default=1)

    # Hard constraint toggles. H1 is structural and always enforced.
    enable_h2_room_conflict = db.Column(db.Boolean, nullable=False, default=True)
    enable_h3_instructor_conflict = db.Column(db.Boolean, nullable=False, default=True)
    enable_h4_capacity = db.Column(db.Boolean, nullable=False, default=True)
    enable_h5_availability = db.Column(db.Boolean, nullable=False, default=True)
    enable_h6_essential_equipment = db.Column(db.Boolean, nullable=False, default=True)

    # Soft weights.
    w1_morning = db.Column(db.Integer, nullable=False, default=10)
    w2_preferred_day = db.Column(db.Integer, nullable=False, default=5)
    w3_equipment = db.Column(db.Integer, nullable=False, default=3)
    w4_room_type = db.Column(db.Integer, nullable=False, default=4)

    solver_time_limit_seconds = db.Column(db.Integer, nullable=False, default=30)

    @classmethod
    def get(cls):
        """Fetch the singleton, creating it with defaults on first use."""
        cfg = db.session.get(cls, 1)
        if cfg is None:
            cfg = cls(id=1)
            db.session.add(cfg)
            db.session.commit()
        return cfg


class Schedule(db.Model):
    __tablename__ = "schedule"
    __table_args__ = (
        db.CheckConstraint(
            "status in ('pending', 'optimal', 'feasible', 'infeasible', 'failed')",
            name="ck_schedule_status",
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200))
    algorithm = db.Column(db.String(50), nullable=False, default="ortools_cpsat")
    status = db.Column(db.String(20), nullable=False, default="pending")

    hard_violations = db.Column(db.Integer, nullable=False, default=0)
    soft_score = db.Column(db.Integer)
    optimality_gap = db.Column(db.Float)
    solve_seconds = db.Column(db.Float)

    # Weights this run actually used, so results stay reproducible even after
    # the config is edited.
    w1_morning = db.Column(db.Integer, nullable=False, default=10)
    w2_preferred_day = db.Column(db.Integer, nullable=False, default=5)
    w3_equipment = db.Column(db.Integer, nullable=False, default=3)
    w4_room_type = db.Column(db.Integer, nullable=False, default=4)

    # Human-readable reason when status is infeasible/failed.
    message = db.Column(db.Text)

    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=_utcnow)

    assignments = db.relationship(
        "CourseAssignment", back_populates="schedule",
        cascade="all, delete-orphan", passive_deletes=True,
    )

    def __repr__(self):
        return f"<Schedule {self.id} {self.status} soft={self.soft_score}>"


class CourseAssignment(db.Model):
    """One solved x[c, r, t] == 1."""

    __tablename__ = "course_assignment"
    __table_args__ = (
        db.UniqueConstraint("schedule_id", "course_id", name="uq_assignment_schedule_course"),
    )

    id = db.Column(db.Integer, primary_key=True)
    schedule_id = db.Column(
        db.Integer, db.ForeignKey("schedule.id", ondelete="CASCADE"), nullable=False
    )
    course_id = db.Column(
        db.Integer, db.ForeignKey("course.id", ondelete="CASCADE"), nullable=False
    )
    room_id = db.Column(
        db.Integer, db.ForeignKey("room.id", ondelete="RESTRICT"), nullable=False
    )
    time_slot_id = db.Column(
        db.Integer, db.ForeignKey("time_slot.id", ondelete="RESTRICT"), nullable=False
    )

    schedule = db.relationship("Schedule", back_populates="assignments")
    course = db.relationship("Course")
    room = db.relationship("Room")
    time_slot = db.relationship("TimeSlot")

    def __repr__(self):
        return f"<Assignment c={self.course_id} r={self.room_id} t={self.time_slot_id}>"
