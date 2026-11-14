"""Solver behaviour through solve(). Expected values are worked out by hand."""

from app.solver import solve
from app.solver.problem import Toggles

from tests.builders import course, inst, make_slots, problem, room


def placed(result):
    """{(course_id, class_index): (room_id, slot_id, duration)}"""
    return {(p.course_id, p.class_index): (p.room_id, p.slot_id, p.duration_hours)
            for p in result.placements}


def test_one_course_one_room_one_slot_is_placed():
    slots = make_slots({0: [9]})
    result = solve(problem([course(1)], [room(1)], slots, [inst(1, slots)]))

    assert result.status == "optimal"
    assert placed(result) == {(1, 1): (1, slots[0].id, 1)}
    assert result.unscheduled == []
    assert result.class_count == 1


def test_three_hour_class_takes_one_continuous_block():
    slots = make_slots({0: [9, 10, 11]})
    result = solve(problem([course(1, duration=3)], [room(1)], slots, [inst(1, slots)]))

    assert placed(result) == {(1, 1): (1, slots[0].id, 3)}


def test_blocks_in_one_room_do_not_overlap():
    slots = make_slots({0: [9, 10, 11], 1: [9, 10, 11]})
    p = problem(
        [course(1, duration=3, instructor_id=1), course(2, duration=3, instructor_id=2)],
        [room(1)], slots, [inst(1, slots), inst(2, slots)],
    )
    result = solve(p)

    assert result.status == "optimal"
    starts = sorted(slot_id for _, slot_id, _ in placed(result).values())
    assert starts == [slots[0].id, slots[3].id]     # Mon 09:00 and Tue 09:00


def test_block_needs_consecutive_hours():
    slots = make_slots({0: [9, 10, 13]})            # gap after 10:00
    result = solve(problem([course(1, duration=3)], [room(1)], slots, [inst(1, slots)]))

    assert result.status == "partial"
    assert result.placements == []
    [u] = result.unscheduled
    assert (u.course_code, u.class_index, u.code) == ("C1", 1, "no_block")


def test_room_too_small_is_named():
    slots = make_slots({0: [9]})
    result = solve(problem(
        [course(1, students=200)], [room(1, code="LH-1", capacity=120)],
        slots, [inst(1, slots)],
    ))

    [u] = result.unscheduled
    assert u.code == "capacity"
    assert "200" in u.message and "LH-1" in u.message and "120" in u.message


def test_missing_essential_equipment_is_named():
    slots = make_slots({0: [9]})
    result = solve(problem(
        [course(1, essential=[7])], [room(1, equipment=[3])], slots, [inst(1, slots)],
        equipment_names={7: "Lab Benches", 3: "Projector"},
    ))

    [u] = result.unscheduled
    assert u.code == "essential_equipment"
    assert "Lab Benches" in u.message


def test_instructor_without_long_enough_window():
    slots = make_slots({0: [9, 10], 1: [9, 10]})
    teacher = inst(1, [slots[0], slots[2]], name="Dr. Somchai")   # Mon 9, Tue 9 only
    result = solve(problem([course(1, duration=2)], [room(1)], slots, [teacher]))

    [u] = result.unscheduled
    assert u.code == "availability"
    assert "Dr. Somchai" in u.message


def test_room_contention_names_the_blocking_class():
    slots = make_slots({0: [9]})
    p = problem(
        [course(1, code="CS101", instructor_id=1), course(2, code="CS102", instructor_id=2)],
        [room(1, code="LAB-1")], slots, [inst(1, slots), inst(2, slots)],
    )
    result = solve(p)

    assert result.status == "partial"
    assert len(result.placements) == 1
    [u] = result.unscheduled
    winner = "CS101" if u.course_code == "CS102" else "CS102"
    assert u.code == "room_contention"
    assert winner in u.message and "LAB-1" in u.message
    assert [(b["kind"], b["course_code"], b["room_code"]) for b in u.blockers] == [
        ("room", winner, "LAB-1")]


def test_instructor_contention_names_the_other_class():
    slots = make_slots({0: [9]})
    p = problem(
        [course(1, code="CS101"), course(2, code="CS102")],
        [room(1), room(2)], slots, [inst(1, slots, name="Dr. Anong")],
    )
    result = solve(p)

    [u] = result.unscheduled
    assert u.code == "instructor_contention"
    assert "Dr. Anong" in u.message
    assert u.blockers[0]["kind"] == "instructor"


def test_two_classes_a_week_land_on_different_days():
    slots = make_slots({0: [9, 10], 1: [9]})
    result = solve(problem([course(1, per_week=2)], [room(1)], slots, [inst(1, slots)]))

    assert result.status == "optimal"
    assert result.class_count == 2
    days = {slots[slot_id - 1].day for _, slot_id, _ in placed(result).values()}
    assert days == {0, 1}


def test_second_class_left_out_when_only_one_day_exists():
    slots = make_slots({0: [9, 10]})
    result = solve(problem([course(1, per_week=2)], [room(1)], slots, [inst(1, slots)]))

    assert result.status == "partial"
    assert list(placed(result)) == [(1, 1)]
    [u] = result.unscheduled
    assert (u.class_index, u.code) == (2, "same_course_day")


def test_placing_more_classes_beats_a_better_preference_score():
    # One room, Mon 09-13. X fits only 10-12 and costs nothing. Y fits only
    # 09-11, Z only 11-13, and Z breaks its instructor's morning preference.
    # X alone scores 0; Y + Z scores 10 but places two classes. Two must win.
    slots = make_slots({0: [9, 10, 11, 12]})
    p = problem(
        [course(1, code="X", instructor_id=1, duration=2),
         course(2, code="Y", instructor_id=2, duration=2),
         course(3, code="Z", instructor_id=3, duration=2)],
        [room(1)], slots,
        [inst(1, slots[1:3]), inst(2, slots[0:2]),
         inst(3, slots[2:4], prefer_morning=True)],
    )
    result = solve(p)

    assert sorted(c for c, _ in placed(result)) == [2, 3]
    assert [u.course_code for u in result.unscheduled] == ["X"]
    assert result.soft_score == 10


def test_morning_preference_counts_any_hour_from_noon():
    # Block 11-13 touches 12:00, so it breaks the preference; 09-11 does not.
    slots = make_slots({0: [11, 12], 1: [9, 10]})
    p = problem([course(1, duration=2)], [room(1)], slots,
                [inst(1, slots, prefer_morning=True)])
    result = solve(p)

    assert placed(result) == {(1, 1): (1, slots[2].id, 2)}
    assert result.soft_score == 0


def test_capacity_rule_can_be_switched_off():
    slots = make_slots({0: [9]})
    p = problem([course(1, students=200)], [room(1, capacity=20)], slots, [inst(1, slots)])

    assert solve(p, toggles=Toggles(h4_capacity=False)).status == "optimal"


def test_room_clash_rule_can_be_switched_off():
    slots = make_slots({0: [9]})
    p = problem(
        [course(1, instructor_id=1), course(2, instructor_id=2)],
        [room(1)], slots, [inst(1, slots), inst(2, slots)],
    )

    assert len(solve(p, toggles=Toggles(h2_room_conflict=False)).placements) == 2


def test_no_courses_is_a_failed_run_with_a_message():
    slots = make_slots({0: [9]})
    result = solve(problem([], [room(1)], slots, []))

    assert result.status == "failed"
    assert "course" in result.message.lower()


def test_crowded_week_has_no_double_booking_and_respects_availability():
    # 30 courses of mixed length fight over 2 rooms and 20 slots: far too many.
    import random
    rng = random.Random(7)
    slots = make_slots({d: [9, 10, 11, 12] for d in range(5)})
    teachers = [inst(i, rng.sample(slots, 12)) for i in range(1, 9)]
    courses = [course(n, instructor_id=rng.randint(1, 8), duration=rng.choice([1, 2, 3]),
                      per_week=rng.choice([1, 1, 2])) for n in range(1, 31)]
    p = problem(courses, [room(1), room(2)], slots, teachers)
    result = solve(p, time_limit_seconds=10)

    by_id = {s.id: s for s in slots}
    teacher_of = {c.id: c.instructor_id for c in courses}
    room_hours, teacher_hours, course_days = set(), set(), set()
    for pl in result.placements:
        start = by_id[pl.slot_id]
        assert (pl.course_id, start.day) not in course_days
        course_days.add((pl.course_id, start.day))
        for k in range(pl.duration_hours):
            hour = (start.day, start.hour + k)
            slot = next(s for s in slots if (s.day, s.hour) == hour)   # block stays in the grid
            assert slot.id in p.instructors[teacher_of[pl.course_id]].available_slot_ids
            assert (pl.room_id, hour) not in room_hours
            assert (teacher_of[pl.course_id], hour) not in teacher_hours
            room_hours.add((pl.room_id, hour))
            teacher_hours.add((teacher_of[pl.course_id], hour))

    assert result.status == "partial"
    assert len(result.placements) + len(result.unscheduled) == result.class_count
    assert all(u.message and u.code != "time_limit" for u in result.unscheduled)
