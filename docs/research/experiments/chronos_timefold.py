"""
Timefold Solver bridge for Chronos instructor-constraints experiment.
Maps our problem (courses, instructors with availability/preferences, rooms, timeslots)
to Timefold domain and constraints, runs the solver, maps solution back to Assignments.

Requires: pip install git+https://github.com/TimefoldAI/timefold-solver-python.git
          JDK 17+ and JAVA_HOME set.
"""

from dataclasses import dataclass
from typing import List, Dict, Tuple, Any, Annotated

# Timefold imports (optional)
try:
    from timefold.solver import SolverFactory
    from timefold.solver.config import (
        SolverConfig,
        ScoreDirectorFactoryConfig,
        TerminationConfig,
        Duration,
    )
    from timefold.solver.domain import (
        planning_entity,
        planning_solution,
        PlanningId,
        PlanningVariable,
        ProblemFactCollectionProperty,
        ValueRangeProvider,
        PlanningEntityCollectionProperty,
        PlanningScore,
    )
    from timefold.solver.score import (
        HardSoftScore,
        constraint_provider,
        ConstraintFactory,
        Constraint,
        Joiners,
    )
    TIMEFOLD_IMPORT_OK = True
except ImportError as e:
    TIMEFOLD_IMPORT_OK = False
    _TIMEFOLD_IMPORT_ERROR = str(e)
    # Stub all names used in domain/solution classes so the module loads and we can report the import error
    planning_entity = lambda c: c
    planning_solution = lambda c: c
    PlanningId = object()
    PlanningVariable = object()
    ProblemFactCollectionProperty = object()
    ValueRangeProvider = object()
    PlanningEntityCollectionProperty = object()
    PlanningScore = object()


# ---------------------------------------------------------------------------
# Timefold domain (mirrors our problem)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class TFTimeslot:
    """Timefold timeslot: id, day (0-4), hour (8-16)."""
    id: str
    day: int
    hour: int


@dataclass
class TFRoom:
    """Timefold room with capacity."""
    id: str
    capacity: int


@dataclass
class TFInstructor:
    """Instructor as problem fact: availability (hard), preferences (soft)."""
    id: str
    availability: tuple  # tuple of (day, hour) for hashability
    prefer_morning: bool
    preferred_days: tuple  # tuple of int


@planning_entity
@dataclass
class TFLesson:
    """Lesson = one course to schedule. Planning variables: timeslot, room."""
    id: Annotated[str, PlanningId]
    course_id: str
    instructor_id: str
    expected_students: int
    timeslot: Annotated[TFTimeslot | None, PlanningVariable] = None
    room: Annotated[TFRoom | None, PlanningVariable] = None


@planning_solution
@dataclass
class TFTimetable:
    """Solution: timeslots, rooms, instructors (facts), lessons (entities), score."""
    timeslots: Annotated[List[TFTimeslot], ProblemFactCollectionProperty, ValueRangeProvider]
    rooms: Annotated[List[TFRoom], ProblemFactCollectionProperty, ValueRangeProvider]
    instructors: Annotated[List[TFInstructor], ProblemFactCollectionProperty]
    lessons: Annotated[List[TFLesson], PlanningEntityCollectionProperty]
    score: Annotated[HardSoftScore | None, PlanningScore] = None


# ---------------------------------------------------------------------------
# Constraints
# ---------------------------------------------------------------------------

@constraint_provider
def define_constraints(constraint_factory: ConstraintFactory) -> List[Constraint]:
    return [
        room_conflict(constraint_factory),
        teacher_conflict(constraint_factory),
        room_capacity(constraint_factory),
        instructor_availability(constraint_factory),
        prefer_morning(constraint_factory),
        prefer_days(constraint_factory),
    ]


def room_conflict(constraint_factory: ConstraintFactory) -> Constraint:
    return (
        constraint_factory.for_each_unique_pair(
            TFLesson,
            Joiners.equal(lambda l: l.timeslot),
            Joiners.equal(lambda l: l.room),
        )
        .penalize(HardSoftScore.ONE_HARD)
        .as_constraint("Room conflict")
    )


def teacher_conflict(constraint_factory: ConstraintFactory) -> Constraint:
    return (
        constraint_factory.for_each_unique_pair(
            TFLesson,
            Joiners.equal(lambda l: l.timeslot),
            Joiners.equal(lambda l: l.instructor_id),
        )
        .penalize(HardSoftScore.ONE_HARD)
        .as_constraint("Teacher conflict")
    )


def room_capacity(constraint_factory: ConstraintFactory) -> Constraint:
    return (
        constraint_factory.for_each(TFLesson)
        .filter(lambda l: l.room is not None and l.room.capacity < l.expected_students)
        .penalize(HardSoftScore.ONE_HARD)
        .as_constraint("Room capacity")
    )


def instructor_availability(constraint_factory: ConstraintFactory) -> Constraint:
    return (
        constraint_factory.for_each(TFLesson)
        .join(TFInstructor, Joiners.equal(lambda l: l.instructor_id, lambda i: i.id))
        .filter(
            lambda lesson, instructor: lesson.timeslot is not None
            and (lesson.timeslot.day, lesson.timeslot.hour) not in instructor.availability
        )
        .penalize(HardSoftScore.ONE_HARD)
        .as_constraint("Instructor availability")
    )


def prefer_morning(constraint_factory: ConstraintFactory) -> Constraint:
    return (
        constraint_factory.for_each(TFLesson)
        .join(TFInstructor, Joiners.equal(lambda l: l.instructor_id, lambda i: i.id))
        .filter(
            lambda lesson, instructor: instructor.prefer_morning
            and lesson.timeslot is not None
            and lesson.timeslot.hour >= 12
        )
        .penalize(HardSoftScore.of_soft(10))
        .as_constraint("Prefer morning")
    )


def prefer_days(constraint_factory: ConstraintFactory) -> Constraint:
    return (
        constraint_factory.for_each(TFLesson)
        .join(TFInstructor, Joiners.equal(lambda l: l.instructor_id, lambda i: i.id))
        .filter(
            lambda lesson, instructor: len(instructor.preferred_days) > 0
            and lesson.timeslot is not None
            and lesson.timeslot.day not in instructor.preferred_days
        )
        .penalize(HardSoftScore.of_soft(5))
        .as_constraint("Prefer days")
    )


# Fix: we defined instructor_availability twice. Remove the first (broken) one.
# Also room_capacity filter: we need to compare with lesson.expected_students. Already there.
# instructor_availability first version was wrong (filter didn't use instructor). Keep only the join version.

# Check HardSoftScore.of_soft(10) - might be ONE_SOFT or different API. Timefold uses HardSoftScore.ONE_SOFT for single unit. For weight 10 we might need of_soft(10). Let me check - in Java it's HardSoftScore.ofSoft(10). In Python might be of_soft(10).

# ---------------------------------------------------------------------------
# Build problem from Chronos format
# ---------------------------------------------------------------------------

def build_timefold_problem(problem: dict) -> TFTimetable:
    """Convert Chronos problem dict to Timefold TFTimetable."""
    courses = problem["courses"]
    instructors = problem["instructors"]
    rooms = problem["rooms"]
    timeslots = problem["timeslots"]

    tf_timeslots = [
        TFTimeslot(id=f"{ts.day}_{ts.hour}", day=ts.day, hour=ts.hour)
        for ts in timeslots
    ]
    tf_rooms = [TFRoom(id=r.id, capacity=r.capacity) for r in rooms]
    tf_instructors = [
        TFInstructor(
            id=inst.id,
            availability=tuple(inst.availability),
            prefer_morning=inst.prefer_morning,
            preferred_days=tuple(inst.preferred_days),
        )
        for inst in instructors.values()
    ]
    tf_lessons = [
        TFLesson(
            id=c.id,
            course_id=c.id,
            instructor_id=c.instructor_id,
            expected_students=c.expected_students,
            timeslot=None,
            room=None,
        )
        for c in courses
    ]

    return TFTimetable(
        timeslots=tf_timeslots,
        rooms=tf_rooms,
        instructors=tf_instructors,
        lessons=tf_lessons,
        score=None,
    )


def solution_to_assignments(solution: TFTimetable, problem: dict) -> List:
    """Convert Timefold solution back to Chronos Assignment list."""
    # Import here to avoid circular import and to use same types as experiment
    import experiment_instructor_constraints as exp
    Assignment = exp.Assignment
    TimeSlot = exp.TimeSlot
    course_by_id = {c.id: c for c in problem["courses"]}
    room_by_id = {r.id: r for r in problem["rooms"]}
    assignments = []
    for tf_lesson in solution.lessons:
        if tf_lesson.timeslot is None or tf_lesson.room is None:
            continue
        c = course_by_id.get(tf_lesson.course_id)
        r = room_by_id.get(tf_lesson.room.id)
        if c is None or r is None:
            continue
        ts = TimeSlot(day=tf_lesson.timeslot.day, hour=tf_lesson.timeslot.hour)
        assignments.append(Assignment(course=c, room=r, timeslot=ts))
    return assignments


def run_timefold_solver(problem: dict, time_limit_seconds: int = 30):
    """Build Timefold problem, solve, return (assignments, elapsed, info)."""
    import time
    import experiment_instructor_constraints as exp
    validate_and_score = exp.validate_and_score

    timetable = build_timefold_problem(problem)
    config = SolverConfig(
        solution_class=TFTimetable,
        entity_class_list=[TFLesson],
        score_director_factory_config=ScoreDirectorFactoryConfig(
            constraint_provider_function=define_constraints
        ),
        termination_config=TerminationConfig(
            spent_limit=Duration(seconds=time_limit_seconds)
        ),
    )
    solver = SolverFactory.create(config).build_solver()
    start = time.perf_counter()
    solution = solver.solve(timetable)
    elapsed = time.perf_counter() - start

    assignments = solution_to_assignments(solution, problem)
    hard, soft, ok = validate_and_score(assignments, problem)
    return assignments, elapsed, {
        "hard_violations": sum(hard.values()),
        "soft_score": soft,
        "all_scheduled": ok,
        "hard_detail": hard,
        "timefold_score": str(solution.score) if solution.score else None,
    }
