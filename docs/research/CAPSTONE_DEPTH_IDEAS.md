# Making Chronos More Capstone-Worthy: Depth and Complexity

Using only OR-Tools out-of-the-box can feel lightweight for a capstone. Below are concrete ways to add **algorithmic depth** and **research-style contribution** without blowing scope.

---

## Option A: Hybrid / Multi-Algorithm Strategy (Recommended)

**Idea:** Don’t expose “just OR-Tools.” Expose a **solver strategy** that chooses or combines algorithms based on the problem and constraints.

**What you implement:**

1. **Strategy selector**
   - Input: problem size (e.g. number of courses), constraint density, user preference (e.g. “prefer speed” vs “prefer best soft score”).
   - Output: chosen strategy, e.g. `OR_TOOLS`, `TIMEFOLD`, `GREEDY_THEN_IMPROVE`, `OR_TOOLS_THEN_LOCAL_SEARCH`.
   - Rule examples: “if courses ≤ 30 and Timefold available → Timefold (better soft in our tests)”; “if courses > 100 or timeout risk → greedy then local search”; “default → OR-Tools with 30s limit.”

2. **Two-phase or hybrid runs**
   - **Phase 1:** OR-Tools (or Timefold) to get a feasible solution quickly.
   - **Phase 2:** Custom **local search** (e.g. swap two assignments, move one course) to improve soft score without breaking hard constraints.
   - You can write the local search yourself (swap/move neighborhoods, accept improving or simulated-annealing moves). That’s a clear “in-depth” contribution: you’re not just calling a solver.

3. **Fallback chain**
   - Try OR-Tools (e.g. 20s) → if infeasible or timeout, try Timefold (if installed) → else try greedy. Report which method produced the schedule and why the previous one failed.

**Why it’s capstone-worthy:** You design and implement **decision logic** and optionally **metaheuristic improvement**; you compare and justify strategies with your existing experiments.

---

## Option B: Configurable Constraints and Multi-Objective Trade-Offs

**Idea:** Make constraint strictness and weights **configurable** and expose **trade-off analysis**.

**What you implement:**

1. **Tunable hard/soft**
   - Some constraints (e.g. “instructor prefers morning”) can be toggled hard vs soft, or given a weight.
   - UI or config: “Treat ‘prefer morning’ as hard constraint?” or “Weight for prefer morning: 10.”

2. **Trade-off reporting**
   - Run the solver with different weights or relaxations; record (hard violations, soft score, solve time).
   - Show a simple **trade-off curve** or table: “If we allow 1 hard violation, soft score improves by X” or “If we relax preferred days, we can schedule 10% more courses.”

**Why it’s capstone-worthy:** You’re doing **parameter and constraint sensitivity analysis** and giving users informed choices.

---

## Option C: Algorithm Selection Based on Problem Characteristics

**Idea:** Automatically **recommend** (or choose) an algorithm based on problem size, constraint density, and time limit.

**What you implement:**

1. **Problem profiler**
   - Compute: number of courses, instructors, rooms, slots; density of availability (e.g. % of slots each instructor can teach); number of soft constraints.

2. **Selection rules or simple model**
   - Rules: “If small and need proven optimal → OR-Tools with long time limit”; “If large and need fast → greedy + local search”; “If many soft constraints and Timefold available → Timefold.”
   - Optionally: a small table from your experiments (e.g. “OR-Tools best for n≤50, Greedy+LS best for n>100”) and use it in code.

3. **Explainability**
   - “We recommend OR-Tools because problem has 25 courses and you requested optimality” or “We recommend Greedy + local search because problem has 120 courses and OR-Tools timed out in pilot runs.”

**Why it’s capstone-worthy:** You’re building a **decision layer** backed by your own empirical comparison.

---

## Option D: Decomposition (Two-Phase Scheduling)

**Idea:** Split the problem into **two phases** and solve each with (possibly) different methods.

**What you implement:**

1. **Phase 1 – Assign (course, timeslot)**  
   Respect: instructor availability, no instructor conflict, optionally “at most one per room per slot.”  
   Solver: OR-Tools or greedy.

2. **Phase 2 – Assign rooms**  
   Given fixed (course, timeslot), assign rooms to minimize capacity waste and preference violations.  
   This can be a smaller optimization (even greedy or small CP) and is easier to explain and tune.

**Why it’s capstone-worthy:** You’re doing **problem decomposition** and discussing why and when it works (and possibly when it doesn’t).

---

## Option E: Formal Experiment and Write-Up as Contribution

**Idea:** Frame your existing (and extended) comparisons as a **reproducible empirical study** and make that a stated contribution of the capstone.

**What you do:**

1. **Structured experiments**
   - Vary: number of courses (10, 20, 40, 80), constraint tightness (few vs many availability slots), time limits.
   - Record: feasibility, soft score, solve time, which algorithm.

2. **Methodology section**
   - Problem definition (inputs, outputs, H1–H5, S1–S2), instance generation, metrics, hardware.

3. **Results and discussion**
   - Tables and short analysis: “OR-Tools scales to 80 with 0 soft; Timefold comparable but slower; greedy fast but higher soft; Backtracking times out at 80.”
   - Conclusion: “For Chronos we choose OR-Tools because …; we recommend hybrid strategy for n>100.”

**Why it’s capstone-worthy:** The **contribution** is the comparison and the **recommendation**, not just using one library.

---

## Suggested Combination for Chronos

- **Core depth:** **Option A** – Hybrid strategy (selector + optional local search on top of OR-Tools/Timefold). This gives you “different algos used together based on requirements and constraints.”
- **Supporting depth:** **Option C** – Simple problem profiler and recommendation (so the strategy has clear inputs).
- **Documentation:** **Option E** – Formalize your experiment and results as a small “solver comparison study” in the report/slides.

---

## Implemented: `solver_strategy` module

A **starter implementation** is in place so you can say Chronos uses a hybrid, strategy-based approach:

- **`solver_strategy.py`**
  - **`profile_problem(problem)`** – Computes n_courses, n_instructors, n_rooms, n_slots, total instructor-slots, slack (for feasibility).
  - **`Strategy` enum** – OR_TOOLS, GREEDY, TIMEFOLD, HYBRID_ORTOOLS_LOCAL_SEARCH, FALLBACK_CHAIN.
  - **`select_strategy(problem, prefer_speed=False)`** – Chooses strategy by size (e.g. Greedy for n>100 or when prefer_speed and n>50; otherwise Hybrid).
  - **`local_search_improve(assignments, problem, max_seconds=5)`** – Improves soft score by swapping (room, timeslot) between two assignments while keeping hard constraints; first-improvement descent.
  - **`solve_hybrid_ortools_ls(problem, ...)`** – Phase 1: OR-Tools; Phase 2: local search on the result.
  - **`solve_with_strategy(problem, strategy=None, ...)`** – Single entry point: auto-select or use given strategy; returns assignments and info (including `strategy_used`, `local_search_improvement` when applicable).

**Run it:** `python solver_strategy.py` (uses default problem, prints profile, selected strategy, and result).

**Next steps you can take:** Hook `solve_with_strategy` into your web API so the app “uses different algorithms based on requirements and constraints”; add more strategies (e.g. Greedy + LS); or run experiments comparing “OR-Tools only” vs “Hybrid OR-Tools + LS” on soft score and time.
