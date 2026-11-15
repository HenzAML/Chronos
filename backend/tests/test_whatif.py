"""Verified what-if fixes through find_fixes(). Hand-built problems, no database."""

import copy

from app.solver import solve
from app.solver.whatif import find_fixes

from tests.builders import course, inst, make_slots, problem, room


def fixes_for(p):
    return find_fixes(p, solve(p))


def test_shortening_a_class_that_is_too_long_is_a_verified_fix():
    slots = make_slots({0: [9, 10]})
    p = problem([course(1, code="DEMO903", duration=3)], [room(1)], slots, [inst(1, slots)])

    assert fixes_for(p) == [{
        "course_id": 1, "course_code": "DEMO903", "class_index": 1, "kind": "shorten",
        "message": "Shorten DEMO903 from 3 to 2 hours", "placed": 1,
    }]


def test_widening_the_instructors_availability_is_a_verified_fix():
    slots = make_slots({0: [9, 10], 1: [9, 10]})
    teacher = inst(1, [slots[0], slots[2]], name="Dr. Somchai")     # never 2 hours in a row
    p = problem([course(1, duration=2)], [room(1)], slots, [teacher])

    fixes = fixes_for(p)

    assert {"course_id": 1, "course_code": "C1", "class_index": 1,
            "kind": "widen_availability",
            "message": "Make Dr. Somchai available on more slots", "placed": 1} in fixes
    assert {f["kind"] for f in fixes} == {"widen_availability", "shorten"}


def test_one_more_room_like_the_blocking_room_is_a_verified_fix():
    slots = make_slots({0: [9]})
    p = problem(
        [course(1, instructor_id=1), course(2, instructor_id=2)],
        [room(1, code="R204", capacity=60, equipment=[3])], slots,
        [inst(1, slots), inst(2, slots)], equipment_names={3: "Projector"},
    )
    before = copy.deepcopy(p)

    [fix] = fixes_for(p)

    assert (fix["kind"], fix["placed"]) == ("room_like", 2)
    assert fix["message"] == "Add a room like R204 (60 seats, Projector)"
    assert p == before                              # the original problem is untouched


def test_a_room_big_enough_fixes_a_capacity_reason():
    slots = make_slots({0: [9]})
    p = problem([course(1, students=200)], [room(1, capacity=120)], slots, [inst(1, slots)])

    [fix] = fixes_for(p)

    assert (fix["kind"], fix["placed"]) == ("new_room", 1)
    assert fix["message"] == "Add a room with at least 200 seats"


def test_a_room_with_the_essential_equipment_fixes_an_equipment_reason():
    slots = make_slots({0: [9]})
    p = problem(
        [course(1, essential=[7])], [room(1, equipment=[3])], slots, [inst(1, slots)],
        equipment_names={7: "Lab Benches", 3: "Projector"},
    )

    [fix] = fixes_for(p)

    assert (fix["kind"], fix["placed"]) == ("new_room", 1)
    assert fix["message"] == "Add a room with at least 30 seats and Lab Benches"


def test_a_class_no_single_change_fixes_says_so():
    slots = make_slots({0: [9]})                    # 3 hours, shortened to 2, still too long
    p = problem([course(1, duration=3)], [room(1)], slots, [inst(1, slots)])

    assert fixes_for(p) == [{
        "course_id": 1, "course_code": "C1", "class_index": 1, "kind": "none",
        "message": "No single change fixes this", "placed": 0,
    }]


def test_a_change_that_only_displaces_another_class_is_not_a_fix():
    # One room, Mon 09-11. A (Dr. 1, free 09:00 only) is placed but in the wrong
    # room type. T is 2 hours and Dr. 2 is free 09:00 only, so T is left out.
    # Widen Dr. 2 or shorten T and the solver prefers T (no penalty) over A:
    # T is placed, A is dropped, the count stays at 1. Neither is a fix.
    slots = make_slots({0: [9, 10]})
    p = problem(
        [course(1, code="A", instructor_id=1, session_type="lab"),
         course(2, code="T", instructor_id=2, duration=2)],
        [room(1)], slots, [inst(1, slots[:1]), inst(2, slots[:1])],
    )
    result = solve(p)
    assert [u.course_code for u in result.unscheduled] == ["T"]

    assert [(f["course_code"], f["kind"], f["placed"]) for f in find_fixes(p, result)] == [
        ("T", "none", 1)]


def test_nothing_left_out_means_no_fixes():
    slots = make_slots({0: [9]})
    p = problem([course(1)], [room(1)], slots, [inst(1, slots)])

    assert fixes_for(p) == []
