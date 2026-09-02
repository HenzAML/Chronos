# Scheduling Algorithms Comparison Experiment

## Purpose
This experiment compares Google OR-Tools with alternative scheduling approaches to justify the technology choice for the Chronos timetabling system.

## Algorithms Compared

### 1. Google OR-Tools (CP-SAT Solver)
- **Type**: Constraint Programming
- **Approach**: Systematic constraint satisfaction with optimization
- **Strengths**: Guarantees valid solutions, handles complex constraints, scalable

### 2. Greedy Algorithm
- **Type**: Heuristic
- **Approach**: Schedule courses one by one, choosing first available slot
- **Strengths**: Fast, simple
- **Weaknesses**: No guarantee of finding solution, poor quality

### 3. Backtracking Algorithm
- **Type**: Exhaustive Search
- **Approach**: Try all combinations with pruning
- **Strengths**: Complete (finds solution if exists)
- **Weaknesses**: Very slow for large problems, exponential time complexity

### 4. Random Assignment (Baseline)
- **Type**: Random
- **Approach**: Randomly assign courses to rooms and times
- **Strengths**: Extremely fast
- **Weaknesses**: Almost never produces valid schedules

## Test Problem

- **10 courses** across different instructors
- **4 classrooms** with varying capacities
- **5 days** × **9 hours/day** = 45 time slots
- **Hard Constraints**:
  - No instructor conflicts
  - No room double-booking
  - Room capacity requirements
  - All courses must be scheduled

## Setup

```bash
# Install dependencies
pip install ortools

# Run experiment
python scheduling_comparison.py
```

## Expected Results

Google OR-Tools should:
- ✓ Find valid solutions consistently
- ✓ Execute in reasonable time (<1 second for this problem size)
- ✓ Scale to larger problems (tested separately if needed)
- ✓ Satisfy all hard constraints with zero violations

Alternative algorithms should show:
- Greedy: May find solution but often fails or has conflicts
- Backtracking: Very slow (may timeout on 10+ courses)
- Random: Almost never finds valid solution

## Metrics Measured

1. **Success Rate**: Did it find a valid schedule?
2. **Execution Time**: How fast?
3. **Constraint Violations**: How many conflicts?
4. **Completeness**: Were all courses scheduled?

## Why This Matters for Chronos

The real-world timetabling problem at KMUTT will have:
- 50-100+ courses per semester
- 20-30+ instructors
- Multiple buildings and room types
- Complex constraints (lab requirements, consecutive sessions, etc.)

Only a robust constraint programming solver like OR-Tools can handle this complexity while guaranteeing valid, conflict-free schedules.
