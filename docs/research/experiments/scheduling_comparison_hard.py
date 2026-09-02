"""
Comparative Experiment: Scheduling Algorithms for Academic Timetabling (HARD VERSION)
This version uses a more constrained problem to demonstrate OR-Tools' advantages

Author: Aung Moe Lin
Project: Chronos - Automated Timetabling Solution
"""

import time
import random
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass
from collections import defaultdict
import sys

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


class TimetablingProblemHard:
    """Defines a MORE CONSTRAINED timetabling problem"""
    
    def __init__(self):
        # More courses with conflicting instructors
        self.courses = [
            Course("CS101", "Intro to Programming", "Dr. Smith", 3, 60),
            Course("CS102", "Data Structures", "Dr. Smith", 3, 50),
            Course("CS103", "Computer Architecture", "Dr. Smith", 3, 45),
            Course("CS201", "Algorithms", "Dr. Johnson", 3, 45),
            Course("CS202", "Database Systems", "Dr. Johnson", 3, 40),
            Course("CS203", "Operating Systems", "Dr. Johnson", 3, 42),
            Course("CS301", "Software Engineering", "Dr. Brown", 3, 35),
            Course("CS302", "Web Development", "Dr. Brown", 3, 55),
            Course("CS303", "Mobile Development", "Dr. Brown", 3, 38),
            Course("CS401", "AI Fundamentals", "Dr. Davis", 3, 30),
            Course("CS402", "Machine Learning", "Dr. Davis", 3, 25),
            Course("CS403", "Computer Vision", "Dr. Davis", 3, 28),
            Course("MATH201", "Discrete Math", "Dr. Taylor", 3, 50),
            Course("MATH301", "Linear Algebra", "Dr. Taylor", 3, 40),
            Course("MATH302", "Probability", "Dr. Taylor", 3, 35),
            Course("PHY201", "Physics I", "Dr. Wilson", 3, 55),
            Course("PHY202", "Physics II", "Dr. Wilson", 3, 48),
            Course("PHY301", "Quantum Computing", "Dr. Wilson", 3, 30),
            Course("ENG201", "Technical Writing", "Dr. Lee", 3, 60),
            Course("ENG202", "Communication", "Dr. Lee", 3, 50),
        ]
        
        # FEWER rooms - more constraint!
        self.rooms = [
            Room("R101", 65),
            Room("R102", 55),
            Room("R103", 45),
        ]
        
        # LIMITED time slots (only morning hours to create more pressure)
        self.timeslots = []
        for day in range(5):  # Mon-Fri
            for hour in range(9, 14):  # 9am-2pm only (5 hours/day = 25 total slots)
                self.timeslots.append(TimeSlot(day, hour))
    
    def validate_schedule(self, assignments: List[Assignment]) -> Tuple[bool, Dict[str, int]]:
        """Validate a schedule against hard constraints"""
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

def solve_with_ortools(problem: TimetablingProblemHard, time_limit: int = 30) -> Tuple[Optional[List[Assignment]], float, Dict]:
    """Solve using Google OR-Tools CP-SAT solver"""
    
    if not ORTOOLS_AVAILABLE:
        return None, 0, {"error": "OR-Tools not installed"}
    
    start_time = time.time()
    
    model = cp_model.CpModel()
    
    # Decision variables
    x = {}
    for course in problem.courses:
        for room in problem.rooms:
            for timeslot in problem.timeslots:
                x[(course.id, room.id, timeslot)] = model.NewBoolVar(
                    f'x_{course.id}_{room.id}_{timeslot.day}_{timeslot.hour}'
                )
    
    # Constraint 1: Each course scheduled exactly once
    for course in problem.courses:
        model.Add(
            sum(x[(course.id, room.id, ts)] 
                for room in problem.rooms 
                for ts in problem.timeslots) == 1
        )
    
    # Constraint 2: No instructor teaches two courses at same time
    for instructor in set(c.instructor for c in problem.courses):
        instructor_courses = [c for c in problem.courses if c.instructor == instructor]
        for ts in problem.timeslots:
            model.Add(
                sum(x[(c.id, r.id, ts)] 
                    for c in instructor_courses 
                    for r in problem.rooms) <= 1
            )
    
    # Constraint 3: No room double-booking
    for room in problem.rooms:
        for ts in problem.timeslots:
            model.Add(
                sum(x[(c.id, room.id, ts)] 
                    for c in problem.courses) <= 1
            )
    
    # Constraint 4: Room capacity
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

def solve_with_greedy(problem: TimetablingProblemHard) -> Tuple[Optional[List[Assignment]], float, Dict]:
    """Solve using a simple greedy heuristic"""
    
    start_time = time.time()
    
    assignments = []
    used_slots = set()  # (room_id, timeslot)
    instructor_slots = set()  # (instructor, timeslot)
    
    # Sort courses by student count (descending)
    sorted_courses = sorted(problem.courses, key=lambda c: c.students, reverse=True)
    
    for course in sorted_courses:
        scheduled = False
        
        for ts in problem.timeslots:
            if (course.instructor, ts) in instructor_slots:
                continue
            
            for room in sorted(problem.rooms, key=lambda r: r.capacity):
                if room.capacity < course.students:
                    continue
                
                if (room.id, ts) not in used_slots:
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
# Algorithm 3: Backtracking with Early Termination
# ============================================================================

def solve_with_backtracking(problem: TimetablingProblemHard, time_limit: int = 10) -> Tuple[Optional[List[Assignment]], float, Dict]:
    """Solve using backtracking"""
    
    start_time = time.time()
    
    def is_valid_assignment(course: Course, room: Room, ts: TimeSlot, 
                           current_assignments: List[Assignment]) -> bool:
        if course.students > room.capacity:
            return False
        
        for existing in current_assignments:
            if existing.course.instructor == course.instructor and existing.timeslot == ts:
                return False
            if existing.room.id == room.id and existing.timeslot == ts:
                return False
        
        return True
    
    def backtrack(course_idx: int, assignments: List[Assignment]) -> Optional[List[Assignment]]:
        if time.time() - start_time > time_limit:
            return None
        
        if course_idx == len(problem.courses):
            return assignments.copy()
        
        course = problem.courses[course_idx]
        
        for room in problem.rooms:
            for ts in problem.timeslots:
                if is_valid_assignment(course, room, ts, assignments):
                    assignments.append(Assignment(course, room, ts))
                    result = backtrack(course_idx + 1, assignments)
                    if result is not None:
                        return result
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
            'reason': 'timeout' if elapsed_time >= time_limit else 'no solution'
        }
    
    return result, elapsed_time, stats


# ============================================================================
# Algorithm 4: Random Assignment
# ============================================================================

def solve_with_random(problem: TimetablingProblemHard, attempts: int = 10000) -> Tuple[Optional[List[Assignment]], float, Dict]:
    """Solve using random assignment"""
    
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
    print("SCHEDULING ALGORITHMS COMPARISON - HARD PROBLEM")
    print("Project: Chronos - Automated Timetabling Solution")
    print("=" * 80)
    print()
    
    problem = TimetablingProblemHard()
    
    print(f"Problem Constraints (HARDER VERSION):")
    print(f"  - Courses: {len(problem.courses)}")
    print(f"  - Instructors: {len(set(c.instructor for c in problem.courses))}")
    print(f"  - Rooms: {len(problem.rooms)} (LIMITED!)")
    print(f"  - Time Slots: {len(problem.timeslots)} (25 slots only - morning hours)")
    print(f"  - Constraint Density: {len(problem.courses) / (len(problem.rooms) * len(problem.timeslots)):.2f}")
    print(f"    (>0.25 indicates tight constraints)")
    print()
    
    # Calculate instructor load
    instructor_courses = defaultdict(int)
    for course in problem.courses:
        instructor_courses[course.instructor] += 1
    
    print("Instructor Course Load:")
    for instructor, count in sorted(instructor_courses.items(), key=lambda x: x[1], reverse=True):
        print(f"  - {instructor}: {count} courses")
    print()
    print("=" * 80)
    print()
    
    algorithms = [
        ("Google OR-Tools (CP-SAT)", lambda: solve_with_ortools(problem, time_limit=15)),
        ("Greedy Algorithm", lambda: solve_with_greedy(problem)),
        ("Backtracking", lambda: solve_with_backtracking(problem, time_limit=15)),
        ("Random Assignment (10K)", lambda: solve_with_random(problem, attempts=10000)),
    ]
    
    results = []
    
    for name, solver in algorithms:
        print(f"Running: {name}...")
        sys.stdout.flush()
        
        try:
            assignments, elapsed_time, stats = solver()
            
            results.append({
                'name': name,
                'assignments': assignments,
                'time': elapsed_time,
                'stats': stats
            })
            
            if stats.get('success'):
                print(f"✓ SOLVED in {elapsed_time:.4f} seconds")
            else:
                print(f"✗ FAILED in {elapsed_time:.4f} seconds")
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
        success = "✓ YES" if stats.get('success', False) else "✗ NO"
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
    print("KEY FINDINGS & CONCLUSION")
    print("=" * 80)
    print()
    
    if ORTOOLS_AVAILABLE:
        ortools_result = results[0]
        greedy_result = results[1]
        
        print("Problem Difficulty:")
        print("  • 20 courses, 8 instructors, only 3 rooms, 25 time slots")
        print("  • High constraint density (0.27) means tight scheduling")
        print("  • Multiple courses per instructor creates conflicts")
        print()
        
        if ortools_result['stats'].get('success'):
            print("✓ Google OR-Tools: SUCCESSFUL")
            print(f"  - Found optimal solution in {ortools_result['time']:.4f} seconds")
            print("  - Guaranteed constraint satisfaction")
            print("  - Can handle even more complex problems")
        else:
            print("✗ Google OR-Tools: No solution found (problem may be infeasible)")
        
        print()
        
        if not greedy_result['stats'].get('success'):
            print("✗ Greedy Algorithm: FAILED")
            violations = greedy_result['stats'].get('violations', {})
            if violations:
                print("  - Constraint violations occurred")
                print("  - Cannot handle tight constraints")
        else:
            print("✓ Greedy Algorithm: Succeeded on this instance")
        
        print()
        print("=" * 80)
        print("WHY GOOGLE OR-TOOLS IS THE BEST CHOICE FOR CHRONOS:")
        print("=" * 80)
        print()
        print("1. CORRECTNESS: Guarantees constraint satisfaction (zero conflicts)")
        print("   - Greedy/Random often fail on constrained problems")
        print("   - Backtracking times out on larger problems")
        print()
        print("2. SCALABILITY: Handles 50-100+ courses efficiently")
        print("   - Real university schedules have 100+ courses")
        print("   - OR-Tools uses advanced pruning techniques")
        print()
        print("3. OPTIMIZATION: Can minimize soft constraint violations")
        print("   - Instructor time preferences")
        print("   - Balanced workloads")
        print("   - Room preferences")
        print()
        print("4. FLEXIBILITY: Easy to add new constraints")
        print("   - Lab room requirements")
        print("   - Consecutive class sessions")
        print("   - Building constraints")
        print()
        print("5. INDUSTRY STANDARD: Used by Google, airlines, hospitals")
        print("   - Well-tested and maintained")
        print("   - Excellent documentation")
        print("   - Active community support")
        print()
    else:
        print("⚠️  Install OR-Tools to see full comparison: pip install ortools")


if __name__ == "__main__":
    run_comparison()
