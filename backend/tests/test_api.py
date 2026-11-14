"""The HTTP API, end to end: build data through the API, generate, read back."""


def post(client, path, data, expect=201):
    res = client.post(f"/api{path}", json=data)
    assert res.status_code == expect, res.get_json()
    return res.get_json()


def setup_campus(client, hours=(9, 10, 11), rooms=1):
    """Monday slots at the given hours, one instructor free for all of them."""
    slots = [post(client, "/timeslots", {"day": 0, "hour": h}) for h in hours]
    teacher = post(client, "/instructors", {
        "name": "Dr. Anong", "availability_slot_ids": [s["id"] for s in slots]})
    for n in range(1, rooms + 1):
        post(client, "/rooms", {"code": f"R{n}", "capacity": 50})
    return slots, teacher


def add_course(client, code, teacher, **extra):
    return post(client, "/courses", {
        "code": code, "name": f"Course {code}", "instructor_id": teacher["id"],
        "expected_students": 30, **extra})


def test_generate_places_a_three_hour_class(client):
    slots, teacher = setup_campus(client)
    add_course(client, "CS101", teacher, duration_hours=3)

    s = post(client, "/generate", {}, expect=200)

    assert s["status"] == "optimal"
    assert (s["assignment_count"], s["unscheduled_count"], s["class_count"]) == (1, 0, 1)
    [a] = s["assignments"]
    assert (a["course"]["code"], a["duration_hours"], a["class_index"]) == ("CS101", 3, 1)
    assert (a["time_slot"]["hour"], a["end_hour"]) == (9, 12)


def test_grid_lists_every_hour_a_block_touches(client):
    slots, teacher = setup_campus(client)
    add_course(client, "CS101", teacher, duration_hours=3)
    s = post(client, "/generate", {}, expect=200)

    grid = client.get(f"/api/schedules/{s['id']}/grid").get_json()

    assert grid["hours"] == [9, 10, 11]
    assert grid["days"] == [0]
    assert [a["course"]["code"] for a in grid["grid"]["0"]["9"]] == ["CS101"]


def test_generate_returns_partial_schedule_with_reasons(client):
    # Two one-hour courses, two instructors, one room, one slot: one must wait.
    [slot] = [post(client, "/timeslots", {"day": 0, "hour": 9})]
    post(client, "/rooms", {"code": "LAB-1", "capacity": 50})
    for n in (1, 2):
        teacher = post(client, "/instructors", {
            "name": f"Dr. {n}", "availability_slot_ids": [slot["id"]]})
        add_course(client, f"CS10{n}", teacher)

    s = post(client, "/generate", {}, expect=200)

    assert s["status"] == "partial"
    assert (s["assignment_count"], s["unscheduled_count"], s["class_count"]) == (1, 1, 2)
    [u] = s["unscheduled"]
    assert u["code"] == "room_contention"
    assert "LAB-1" in u["message"]
    assert u["blockers"][0]["course_code"] == s["assignments"][0]["course"]["code"]

    # The reasons are stored, not just returned once.
    again = client.get(f"/api/schedules/{s['id']}").get_json()
    assert again["unscheduled"] == s["unscheduled"]
    listed = client.get("/api/schedules").get_json()
    assert listed[0]["unscheduled_count"] == 1


def test_generate_with_no_data_fails_gracefully(client):
    res = client.post("/api/generate", json={})

    assert res.status_code == 200
    s = res.get_json()
    assert s["status"] == "failed"
    assert "no courses" in s["message"].lower()
    assert s["assignments"] == [] and s["unscheduled"] == []


def test_course_takes_classes_per_week(client):
    slots, teacher = setup_campus(client)
    c = add_course(client, "CS101", teacher, classes_per_week=2)
    assert c["classes_per_week"] == 2

    res = client.patch(f"/api/courses/{c['id']}", json={"classes_per_week": 1})
    assert res.get_json()["classes_per_week"] == 1

    res = client.patch(f"/api/courses/{c['id']}", json={"classes_per_week": 0})
    assert res.status_code == 422


def test_course_defaults_to_one_class_of_one_hour(client):
    slots, teacher = setup_campus(client)
    c = add_course(client, "CS101", teacher)

    assert (c["duration_hours"], c["classes_per_week"]) == (1, 1)


def test_unknown_schedule_is_a_json_404(client):
    res = client.get("/api/schedules/999")

    assert res.status_code == 404
    assert "not found" in res.get_json()["error"]["message"].lower()


def test_bad_generate_input_is_rejected_with_details(client):
    res = client.post("/api/generate", json={"time_limit_seconds": "soon"})

    assert res.status_code == 422
    assert res.get_json()["error"]["details"] == ["'time_limit_seconds' must be an integer."]
