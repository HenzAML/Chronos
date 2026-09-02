"""
Experiment: Instructor Availability & Preference Constraints
Compares scheduling algorithms with real-world instructor constraints.

Author: Aung Moe Lin
Project: Chronos - Automated Timetabling Solution

=============================================================================
DEFINITIONS (Inputs, Outputs, Constraints)
=============================================================================

INPUTS:
-------
1. COURSES
   - course_id: str
   - name: str
   - instructor_id: str (references an instructor)
   - duration_hours: int (e.g. 1)
   - expected_students: int

2. INSTRUCTORS
   - instructor_id: str
   - name: str
   - availability: List[Tuple[day, hour]]  # HARD: only these (day, hour) slots are allowed
     Example: [(0,9), (0,10), (2,9), (2,10)] = "Only Mon 9-10 and Wed 9-10"
   - prefer_morning: bool  # SOFT: prefer hour < 12
   - preferred_days: List[int]  # SOFT: e.g. [1, 2] = Tue, Wed only preferred
   - preferred_slots: List[Tuple[day, hour]]  # SOFT: optional, preferred slots

3. ROOMS
   - room_id: str
   - capacity: int

4. TIME SLOTS
   - List of (day, hour): day 0=Mon..4=Fri, hour 8-17 (8am-5pm)

OUTPUTS:
--------
- schedule: List[Assignment] where Assignment = (course_id, room_id, day, hour)
- metrics:
  - hard_violations: int (must be 0 for feasible)
  - soft_score: int (lower is better; weighted sum of preference violations)
  - all_courses_scheduled: bool

HARD CONSTRAINTS (must be satisfied):
------------------------------------
H1. Each course is assigned exactly one (room, timeslot).
H2. No room is used by more than one course in the same timeslot.
H3. No instructor teaches more than one course in the same timeslot.
H4. Room capacity >= course expected_students for that assignment.
H5. INSTRUCTOR AVAILABILITY: A course can only be scheduled in a timeslot
    that is in its instructor's availability set. ("I'm only free at this time.")

SOFT CONSTRAINTS (minimize violations; preferences):
---------------------------------------------------
S1. PREFER MORNING: If instructor has prefer_morning=True, penalize if
    assigned hour >= 12.
S2. PREFER CERTAIN DAYS: If instructor has preferred_days, penalize if
    assigned day not in preferred_days (e.g. "I want only Tue and Wed").
S3. PREFER PREFERRED SLOTS: If instructor has preferred_slots, penalize
    distance from preferred (optional).
"""

import time
import random
from typing import List, Dict, Tuple, Optional, Set
from dataclasses import dataclass, field
from collections import defaultdict

# ---------------------------------------------------------------------------
# Try imports
# ---------------------------------------------------------------------------
try:
    from ortools.sat.python import cp_model
    ORTOOLS_AVAILABLE = True
except ImportError:
    ORTOOLS_AVAILABLE = False

# Timefold: use chronos_timefold bridge if available (requires: pip install from git + JDK 17)
TIMEFOLD_AVAILABLE = False
_TIMEFOLD_ERROR = "Timefold not installed"
try:
    import chronos_timefold as _tf
    if getattr(_tf, "TIMEFOLD_IMPORT_OK", False):
        TIMEFOLD_AVAILABLE = True
    else:
        _TIMEFOLD_ERROR = getattr(_tf, "_TIMEFOLD_IMPORT_ERROR", "Timefold not installed")
except ImportError as e:
    _TIMEFOLD_ERROR = str(e)
except Exception as e:
    _TIMEFOLD_ERROR = str(e)

# OptaPlanner is JVM-only; we document same problem for comparison
OPTAPLANNER_AVAILABLE = False  # Java only; same model as Timefold


# =============================================================================
# Data structures
# =============================================================================

@dataclass
class Course:
    id: str
    name: str
    instructor_id: str
    duration_hours: int
    expected_students: int


@dataclass
class Instructor:
    id: str
    name: str
    availability: List[Tuple[int, int]]  # (day, hour) - HARD: only these slots
    prefer_morning: bool = False         # SOFT
    preferred_days: List[int] = field(default_factory=list)   # e.g. [1,2] = Tue, Wed
    preferred_slots: List[Tuple[int, int]] = field(default_factory=list)  # SOFT optional


@dataclass
class Room:
    id: str
    capacity: int


@dataclass
class TimeSlot:
    day: int
    hour: int

    def __hash__(self):
        return hash((self.day, self.hour))

    def __eq__(self, other):
        if not isinstance(other, TimeSlot):
            return False
        return self.day == other.day and self.hour == other.hour

    def tuple(self):
        return (self.day, self.hour)


@dataclass
class Assignment:
    course: Course
    room: Room
    timeslot: TimeSlot


# =============================================================================
# Problem instance with instructor constraints
# =============================================================================

def build_problem(size="default"):
    """Build a problem instance with explicit instructor availability and preferences.
    size: 'default' (10 courses) or 'medium' (tighter preferences so soft scores differ).
    """
    # Time slots: Mon-Fri, 8am-5pm (9 hours per day)
    timeslots = []
    for day in range(5):
        for hour in range(8, 17):
            timeslots.append(TimeSlot(day, hour))

    # Instructors with AVAILABILITY (hard) and PREFERENCES (soft)
    # Some have limited availability so that not all preferred slots are feasible
    instructors = [
        Instructor(
            id="inst_smith",
            name="Dr. Smith",
            # Only free Mon 9-11, Wed 9-11 (no afternoon -> morning preference always satisfiable here)
            availability=[(0, 9), (0, 10), (0, 11), (2, 9), (2, 10), (2, 11)],
            prefer_morning=True,
            preferred_days=[0, 2],
        ),
        Instructor(
            id="inst_johnson",
            name="Dr. Johnson",
            # Tue/Thu 10-12 and 14-15 -> afternoon available; prefer morning
            availability=[(1, 10), (1, 11), (1, 12), (1, 14), (1, 15), (3, 10), (3, 11), (3, 12), (3, 14), (3, 15)],
            prefer_morning=True,
            preferred_days=[1, 3],
        ),
        Instructor(
            id="inst_brown",
            name="Dr. Brown",
            availability=[(d, h) for d in [1, 2] for h in range(9, 15)],
            prefer_morning=False,
            preferred_days=[1, 2],  # "I want only Tuesday and Wednesday"
        ),
        Instructor(
            id="inst_davis",
            name="Dr. Davis",
            # Some morning, some afternoon -> morning preference can be violated
            availability=[(d, h) for d in [0, 2, 4] for h in list(range(8, 12)) + list(range(13, 17))],
            prefer_morning=True,
            preferred_days=[0, 2, 4],
        ),
        Instructor(
            id="inst_taylor",
            name="Dr. Taylor",
            availability=[(d, h) for d in [3, 4] for h in range(9, 17)],
            prefer_morning=False,
            preferred_days=[3, 4],
        ),
    ]

    courses = [
        Course("CS101", "Intro to Programming", "inst_smith", 1, 60),
        Course("CS102", "Data Structures", "inst_smith", 1, 50),
        Course("CS201", "Algorithms", "inst_johnson", 1, 45),
        Course("CS202", "Database Systems", "inst_johnson", 1, 40),
        Course("CS301", "Software Engineering", "inst_brown", 1, 35),
        Course("CS302", "Web Development", "inst_brown", 1, 55),
        Course("CS401", "AI Fundamentals", "inst_davis", 1, 30),
        Course("CS402", "Machine Learning", "inst_davis", 1, 25),
        Course("MATH201", "Discrete Math", "inst_taylor", 1, 50),
        Course("MATH301", "Linear Algebra", "inst_taylor", 1, 40),
    ]

    rooms = [
        Room("R101", 70),
        Room("R102", 60),
        Room("R103", 50),
        Room("R104", 45),
    ]

    return {
        "courses": courses,
        "instructors": {i.id: i for i in instructors},
        "rooms": rooms,
        "timeslots": timeslots,
    }


# =============================================================================
# Validation and scoring
# =============================================================================

def check_hard_constraints(assignments: List[Assignment], instructors: Dict, rooms: List[Room]) -> Dict[str, int]:
    """Return violation counts for each hard constraint. All should be 0."""
    violations = defaultdict(int)

    # H1: each course once
    course_ids = [a.course.id for a in assignments]
    if len(course_ids) != len(set(course_ids)):
        violations["H1_duplicate_course"] = len(course_ids) - len(set(course_ids))

    # H2: no room double-book
    room_slots = defaultdict(list)
    for a in assignments:
        key = (a.room.id, a.timeslot.tuple())
        room_slots[key].append(a.course.id)
    for key, lst in room_slots.items():
        if len(lst) > 1:
            violations["H2_room_conflict"] += len(lst) - 1

    # H3: no instructor double-book
    inst_slots = defaultdict(list)
    for a in assignments:
        key = (a.course.instructor_id, a.timeslot.tuple())
        inst_slots[key].append(a.course.id)
    for key, lst in inst_slots.items():
        if len(lst) > 1:
            violations["H3_instructor_conflict"] += len(lst) - 1

    # H4: capacity
    for a in assignments:
        if a.course.expected_students > a.room.capacity:
            violations["H4_capacity"] += 1

    # H5: instructor availability
    for a in assignments:
        inst = instructors.get(a.course.instructor_id)
        if not inst:
            violations["H5_unknown_instructor"] += 1
        else:
            if a.timeslot.tuple() not in inst.availability:
                violations["H5_availability"] += 1

    return dict(violations)


def soft_score(assignments: List[Assignment], instructors: Dict) -> int:
    """Lower is better. Weighted sum of preference violations."""
    total = 0
    for a in assignments:
        inst = instructors.get(a.course.instructor_id)
        if not inst:
            continue
        day, hour = a.timeslot.day, a.timeslot.hour
        # S1: prefer morning (hour < 12)
        if inst.prefer_morning and hour >= 12:
            total += 10
        # S2: prefer certain days
        if inst.preferred_days and day not in inst.preferred_days:
            total += 5
        # S3: preferred_slots (if specified)
        if inst.preferred_slots and (day, hour) not in inst.preferred_slots:
            total += 2  # smaller weight
    return total


def validate_and_score(assignments: List[Assignment], problem: dict) -> Tuple[Dict[str, int], int, bool]:
    """Returns (hard_violations_dict, soft_score, all_courses_scheduled)."""
    instructors = problem["instructors"]
    rooms = problem["rooms"]
    course_ids = {c.id for c in problem["courses"]}
    scheduled_ids = {a.course.id for a in assignments}
    hard = check_hard_constraints(assignments, instructors, rooms)
    all_scheduled = scheduled_ids == course_ids and len(assignments) == len(problem["courses"])
    soft = soft_score(assignments, instructors) if assignments else 0
    return hard, soft, all_scheduled


# =============================================================================
# Algorithm 1: Google OR-Tools (CP-SAT)
# =============================================================================

def solve_ortools(problem: dict, time_limit_seconds: int = 30) -> Tuple[List[Assignment], float, dict]:
    """OR-Tools: hard constraints as constraints, soft as minimization objective."""
    if not ORTOOLS_AVAILABLE:
        return [], 0.0, {"error": "OR-Tools not installed"}

    courses = problem["courses"]
    instructors = problem["instructors"]
    rooms = problem["rooms"]
    timeslots = problem["timeslots"]

    model = cp_model.CpModel()
    # x[c, r, t] = 1 if course c in room r at timeslot t
    x = {}
    for c in courses:
        inst = instructors[c.instructor_id]
        allowed_slots = {ts.tuple() for ts in timeslots if ts.tuple() in inst.availability}
        for r in rooms:
            if c.expected_students > r.capacity:
                continue
            for ts in timeslots:
                if ts.tuple() not in allowed_slots:
                    continue
                x[(c.id, r.id, ts)] = model.NewBoolVar(f"x_{c.id}_{r.id}_{ts.day}_{ts.hour}")

    # H1: each course exactly once
    for c in courses:
        model.Add(sum(x.get((c.id, r.id, ts), 0) for r in rooms for ts in timeslots
                    if (c.id, r.id, ts) in x) == 1)

    # H2: room at most one per slot
    for r in rooms:
        for ts in timeslots:
            model.Add(sum(x.get((c.id, r.id, ts), 0) for c in courses if (c.id, r.id, ts) in x) <= 1)

    # H3: instructor at most one per slot
    for inst_id, inst in instructors.items():
        inst_courses = [c for c in courses if c.instructor_id == inst_id]
        for ts in timeslots:
            model.Add(sum(x.get((c.id, r.id, ts), 0) for c in inst_courses for r in rooms
                       if (c.id, r.id, ts) in x) <= 1)

    # Soft: minimize weighted violations (LinearExpr.WeightedSum for BoolVars)
    soft_vars = []
    soft_weights = []
    for c in courses:
        inst = instructors[c.instructor_id]
        for r in rooms:
            if c.expected_students > r.capacity:
                continue
            for ts in timeslots:
                if (c.id, r.id, ts) not in x:
                    continue
                penalty = 0
                if inst.prefer_morning and ts.hour >= 12:
                    penalty += 10
                if inst.preferred_days and ts.day not in inst.preferred_days:
                    penalty += 5
                if penalty > 0:
                    soft_vars.append(x[(c.id, r.id, ts)])
                    soft_weights.append(penalty)
    if soft_vars:
        model.Minimize(cp_model.LinearExpr.WeightedSum(soft_vars, soft_weights))
    else:
        model.Minimize(0)

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = time_limit_seconds
    start = time.perf_counter()
    status = solver.Solve(model)
    elapsed = time.perf_counter() - start

    assignments = []
    if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        for c in courses:
            for r in rooms:
                for ts in timeslots:
                    key = (c.id, r.id, ts)
                    if key in x and solver.Value(x[key]) == 1:
                        assignments.append(Assignment(course=c, room=r, timeslot=ts))
                        break
                else:
                    continue
                break

    hard, soft, ok = validate_and_score(assignments, problem)
    return assignments, elapsed, {
        "status": "OPTIMAL" if status == cp_model.OPTIMAL else "FEASIBLE" if status == cp_model.FEASIBLE else "INFEASIBLE",
        "hard_violations": sum(hard.values()),
        "soft_score": soft,
        "all_scheduled": ok,
        "hard_detail": hard,
    }


# =============================================================================
# Algorithm 2: Greedy (respect hard, minimize soft)
# =============================================================================

def solve_greedy(problem: dict) -> Tuple[List[Assignment], float, dict]:
    """Greedy: assign courses one by one, pick slot with lowest soft penalty among feasible."""
    courses = problem["courses"]
    instructors = problem["instructors"]
    rooms = problem["rooms"]
    timeslots = problem["timeslots"]

    used_room_slot = set()
    used_inst_slot = set()
    assignments = []

    start = time.perf_counter()
    # Sort by instructor load (spread)
    for c in courses:
        inst = instructors[c.instructor_id]
        best_a = None
        best_penalty = 1 << 30
        for ts in timeslots:
            if ts.tuple() not in inst.availability:
                continue
            if (c.instructor_id, ts.tuple()) in used_inst_slot:
                continue
            for r in rooms:
                if c.expected_students > r.capacity:
                    continue
                if (r.id, ts.tuple()) in used_room_slot:
                    continue
                penalty = 0
                if inst.prefer_morning and ts.hour >= 12:
                    penalty += 10
                if inst.preferred_days and ts.day not in inst.preferred_days:
                    penalty += 5
                if penalty < best_penalty:
                    best_penalty = penalty
                    best_a = (c, r, ts)
        if best_a is None:
            break
        c, r, ts = best_a
        assignments.append(Assignment(course=c, room=r, timeslot=ts))
        used_room_slot.add((r.id, ts.tuple()))
        used_inst_slot.add((c.instructor_id, ts.tuple()))

    elapsed = time.perf_counter() - start
    hard, soft, ok = validate_and_score(assignments, problem)
    return assignments, elapsed, {
        "hard_violations": sum(hard.values()),
        "soft_score": soft,
        "all_scheduled": ok,
        "hard_detail": hard,
    }


# =============================================================================
# Algorithm 3: Random (respect hard only, then score soft)
# =============================================================================

def solve_random(problem: dict, attempts: int = 500) -> Tuple[List[Assignment], float, dict]:
    """Random: repeatedly try random feasible assignment; keep best by soft score."""
    courses = problem["courses"]
    instructors = problem["instructors"]
    rooms = problem["rooms"]
    timeslots = problem["timeslots"]

    start = time.perf_counter()
    best_assignments = []
    best_soft = 1 << 30

    for _ in range(attempts):
        used_room_slot = set()
        used_inst_slot = set()
        assignments = []
        pool = []
        for c in courses:
            inst = instructors[c.instructor_id]
            for ts in timeslots:
                if ts.tuple() not in inst.availability:
                    continue
                for r in rooms:
                    if c.expected_students > r.capacity:
                        continue
                    pool.append((c, r, ts))
        random.shuffle(pool)
        used_c = set()
        for c, r, ts in pool:
            if c.id in used_c:
                continue
            if (r.id, ts.tuple()) in used_room_slot or (c.instructor_id, ts.tuple()) in used_inst_slot:
                continue
            assignments.append(Assignment(course=c, room=r, timeslot=ts))
            used_c.add(c.id)
            used_room_slot.add((r.id, ts.tuple()))
            used_inst_slot.add((c.instructor_id, ts.tuple()))

        if len(assignments) == len(courses):
            hard, soft, _ = validate_and_score(assignments, problem)
            if sum(hard.values()) == 0 and soft < best_soft:
                best_soft = soft
                best_assignments = list(assignments)

    elapsed = time.perf_counter() - start
    hard, soft, ok = validate_and_score(best_assignments, problem)
    return best_assignments, elapsed, {
        "hard_violations": sum(hard.values()),
        "soft_score": soft,
        "all_scheduled": ok,
        "hard_detail": hard,
        "attempts": attempts,
    }


# =============================================================================
# Algorithm 4: Timefold (if available) - stub for same interface
# =============================================================================

def solve_timefold(problem: dict, time_limit_seconds: int = 30) -> Tuple[List[Assignment], float, dict]:
    """Timefold Solver: same inputs/outputs; availability=hard, preferences=soft."""
    if not TIMEFOLD_AVAILABLE:
        return [], 0.0, {"error": _TIMEFOLD_ERROR or "Timefold not installed (pip install git+https://github.com/TimefoldAI/timefold-solver-python.git, JDK 17+)"}
    try:
        import chronos_timefold as _tf
        return _tf.run_timefold_solver(problem, time_limit_seconds=time_limit_seconds)
    except Exception as e:
        return [], 0.0, {"error": f"Timefold solve failed: {e}"}


# =============================================================================
# Algorithm 5: Backtracking (with availability)
# =============================================================================

def solve_backtracking(problem: dict, time_limit_seconds: int = 15) -> Tuple[List[Assignment], float, dict]:
    """Backtracking: exhaustive search respecting all hard constraints."""
    courses = problem["courses"]
    instructors = problem["instructors"]
    rooms = problem["rooms"]
    timeslots = problem["timeslots"]
    start = time.perf_counter()

    used_room_slot = set()
    used_inst_slot = set()

    def feasible(c, r, ts):
        if (r.id, ts.tuple()) in used_room_slot:
            return False
        if (c.instructor_id, ts.tuple()) in used_inst_slot:
            return False
        if ts.tuple() not in instructors[c.instructor_id].availability:
            return False
        if c.expected_students > r.capacity:
            return False
        return True

    result = []

    def backtrack(idx):
        if time.perf_counter() - start > time_limit_seconds:
            return False
        if idx == len(courses):
            return True
        c = courses[idx]
        inst = instructors[c.instructor_id]
        for ts in timeslots:
            if ts.tuple() not in inst.availability:
                continue
            for r in rooms:
                if not feasible(c, r, ts):
                    continue
                used_room_slot.add((r.id, ts.tuple()))
                used_inst_slot.add((c.instructor_id, ts.tuple()))
                result.append(Assignment(course=c, room=r, timeslot=ts))
                if backtrack(idx + 1):
                    return True
                result.pop()
                used_room_slot.discard((r.id, ts.tuple()))
                used_inst_slot.discard((c.instructor_id, ts.tuple()))
        return False

    backtrack(0)
    elapsed = time.perf_counter() - start
    hard, soft, ok = validate_and_score(result, problem)
    return result, elapsed, {
        "hard_violations": sum(hard.values()),
        "soft_score": soft,
        "all_scheduled": ok,
        "hard_detail": hard,
    }


# =============================================================================
# Run comparison
# =============================================================================

def run_experiment():
    problem = build_problem()
    n_courses = len(problem["courses"])
    n_slots = len(problem["timeslots"])
    n_rooms = len(problem["rooms"])

    print("=" * 70)
    print("EXPERIMENT: Instructor Availability & Preference Constraints")
    print("=" * 70)
    print()
    print("INPUTS:")
    print(f"  Courses: {n_courses}")
    print(f"  Instructors: {len(problem['instructors'])}")
    print(f"  Rooms: {n_rooms}")
    print(f"  Time slots: {n_slots}")
    print()
    print("HARD CONSTRAINTS: H1–H5 (availability = only free at certain times)")
    print("SOFT CONSTRAINTS: S1 prefer morning, S2 prefer certain days (e.g. Tue/Wed)")
    print()
    print("ALGORITHMS: OR-Tools, Timefold, Greedy, Random, Backtracking (OptaPlanner: JVM-only)")
    print("=" * 70)
    print()

    algorithms = [
        ("Google OR-Tools (CP-SAT)", lambda: solve_ortools(problem, time_limit_seconds=20)),
        ("Timefold Solver", lambda: solve_timefold(problem, time_limit_seconds=20)),
        ("Greedy (preference-aware)", lambda: solve_greedy(problem)),
        ("Random (best of 500)", lambda: solve_random(problem, attempts=500)),
        ("Backtracking", lambda: solve_backtracking(problem, time_limit_seconds=15)),
    ]

    results = []
    for name, fn in algorithms:
        print(f"Running {name}...")
        try:
            assignments, elapsed, info = fn()
        except Exception as e:
            assignments = []
            elapsed = 0.0
            info = {"error": str(e)}
        results.append((name, assignments, elapsed, info))
        sched = len(assignments) if assignments else 0
        err = info.get("error")
        if err:
            print(f"  -> skipped: {err[:70]}{'...' if len(str(err)) > 70 else ''}")
        else:
            print(f"  -> {sched} scheduled, hard={info.get('hard_violations', 'N/A')}, soft={info.get('soft_score', 'N/A')}, time={elapsed:.3f}s")
    print()

    # Table
    print("RESULTS SUMMARY")
    print("-" * 70)
    print(f"{'Algorithm':<30} {'Scheduled':<12} {'Hard Viol':<10} {'Soft Score':<12} {'Time(s)':<10}")
    print("-" * 70)
    for name, assignments, elapsed, info in results:
        sched = f"{len(assignments)}/{n_courses}"
        hard = info.get("hard_violations", "—")
        soft = info.get("soft_score", "—")
        print(f"{name:<30} {sched:<12} {str(hard):<10} {str(soft):<12} {elapsed:.3f}")
    print()
    print("(Soft score: lower is better; preferences better satisfied)")
    if not TIMEFOLD_AVAILABLE:
        print("(Timefold: install with pip install git+https://github.com/TimefoldAI/timefold-solver-python.git and JDK 17+)")
    print("(OptaPlanner: JVM-only; same model as Timefold)")
    return results


def run_scalability_table():
    """Run comparison for 10, 20, 40, 80 courses (scaled problem) and print table."""
    base = build_problem()
    algorithms = [
        ("OR-Tools", lambda p: solve_ortools(p, time_limit_seconds=30)),
        ("Timefold", lambda p: solve_timefold(p, time_limit_seconds=30)),
        ("Greedy", solve_greedy),
        ("Random (500)", lambda p: solve_random(p, attempts=500)),
        ("Backtracking", lambda p: solve_backtracking(p, time_limit_seconds=20)),
    ]
    sizes = [10, 20, 40, 80]
    # Scale by duplicating courses and adding instructors
    print("\n" + "=" * 70)
    print("SCALABILITY: Different problem sizes (courses)")
    print("=" * 70)
    print(f"{'Size':<8} {'Algorithm':<18} {'Scheduled':<12} {'Hard':<6} {'Soft':<8} {'Time(s)':<10}")
    print("-" * 70)
    for n in sizes:
        if n == 10:
            problem = base
        else:
            problem = scale_problem(base, n)
        for algo_name, fn in algorithms:
            try:
                assignments, elapsed, info = fn(problem)
                sched = f"{len(assignments)}/{n}"
                hard = info.get("hard_violations", "—")
                soft = info.get("soft_score", "—")
                print(f"{n:<8} {algo_name:<18} {sched:<12} {hard!s:<6} {soft!s:<8} {elapsed:.3f}")
            except Exception as e:
                print(f"{n:<8} {algo_name:<18} {'—':<12} {'—':<6} {'—':<8} {str(e)[:20]}")
    print()


def scale_problem(base: dict, target_courses: int) -> dict:
    """Scale problem to target_courses by duplicating courses and cloning instructors.
    Cloning instructors (same availability) keeps the problem feasible: otherwise
    at 40/80 courses the same 5 instructors don't have enough slots (e.g. Smith has only 6).
    """
    courses = list(base["courses"])
    instructors_orig = dict(base["instructors"])
    rooms = base["rooms"]
    timeslots = base["timeslots"]
    if target_courses <= len(courses):
        return {**base, "courses": courses[:target_courses]}

    # Clone instructors so we have enough instructor-slots (each clone has same availability)
    n_copies = max(1, (target_courses + 9) // 10)  # 10->1, 20->2, 40->4, 80->8
    instructors = {}
    for orig_id, inst in instructors_orig.items():
        for k in range(n_copies):
            iid = f"{orig_id}_{k}" if k > 0 else orig_id
            instructors[iid] = Instructor(
                id=iid,
                name=inst.name + (f" ({k})" if k > 0 else ""),
                availability=list(inst.availability),
                prefer_morning=inst.prefer_morning,
                preferred_days=list(inst.preferred_days),
                preferred_slots=list(inst.preferred_slots) if inst.preferred_slots else [],
            )
    inst_ids = list(instructors.keys())

    new_courses = list(courses)
    idx = 0
    while len(new_courses) < target_courses:
        c = courses[idx % len(courses)]
        inst_id = inst_ids[idx % len(inst_ids)]
        new_courses.append(Course(
            f"{c.id}_{len(new_courses)}", c.name + f" ({len(new_courses)})",
            inst_id, c.duration_hours, c.expected_students
        ))
        idx += 1
    return {
        "courses": new_courses[:target_courses],
        "instructors": instructors,
        "rooms": rooms,
        "timeslots": timeslots,
    }


if __name__ == "__main__":
    run_experiment()
    run_scalability_table()
