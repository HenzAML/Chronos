# Experiment: Instructor Availability & Preference Constraints

**Author:** Aung Moe Lin  
**Project:** Chronos  
**Purpose:** Compare scheduling algorithms (Google OR-Tools, Greedy, Random, Backtracking; Timefold/OptaPlanner documented) when instructors have **availability** (“I’m only free at these times”) and **preferences** (“I prefer mornings”, “I want only Tuesday and Wednesday”).

---

## 1. INPUTS

| Input | Type | Description |
|-------|------|-------------|
| **Courses** | List[Course] | Each: `id`, `name`, `instructor_id`, `duration_hours`, `expected_students`. |
| **Instructors** | Dict[instructor_id, Instructor] | Each: `id`, `name`, **availability**, **prefer_morning**, **preferred_days**, optional **preferred_slots**. |
| **Rooms** | List[Room] | Each: `id`, `capacity`. |
| **Time slots** | List[TimeSlot] | Each: `day` (0=Mon..4=Fri), `hour` (e.g. 8–16). |

### Instructor fields (constraint-related)

- **availability**: `List[Tuple[day, hour]]`  
  **HARD.** Only these (day, hour) pairs are allowed for that instructor.  
  Example: `[(0,9), (0,10), (2,9)]` = “I’m only free Mon 9–10 and Wed 9.”

- **prefer_morning**: `bool`  
  **SOFT.** If True, we penalize assignments with `hour >= 12`.

- **preferred_days**: `List[int]`  
  **SOFT.** Preferred days (e.g. `[1, 2]` = Tuesday and Wednesday). We penalize assignments on other days.

- **preferred_slots**: `List[Tuple[day, hour]]` (optional)  
  **SOFT.** Preferred (day, hour); we can penalize assignments not in this set.

---

## 2. OUTPUTS

| Output | Type | Description |
|--------|------|-------------|
| **Schedule** | List[Assignment] | Each: `course`, `room`, `timeslot`. |
| **Hard violations** | Dict[str, int] | Count per type (H1–H5). Feasible iff all are 0. |
| **Soft score** | int | Weighted sum of preference violations; **lower is better**. |
| **All scheduled** | bool | True iff every course has exactly one assignment. |

**Success (feasible):** All courses scheduled, zero hard violations.  
**Quality:** Among feasible solutions, lower soft score = better satisfaction of instructor preferences.

---

## 3. HARD CONSTRAINTS (must be satisfied)

| ID | Description |
|----|-------------|
| **H1** | Each course is assigned exactly one (room, timeslot). |
| **H2** | No room is double-booked: at most one course per (room, timeslot). |
| **H3** | No instructor double-booked: at most one course per (instructor, timeslot). |
| **H4** | Room capacity: for each assignment, `room.capacity >= course.expected_students`. |
| **H5** | **Instructor availability:** A course can only be scheduled in a timeslot that is in its instructor’s **availability** set. (“I’m only free at this time.”) |

---

## 4. SOFT CONSTRAINTS (minimize violations)

| ID | Description | Weight (example) |
|----|-------------|-------------------|
| **S1** | **Prefer morning:** If instructor has `prefer_morning=True`, penalize if `hour >= 12`. | 10 |
| **S2** | **Prefer certain days:** If instructor has `preferred_days`, penalize if `day not in preferred_days` (e.g. “I want only Tue and Wed”). | 5 |
| **S3** | **Prefer specific slots:** If instructor has `preferred_slots`, penalize assignment not in that set (optional). | 2 |

Soft score = sum over all assignments of the corresponding penalties. **Lower is better.**

---

## 5. ALGORITHMS COMPARED

| Algorithm | Role in experiment | Notes |
|-----------|--------------------|--------|
| **Google OR-Tools (CP-SAT)** | Implemented | Hard as constraints, soft as linear objective (WeightedSum). Minimize total penalty. |
| **Greedy (preference-aware)** | Implemented | Assign courses one by one; choose feasible (room, timeslot) with smallest added soft penalty. |
| **Random** | Implemented | Repeated random feasible assignments; keep best by soft score (best of 500). |
| **Backtracking** | Implemented | Exhaustive search respecting all hard constraints; no soft optimization (finds first feasible). |
| **Timefold Solver** | Implemented (optional) | Same inputs/outputs/constraints. Bridge: `chronos_timefold.py`. Availability = hard constraint; preferences = soft (ConstraintStreams). Run when Timefold Python + JDK 17 are installed. |
| **OptaPlanner** | Documented | Same as Timefold (Timefold is the successor). JVM-only; same model: availability hard, preferences soft. |

---

## 6. METHODOLOGY

1. **Single instance:** Build one problem with 10 courses, 5 instructors (with availability and preferences), 4 rooms, 45 time slots. Run OR-Tools, Greedy, Random, Backtracking; record scheduled count, hard violations, soft score, time.
2. **Scalability:** Scale to 20 (and optionally 40) courses; same algorithms; same metrics.
3. **Definition of success:**  
   - **Feasible:** All courses scheduled, zero hard violations.  
   - **Better quality:** Among feasible, lower soft score.
4. **Timefold/OptaPlanner:** Same input/output and constraint definitions; implementation would be in Java/Kotlin (OptaPlanner) or Java/Kotlin/Python (Timefold). They would model H5 as “only allow assignments in instructor.availability” and S1–S3 as soft constraints in their scoring API.

---

## 7. HOW TO RUN

```bash
cd /path/to/Chronos
python experiment_instructor_constraints.py
```

- **Required:** `ortools` (for OR-Tools).
- **Optional – Timefold:** To include Timefold in the comparison:
  1. Install JDK 17+ and set `JAVA_HOME`.
  2. `pip install git+https://github.com/TimefoldAI/timefold-solver-python.git`
  3. The experiment will run the Timefold solver via `chronos_timefold.py` and include it in the results table.

---

## 8. INTERPRETATION

- **OR-Tools:** Expect best soft score when a feasible solution exists (optimal or near-optimal for the linear soft objective).
- **Greedy:** Fast; soft score depends on order and tie-breaking; may be worse than OR-Tools.
- **Random:** Often worse soft score; useful as baseline.
- **Backtracking:** Finds a feasible solution; does not optimize soft (so soft score can be high).
- **Timefold/OptaPlanner:** Would optimize soft constraints with metaheuristics; comparable goal to OR-Tools with different solving approach (and possibly different soft constraint expressiveness).

This experiment shows that **instructor availability** (hard) and **instructor preferences** (soft) can be defined clearly and compared across algorithms that support the same inputs and outputs.
