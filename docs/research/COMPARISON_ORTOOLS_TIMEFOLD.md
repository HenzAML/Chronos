# OR-Tools vs Timefold – Experiment Comparison

**Experiment:** Instructor availability & preference constraints  
**Run:** Same problem (10 courses, 5 instructors, 4 rooms, 45 slots)  
**Hard constraints:** H1–H5 (including instructor availability)  
**Soft constraints:** S1 prefer morning, S2 prefer certain days  

---

## Results from last run

| Algorithm              | Scheduled | Hard violations | Soft score | Time (s) |
|------------------------|-----------|------------------|------------|----------|
| **Google OR-Tools (CP-SAT)** | **10/10** | **0**            | **0**      | **0.050** |
| Timefold Solver        | —         | —                | —          | —        |
| Greedy (preference-aware) | 10/10   | 0                | 0          | 0.000    |
| Random (best of 500)   | 10/10     | 0                | 0          | 0.163    |
| Backtracking           | 10/10     | 0                | 0.000      | 0.000    |

*Timefold was skipped in this run (install from git + JDK 17 required; see below).*

---

## Scalability (10 vs 20 courses)

| Size | OR-Tools | Greedy | Random (500) | Backtracking |
|------|----------|--------|--------------|--------------|
| **10** | 10/10, 0 hard, 0 soft, ~0.02s | 10/10, 0, 0, ~0.00s | 10/10, 0, 0, ~0.16s | 10/10, 0, 0, ~0.00s |
| **20** | 20/20, 0 hard, 0 soft, ~0.04s | 20/20, 0, 0, ~0.00s | 20/20, 0, 10 soft, ~0.33s | 20/20, 0, 20 soft, ~0.00s |

- **OR-Tools** and **Greedy** keep 0 hard and 0 soft at both sizes.  
- **Random** and **Backtracking** satisfy hard constraints but get worse soft scores at 20 courses (preferences not optimized).  

---

## OR-Tools vs Timefold (same model)

- **Same inputs:** courses, instructors (availability + preferences), rooms, timeslots.  
- **Same outputs:** list of assignments; hard violations; soft score.  
- **Same constraints:**  
  - Hard: one assignment per course, no room/instructor conflict, capacity, **instructor availability**.  
  - Soft: prefer morning (weight 10), prefer days (weight 5).  

When Timefold is installed and the bridge runs successfully, you get a direct comparison on the same instance and metrics.

---

## How to run with Timefold included

1. Install **JDK 17+** and set `JAVA_HOME`.  
2. Install Timefold Solver for Python:
   ```bash
   pip install git+https://github.com/TimefoldAI/timefold-solver-python.git
   ```
3. Run:
   ```bash
   python experiment_instructor_constraints.py
   ```

If Timefold loads correctly, the table will include a Timefold row (scheduled, hard, soft, time). If it is skipped, the script prints a short message (e.g. install instructions or error).

---

## Summary

- **OR-Tools** is running and finds feasible, preference-optimal solutions (0 hard, 0 soft) in ~0.02–0.05 s for 10–20 courses.  
- **Timefold** is wired in via `chronos_timefold.py`; when the environment (Timefold + JDK 17) is correct, the same experiment run compares OR-Tools and Timefold on the same problem and metrics.
