"""
Comparative Experiment: Scheduling Algorithms for Academic Timetabling
Compares Google OR-Tools vs. Alternative Approaches

Author: Aung Moe Lin
Project: Chronos - Automated Timetabling Solution
"""

import time
import random
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass
from collections import defaultdict

# Try to import OR-Tools (will handle if not installed)
try:
    from ortools.sat.python import cp_model
    ORTOOLS_AVAILABLE = True
except ImportError:
    ORTOOLS_AVAILABLE = False
    print("⚠️  Google OR-Tools not installed. Install with: pip install ortools")


@dataclass
class Course:
    """Represents a course to be scheduled"""
    id: str
    name: str
    instructor: str
    duration: int  # in hours
    students: int


@dataclass
class Room:
    """Represents a classroom"""
    id: str
    capacity: int


@dataclass
class TimeSlot:
    """Represents a time slot (day, hour)"""
    day: int  # 0-4 (Mon-Fri)
    hour: int  # 8-17 (8am-5pm)
    
    def __hash__(self):
        return hash((self.day, self.hour))
    
    def __eq__(self, other):
        return self.day == other.day and self.hour == other.hour
    
    def __repr__(self):
        days = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri']
        return f"{days[self.day]} {self.hour}:00"


@dataclass
class Assignment:
    """Represents a scheduled course"""
    course: Course
    room: Room
    timeslot: TimeSlot


class TimetablingProblem:
    """Defines the timetabling problem instance"""
    
    def __init__(self):
        # Generate test data
        self.courses = [
            Course("CS101", "Intro to Programming", "Dr. Smith", 3, 60),
            Course("CS102", "Data Structures", "Dr. Smith", 3, 50),
            Course("CS201", "Algorithms", "Dr. Johnson", 3, 45),
            Course("CS202", "Database Systems", "Dr. Brown", 3, 40),
            Course("CS301", "Software Engineering", "Dr. Johnson", 3, 35),
            Course("CS302", "Web Development", "Dr. Davis", 3, 55),
            Course("CS401", "AI Fundamentals", "Dr. Brown", 3, 30),
            Course("CS402", "Machine Learning", "Dr. Wilson", 3, 25),
            Course("MATH201", "Discrete Math", "Dr. Taylor", 3, 50),
            Course("MATH301", "Linear Algebra", "Dr. Taylor", 3, 40),
        ]
        
        self.rooms = [
            Room("R101", 70),
            Room("R102", 60),
            Room("R103", 50),
            Room("R104", 40),
        ]
        
        # Generate all possible timeslots (Mon-Fri, 8am-5pm)
        self.timeslots = []
        for day in range(5):  # Mon-Fri
            for hour in range(8, 17):  # 8am-5pm
                self.timeslots.append(TimeSlot(day, hour))
    
    def validate_schedule(self, assignments: List[Assignment]) -> Tuple[bool, Dict[str, int]]:
        """
        Validate a schedule against hard constraints
        Returns: (is_valid, constraint_violations)
        """
        violations = defaultdict(int)
        
        # Check 1: No instructor teaching two courses at same time
        instructor_schedule = defaultdict(list)
        for assignment in assignments:
            key = (assignment.course.instructor, assignment.timeslot)
            instructor_schedule[key].append(assignment.course.id)
        
        for key, courses in instructor_schedule.items():
            if len(courses) > 1:
                violations['instructor_conflict'] += len(courses) - 1
        
        # Check 2: No room double-booking
        room_schedule = defaultdict(list)
        for assignment in assignments:
            key = (assignment.room.id, assignment.timeslot)
            room_schedule[key].append(assignment.course.id)
        
        for key, courses in room_schedule.items():
            if len(courses) > 1:
                violations['room_conflict'] += len(courses) - 1
        
        # Check 3: Room capacity
        for assignment in assignments:
            if assignment.course.students > assignment.room.capacity:
                violations['capacity_violation'] += 1
        
        # Check 4: All courses scheduled
        scheduled_courses = {a.course.id for a in assignments}
        total_courses = {c.id for c in self.courses}
        missing = total_courses - scheduled_courses
        violations['missing_courses'] = len(missing)
        
        is_valid = sum(violations.values()) == 0
        return is_valid, dict(violations)


# ============================================================================
# Algorithm 1: Google OR-Tools (Constraint Programming)
# ============================================================================

def solve_with_ortools(problem: TimetablingProblem, time_limit: int = 30) -> Tuple[Optional[List[Assignment]], float, Dict]:
    """Solve using Google OR-Tools CP-SAT solver"""
    
    if not ORTOOLS_AVAILABLE:
        return None, 0, {"error": "OR-Tools not installed"}
    
    start_time = time.time()
    
    model = cp_model.CpModel()
    
    # Decision variables: x[c, r, t] = 1 if course c is in room r at time t
    x = {}
    for course in problem.courses:
        for room in problem.rooms:
            for timeslot in problem.timeslots:
                x[(course.id, room.id, timeslot)] = model.NewBoolVar(
                    f'x_{course.id}_{room.id}_{timeslot.day}_{timeslot.hour}'
                )
    
    # Constraint 1: Each course must be scheduled exactly once
    for course in problem.courses:
        model.Add(
            sum(x[(course.id, room.id, ts)] 
                for room in problem.rooms 
                for ts in problem.timeslots) == 1
        )
    
    # Constraint 2: No instructor teaches two courses at the same time
    for instructor in set(c.instructor for c in problem.courses):
        instructor_courses = [c for c in problem.courses if c.instructor == instructor]
        for ts in problem.timeslots:
            model.Add(
                sum(x[(c.id, r.id, ts)] 
                    for c in instructor_courses 
                    for r in problem.rooms) <= 1
            )
    
    # Constraint 3: No room can have two courses at the same time
    for room in problem.rooms:
        for ts in problem.timeslots:
            model.Add(
                sum(x[(c.id, room.id, ts)] 
                    for c in problem.courses) <= 1
            )
    
    # Constraint 4: Room capacity must be sufficient
    for course in problem.courses:
        for room in problem.rooms:
            if course.students > room.capacity:
                for ts in problem.timeslots:
                    model.Add(x[(course.id, room.id, ts)] == 0)
    
    # Solve
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = time_limit
    status = solver.Solve(model)
    
    elapsed_time = time.time() - start_time
    
    # Extract solution
    assignments = []
    if status in [cp_model.OPTIMAL, cp_model.FEASIBLE]:
        for course in problem.courses:
            for room in problem.rooms:
                for ts in problem.timeslots:
                    if solver.Value(x[(course.id, room.id, ts)]) == 1:
                        assignments.append(Assignment(course, room, ts))
        
        is_valid, violations = problem.validate_schedule(assignments)
        stats = {
            'success': True,
            'status': 'OPTIMAL' if status == cp_model.OPTIMAL else 'FEASIBLE',
            'violations': violations,
            'courses_scheduled': len(assignments)
        }
    else:
        stats = {
            'success': False,
            'status': 'INFEASIBLE',
            'violations': {},
            'courses_scheduled': 0
        }
        assignments = None
    
    return assignments, elapsed_time, stats


# ============================================================================
# Algorithm 2: Greedy Algorithm
# ============================================================================

def solve_with_greedy(problem: TimetablingProblem) -> Tuple[Optional[List[Assignment]], float, Dict]:
    """Solve using a simple greedy heuristic"""
    
    start_time = time.time()
    
    assignments = []
    used_slots = set()  # (room_id, timeslot)
    instructor_slots = set()  # (instructor, timeslot)
    
    # Sort courses by student count (descending) - schedule larger classes first
    sorted_courses = sorted(problem.courses, key=lambda c: c.students, reverse=True)
    
    for course in sorted_courses:
        scheduled = False
        
        # Try to find a valid slot
        for ts in problem.timeslots:
            # Check instructor availability
            if (course.instructor, ts) in instructor_slots:
                continue
            
            # Try to find an available room with sufficient capacity
            for room in sorted(problem.rooms, key=lambda r: r.capacity):
                if room.capacity < course.students:
                    continue
                
                if (room.id, ts) not in used_slots:
                    # Found a valid assignment
                    assignments.append(Assignment(course, room, ts))
                    used_slots.add((room.id, ts))
                    instructor_slots.add((course.instructor, ts))
                    scheduled = True
                    break
            
            if scheduled:
                break
    
    elapsed_time = time.time() - start_time
    
    is_valid, violations = problem.validate_schedule(assignments)
    stats = {
        'success': is_valid,
        'violations': violations,
        'courses_scheduled': len(assignments)
    }
    
    return assignments if assignments else None, elapsed_time, stats


# ============================================================================
# Algorithm 3: Backtracking Algorithm
# ============================================================================

def solve_with_backtracking(problem: TimetablingProblem, time_limit: int = 30) -> Tuple[Optional[List[Assignment]], float, Dict]:
    """Solve using backtracking with constraint checking"""
    
    start_time = time.time()
    
    def is_valid_assignment(course: Course, room: Room, ts: TimeSlot, 
                           current_assignments: List[Assignment]) -> bool:
        """Check if assignment violates any constraint"""
        
        # Check room capacity
        if course.students > room.capacity:
            return False
        
        # Check conflicts with existing assignments
        for existing in current_assignments:
            # Same instructor at same time
            if existing.course.instructor == course.instructor and existing.timeslot == ts:
                return False
            
            # Same room at same time
            if existing.room.id == room.id and existing.timeslot == ts:
                return False
        
        return True
    
    def backtrack(course_idx: int, assignments: List[Assignment]) -> Optional[List[Assignment]]:
        """Recursive backtracking"""
        
        # Check time limit
        if time.time() - start_time > time_limit:
            return None
        
        # Base case: all courses scheduled
        if course_idx == len(problem.courses):
            return assignments.copy()
        
        course = problem.courses[course_idx]
        
        # Try each combination of room and timeslot
        for room in problem.rooms:
            for ts in problem.timeslots:
                if is_valid_assignment(course, room, ts, assignments):
                    # Make assignment
                    assignments.append(Assignment(course, room, ts))
                    
                    # Recurse
                    result = backtrack(course_idx + 1, assignments)
                    if result is not None:
                        return result
                    
                    # Backtrack
                    assignments.pop()
        
        return None
    
    result = backtrack(0, [])
    elapsed_time = time.time() - start_time
    
    if result:
        is_valid, violations = problem.validate_schedule(result)
        stats = {
            'success': True,
            'violations': violations,
            'courses_scheduled': len(result)
        }
    else:
        stats = {
            'success': False,
            'violations': {},
            'courses_scheduled': 0,
            'reason': 'timeout' if elapsed_time >= time_limit else 'no solution found'
        }
    
    return result, elapsed_time, stats


# ============================================================================
# Algorithm 4: Random Assignment (Baseline)
# ============================================================================

def solve_with_random(problem: TimetablingProblem, attempts: int = 1000) -> Tuple[Optional[List[Assignment]], float, Dict]:
    """Solve using random assignment (baseline)"""
    
    start_time = time.time()
    
    best_assignments = None
    best_violation_count = float('inf')
    
    for _ in range(attempts):
        assignments = []
        
        for course in problem.courses:
            room = random.choice(problem.rooms)
            ts = random.choice(problem.timeslots)
            assignments.append(Assignment(course, room, ts))
        
        is_valid, violations = problem.validate_schedule(assignments)
        total_violations = sum(violations.values())
        
        if total_violations < best_violation_count:
            best_violation_count = total_violations
            best_assignments = assignments
        
        if is_valid:
            break
    
    elapsed_time = time.time() - start_time
    
    is_valid, violations = problem.validate_schedule(best_assignments)
    stats = {
        'success': is_valid,
        'violations': violations,
        'courses_scheduled': len(best_assignments),
        'attempts': attempts
    }
    
    return best_assignments, elapsed_time, stats


# ============================================================================
# Main Comparison
# ============================================================================

def run_comparison():
    """Run all algorithms and compare results"""
    
    print("=" * 80)
    print("SCHEDULING ALGORITHMS COMPARISON EXPERIMENT")
    print("Project: Chronos - Automated Timetabling Solution")
    print("=" * 80)
    print()
    
    # Create problem instance
    problem = TimetablingProblem()
    
    print(f"Problem Size:")
    print(f"  - Courses: {len(problem.courses)}")
    print(f"  - Instructors: {len(set(c.instructor for c in problem.courses))}")
    print(f"  - Rooms: {len(problem.rooms)}")
    print(f"  - Time Slots: {len(problem.timeslots)}")
    print(f"  - Search Space: ~{len(problem.rooms) * len(problem.timeslots) ** len(problem.courses):,.0f} combinations")
    print()
    print("=" * 80)
    print()
    
    algorithms = [
        ("Google OR-Tools (CP-SAT)", lambda: solve_with_ortools(problem, time_limit=10)),
        ("Greedy Algorithm", lambda: solve_with_greedy(problem)),
        ("Backtracking", lambda: solve_with_backtracking(problem, time_limit=10)),
        ("Random Assignment", lambda: solve_with_random(problem, attempts=1000)),
    ]
    
    results = []
    
    for name, solver in algorithms:
        print(f"Running: {name}...")
        
        try:
            assignments, elapsed_time, stats = solver()
            
            results.append({
                'name': name,
                'assignments': assignments,
                'time': elapsed_time,
                'stats': stats
            })
            
            print(f"✓ Completed in {elapsed_time:.4f} seconds")
            print()
            
        except Exception as e:
            print(f"✗ Error: {e}")
            print()
            results.append({
                'name': name,
                'assignments': None,
                'time': 0,
                'stats': {'success': False, 'error': str(e)}
            })
    
    # Display comparison table
    print("=" * 80)
    print("RESULTS SUMMARY")
    print("=" * 80)
    print()
    
    header = f"{'Algorithm':<30} {'Success':<10} {'Time (s)':<12} {'Violations':<15} {'Scheduled'}"
    print(header)
    print("-" * len(header))
    
    for result in results:
        name = result['name']
        stats = result['stats']
        success = "✓ Yes" if stats.get('success', False) else "✗ No"
        elapsed = f"{result['time']:.4f}"
        violations = sum(stats.get('violations', {}).values())
        scheduled = stats.get('courses_scheduled', 0)
        
        print(f"{name:<30} {success:<10} {elapsed:<12} {violations:<15} {scheduled}/{len(problem.courses)}")
    
    print()
    print("=" * 80)
    print("DETAILED ANALYSIS")
    print("=" * 80)
    print()
    
    for result in results:
        print(f"{result['name']}:")
        stats = result['stats']
        
        if stats.get('success'):
            print(f"  ✓ Successfully scheduled all {stats['courses_scheduled']} courses")
            print(f"  ✓ Zero constraint violations")
            print(f"  ⏱  Execution time: {result['time']:.4f} seconds")
        else:
            print(f"  ✗ Failed to find valid solution")
            if 'violations' in stats and stats['violations']:
                print(f"  Constraint violations:")
                for violation_type, count in stats['violations'].items():
                    print(f"    - {violation_type}: {count}")
            print(f"  Courses scheduled: {stats.get('courses_scheduled', 0)}/{len(problem.courses)}")
            print(f"  ⏱  Execution time: {result['time']:.4f} seconds")
        
        print()
    
    print("=" * 80)
    print("CONCLUSION")
    print("=" * 80)
    print()
    
    if ORTOOLS_AVAILABLE:
        ortools_result = results[0]
        if ortools_result['stats'].get('success'):
            print("✓ Google OR-Tools successfully solved the problem optimally")
            print("✓ All hard constraints satisfied")
            print(f"✓ Fast execution time: {ortools_result['time']:.4f} seconds")
            print()
            print("Why OR-Tools is the best choice:")
            print("  1. Guarantees constraint satisfaction (no conflicts)")
            print("  2. Fast solving time even for complex problems")
            print("  3. Scales to larger problem sizes")
            print("  4. Supports both hard and soft constraints")
            print("  5. Industry-standard tool with excellent documentation")
            print("  6. Can optimize for preferences (minimize violations of soft constraints)")
    else:
        print("⚠️  Install OR-Tools to see full comparison: pip install ortools")


if __name__ == "__main__":
    run_comparison()
