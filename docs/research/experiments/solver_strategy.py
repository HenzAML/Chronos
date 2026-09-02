"""
Chronos: Hybrid solver strategy and algorithm selection.

This module adds capstone depth by:
- Profiling the problem (size, constraint density)
- Selecting or combining algorithms based on problem and user preference
- Optional local search improvement on top of OR-Tools (or other) solutions

Author: Aung Moe Lin
Project: Chronos - Automated Timetabling Solution
"""

import time
from enum import Enum
from typing import List, Tuple, Dict, Any

# Use experiment module for solvers and validation (avoids duplicating constraint logic)
from experiment_instructor_constraints import (
    solve_ortools,
    solve_greedy,
    validate_and_score,
    check_hard_constraints,
    soft_score,
    TIMEFOLD_AVAILABLE,
    Assignment,
)
try:
    from experiment_instructor_constraints import solve_timefold
except Exception:
    solve_timefold = None


class Strategy(str, Enum):
    """Solver strategy: which algorithm(s) to use."""
    OR_TOOLS = "OR_TOOLS"
    GREEDY = "GREEDY"
    TIMEFOLD = "TIMEFOLD"
    HYBRID_ORTOOLS_LOCAL_SEARCH = "HYBRID_ORTOOLS_LOCAL_SEARCH"
    FALLBACK_CHAIN = "FALLBACK_CHAIN"  # Try OR-Tools → Timefold → Greedy


def profile_problem(problem: dict) -> dict:
    """Compute problem characteristics for strategy selection."""
    courses = problem["courses"]
    instructors = problem["instructors"]
    rooms = problem["rooms"]
    timeslots = problem["timeslots"]
    n_courses = len(courses)
    n_instructors = len(instructors)
    n_rooms = len(rooms)
    n_slots = len(timeslots)
    total_instructor_slots = sum(len(inst.availability) for inst in instructors.values())
    # Density: how many (instructor, slot) options per course on average
    avg_slots_per_instructor = total_instructor_slots / n_instructors if n_instructors else 0
    return {
        "n_courses": n_courses,
        "n_instructors": n_instructors,
        "n_rooms": n_rooms,
        "n_slots": n_slots,
        "total_instructor_slots": total_instructor_slots,
        "avg_slots_per_instructor": avg_slots_per_instructor,
        "slack": total_instructor_slots - n_courses,  # positive => likely feasible
    }


def select_strategy(
    problem: dict,
    prefer_speed: bool = False,
    time_limit_seconds: int = 30,
) -> Strategy:
    """
    Choose a strategy based on problem profile and preference.
    - Small problems: OR-Tools (or Timefold if available and we want to compare).
    - Prefer speed + large n: Greedy (no improvement phase).
    - Default: OR-Tools; optionally add local search for better soft score.
    - Fallback chain: use when we want robustness (try multiple solvers).
    """
    prof = profile_problem(problem)
    n = prof["n_courses"]

    if prefer_speed and n > 50:
        return Strategy.GREEDY
    if n > 100:
        # Large: greedy is fast; hybrid would use more time for LS
        return Strategy.GREEDY
    # Default: hybrid OR-Tools + local search for better soft score (capstone depth)
    return Strategy.HYBRID_ORTOOLS_LOCAL_SEARCH


def local_search_improve(
    assignments: List[Any],
    problem: dict,
    max_seconds: float = 5.0,
    max_iterations: int = 5000,
) -> Tuple[List[Any], int, int]:
    """
    Improve soft score by swapping (room, timeslot) between two assignments.
    Keeps hard constraints satisfied. Returns (improved_assignments, soft_before, soft_after).
    """
    if not assignments:
        return assignments, 0, 0
    # Avoid mutating original
    current = list(assignments)
    instructors = problem["instructors"]
    rooms = problem["rooms"]
    current_soft = soft_score(current, instructors)
    start = time.perf_counter()
    it = 0
    improved = True
    while improved and (time.perf_counter() - start) < max_seconds and it < max_iterations:
        improved = False
        it += 1
        for i in range(len(current)):
            if (time.perf_counter() - start) >= max_seconds:
                break
            for j in range(i + 1, len(current)):
                a_i, a_j = current[i], current[j]
                # Swap (room, timeslot) between a_i and a_j
                if a_i.room.id == a_j.room.id and a_i.timeslot.tuple() == a_j.timeslot.tuple():
                    continue
                # Build new assignments: a_i gets (a_j.room, a_j.timeslot), a_j gets (a_i.room, a_i.timeslot)
                r_j = a_j.room
                ts_j = a_j.timeslot
                r_i = a_i.room
                ts_i = a_i.timeslot
                # Feasibility: capacity and instructor availability
                if a_i.course.expected_students > r_j.capacity or a_j.course.expected_students > r_i.capacity:
                    continue
                inst_i = instructors.get(a_i.course.instructor_id)
                inst_j = instructors.get(a_j.course.instructor_id)
                if inst_i and ts_j.tuple() not in inst_i.availability:
                    continue
                if inst_j and ts_i.tuple() not in inst_j.availability:
                    continue
                new_i = Assignment(course=a_i.course, room=r_j, timeslot=ts_j)
                new_j = Assignment(course=a_j.course, room=r_i, timeslot=ts_i)
                new_list = current[:i] + [new_i] + current[i + 1 : j] + [new_j] + current[j + 1 :]
                hard = check_hard_constraints(new_list, instructors, rooms)
                if sum(hard.values()) > 0:
                    continue
                new_soft = soft_score(new_list, instructors)
                if new_soft < current_soft:
                    current = new_list
                    current_soft = new_soft
                    improved = True
                    break
            if improved:
                break
    return current, soft_score(assignments, instructors), current_soft


def solve_hybrid_ortools_ls(
    problem: dict,
    time_limit_ortools: float = 25.0,
    time_limit_ls: float = 5.0,
) -> Tuple[List[Any], float, dict]:
    """
    Phase 1: OR-Tools to get a feasible solution.
    Phase 2: Local search to improve soft score.
    Returns (assignments, total_elapsed, info).
    """
    start_total = time.perf_counter()
    assignments, elapsed_ot, info_ot = solve_ortools(problem, time_limit_seconds=int(time_limit_ortools))
    if not assignments:
        return [], time.perf_counter() - start_total, {
            **info_ot,
            "strategy": "HYBRID_ORTOOLS_LOCAL_SEARCH",
            "phase1": "OR-Tools",
            "phase2": "skipped (no feasible solution)",
        }
    soft_before = info_ot.get("soft_score", soft_score(assignments, problem["instructors"]))
    improved_assignments, soft_before_ls, soft_after_ls = local_search_improve(
        assignments, problem, max_seconds=time_limit_ls
    )
    elapsed_total = time.perf_counter() - start_total
    hard, soft_final, ok = validate_and_score(improved_assignments, problem)
    return improved_assignments, elapsed_total, {
        "hard_violations": sum(hard.values()),
        "soft_score": soft_final,
        "all_scheduled": ok,
        "strategy": "HYBRID_ORTOOLS_LOCAL_SEARCH",
        "phase1": "OR-Tools",
        "phase2": "local_search",
        "soft_before_ls": soft_before,
        "soft_after_ls": soft_final,
        "local_search_improvement": soft_before - soft_final,
    }


def solve_with_strategy(
    problem: dict,
    strategy: Strategy = None,
    time_limit_seconds: int = 30,
    prefer_speed: bool = False,
) -> Tuple[List[Any], float, dict]:
    """
    Solve using the given strategy, or auto-select based on problem and prefer_speed.
    Returns (assignments, elapsed, info). info includes "strategy_used".
    """
    if strategy is None:
        strategy = select_strategy(problem, prefer_speed=prefer_speed, time_limit_seconds=time_limit_seconds)

    if strategy == Strategy.OR_TOOLS:
        a, e, i = solve_ortools(problem, time_limit_seconds=time_limit_seconds)
        i["strategy_used"] = "OR_TOOLS"
        return a, e, i
    if strategy == Strategy.GREEDY:
        a, e, i = solve_greedy(problem)
        i["strategy_used"] = "GREEDY"
        return a, e, i
    if strategy == Strategy.TIMEFOLD and TIMEFOLD_AVAILABLE and solve_timefold:
        a, e, i = solve_timefold(problem, time_limit_seconds=time_limit_seconds)
        i["strategy_used"] = "TIMEFOLD"
        return a, e, i
    if strategy == Strategy.HYBRID_ORTOOLS_LOCAL_SEARCH:
        a, e, i = solve_hybrid_ortools_ls(
            problem,
            time_limit_ortools=max(5, time_limit_seconds - 5),
            time_limit_ls=5.0,
        )
        i["strategy_used"] = "HYBRID_ORTOOLS_LOCAL_SEARCH"
        return a, e, i
    if strategy == Strategy.FALLBACK_CHAIN:
        a, e, i = solve_ortools(problem, time_limit_seconds=time_limit_seconds - 5)
        if a:
            i["strategy_used"] = "FALLBACK_CHAIN(OR_TOOLS)"
            return a, e, i
        if TIMEFOLD_AVAILABLE and solve_timefold:
            a, e, i = solve_timefold(problem, time_limit_seconds=time_limit_seconds - 5)
            if a:
                i["strategy_used"] = "FALLBACK_CHAIN(TIMEFOLD)"
                return a, e, i
        a, e, i = solve_greedy(problem)
        i["strategy_used"] = "FALLBACK_CHAIN(GREEDY)"
        return a, e, i

    # Default
    a, e, i = solve_ortools(problem, time_limit_seconds=time_limit_seconds)
    i["strategy_used"] = str(strategy)
    return a, e, i


if __name__ == "__main__":
    from experiment_instructor_constraints import build_problem

    problem = build_problem()
    prof = profile_problem(problem)
    print("Problem profile:", prof)
    strategy = select_strategy(problem)
    print("Selected strategy:", strategy)
    assignments, elapsed, info = solve_with_strategy(problem, time_limit_seconds=30)
    print(f"Scheduled: {len(assignments)}/{len(problem['courses'])}, soft={info.get('soft_score')}, time={elapsed:.3f}s")
    print("Strategy used:", info.get("strategy_used"))
    if "local_search_improvement" in info:
        print("Local search improvement (soft):", info["local_search_improvement"])
