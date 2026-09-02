"""
Visualize Generated Timetable
Shows the actual schedule output from OR-Tools in a readable format

Author: Aung Moe Lin
Project: Chronos - Automated Timetabling Solution
"""

import sys
from scheduling_comparison_hard import (
    TimetablingProblemHard,
    solve_with_ortools,
    TimeSlot
)
from collections import defaultdict


def visualize_schedule(problem, assignments):
    """Create a visual timetable"""
    
    print("=" * 120)
    print("GENERATED TIMETABLE - CHRONOS AUTOMATED SCHEDULING SYSTEM")
    print("=" * 120)
    print()
    
    # Organize by room
    room_schedules = defaultdict(lambda: defaultdict(list))
    
    for assignment in assignments:
        room_id = assignment.room.id
        ts = assignment.timeslot
        room_schedules[room_id][(ts.day, ts.hour)].append(assignment)
    
    # Print room-by-room schedule
    for room in sorted(problem.rooms, key=lambda r: r.id):
        print(f"\n{'=' * 120}")
        print(f"ROOM: {room.id} (Capacity: {room.capacity})")
        print(f"{'=' * 120}")
        print()
        
        # Create header
        days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']
        hours = list(range(9, 14))  # 9am-2pm
        
        # Print header
        print(f"{'Time':<12}", end='')
        for day in days:
            print(f"{day:<22}", end='')
        print()
        print("-" * 120)
        
        # Print schedule
        for hour in hours:
            print(f"{hour:02d}:00-{hour+1:02d}:00  ", end='')
            
            for day_idx in range(5):
                assignments_in_slot = room_schedules[room.id].get((day_idx, hour), [])
                
                if assignments_in_slot:
                    assignment = assignments_in_slot[0]
                    course_info = f"{assignment.course.id[:6]}"
                    print(f"{course_info:<22}", end='')
                else:
                    print(f"{'---':<22}", end='')
            print()
    
    print()
    print("=" * 120)
    print("INSTRUCTOR SCHEDULE")
    print("=" * 120)
    print()
    
    # Organize by instructor
    instructor_schedules = defaultdict(list)
    for assignment in assignments:
        instructor_schedules[assignment.course.instructor].append(assignment)
    
    for instructor in sorted(instructor_schedules.keys()):
        print(f"\n{instructor}:")
        courses = instructor_schedules[instructor]
        
        # Sort by day then hour
        courses.sort(key=lambda a: (a.timeslot.day, a.timeslot.hour))
        
        for assignment in courses:
            days = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri']
            day_str = days[assignment.timeslot.day]
            hour = assignment.timeslot.hour
            
            print(f"  • {assignment.course.id:<8} {assignment.course.name:<35} "
                  f"| {day_str} {hour:02d}:00-{hour+1:02d}:00 | Room {assignment.room.id} "
                  f"| {assignment.course.students} students")
    
    print()
    print("=" * 120)
    print("COURSE DETAILS")
    print("=" * 120)
    print()
    
    print(f"{'Course ID':<10} {'Course Name':<35} {'Instructor':<20} {'Day/Time':<20} {'Room':<8} {'Students'}")
    print("-" * 120)
    
    # Sort all assignments by course ID
    sorted_assignments = sorted(assignments, key=lambda a: a.course.id)
    
    for assignment in sorted_assignments:
        days = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri']
        day_str = days[assignment.timeslot.day]
        hour = assignment.timeslot.hour
        time_str = f"{day_str} {hour:02d}:00"
        
        print(f"{assignment.course.id:<10} {assignment.course.name:<35} "
              f"{assignment.course.instructor:<20} {time_str:<20} "
              f"{assignment.room.id:<8} {assignment.course.students}")
    
    print()
    print("=" * 120)
    print("STATISTICS")
    print("=" * 120)
    print()
    
    # Calculate statistics
    print(f"Total Courses Scheduled: {len(assignments)}")
    print(f"Total Instructors: {len(instructor_schedules)}")
    print(f"Total Rooms Used: {len(set(a.room.id for a in assignments))}")
    print()
    
    # Room utilization
    total_slots = 5 * 5  # 5 days x 5 hours
    print("Room Utilization:")
    for room in problem.rooms:
        used_slots = len([a for a in assignments if a.room.id == room.id])
        utilization = (used_slots / total_slots) * 100
        print(f"  • {room.id}: {used_slots}/{total_slots} slots ({utilization:.1f}% utilized)")
    
    print()
    
    # Instructor workload
    print("Instructor Workload (hours per week):")
    for instructor, courses in sorted(instructor_schedules.items()):
        hours = sum(c.course.duration for c in courses)
        print(f"  • {instructor}: {hours} hours ({len(courses)} courses)")
    
    print()
    print("=" * 120)
    print("✓ SCHEDULE GENERATED SUCCESSFULLY - ZERO CONFLICTS")
    print("=" * 120)


def main():
    """Main function"""
    
    print("Generating optimal timetable using Google OR-Tools...")
    print()
    
    # Create problem
    problem = TimetablingProblemHard()
    
    # Solve with OR-Tools
    assignments, elapsed_time, stats = solve_with_ortools(problem, time_limit=15)
    
    if stats.get('success'):
        print(f"✓ Solution found in {elapsed_time:.4f} seconds")
        print()
        
        # Visualize
        visualize_schedule(problem, assignments)
    else:
        print(f"✗ Failed to find solution")
        print(f"Status: {stats.get('status')}")
        sys.exit(1)


if __name__ == "__main__":
    main()
