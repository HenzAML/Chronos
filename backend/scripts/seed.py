"""Seed Chronos with realistic KMUTT-scale data.

Deterministic: a fixed RNG seed means every run produces the same dataset, so
solver results stay comparable across runs (needed for the report's experiments).

Usage:
    python scripts/seed.py --reset            # default: ~80 courses
    python scripts/seed.py --reset --size small
    python scripts/seed.py --reset --courses 120
"""

import argparse
import os
import random
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))

from app import create_app
from app.extensions import db
from app.models import (
    ConstraintConfig,
    Course,
    CourseEquipmentRequirement,
    Equipment,
    Instructor,
    InstructorAvailability,
    Room,
    RoomEquipment,
    TimeSlot,
)

RNG_SEED = 20260902

DAYS = range(5)          # Mon-Fri
HOURS = range(8, 17)     # 08:00-16:00 starts -> 45 slots

EQUIPMENT = [
    ("projector", "Projector"),
    ("computers", "Computer Workstations"),
    ("whiteboard", "Whiteboard"),
    ("smartboard", "Interactive Smartboard"),
    ("lab_bench", "Lab Benches"),
    ("video_conf", "Video Conferencing"),
    ("sound_system", "Sound System"),
]

# (code, name, capacity, capabilities, equipment)
ROOMS = [
    # Lecture halls
    ("LH-101", "Lecture Hall 101", 120, ["lecture"], ["projector", "whiteboard", "sound_system"]),
    ("LH-102", "Lecture Hall 102", 110, ["lecture"], ["projector", "whiteboard", "sound_system"]),
    ("LH-103", "Lecture Hall 103", 100, ["lecture", "seminar"], ["projector", "whiteboard", "smartboard"]),
    ("CB-201", "Classroom 201", 80, ["lecture"], ["projector", "whiteboard"]),
    ("CB-202", "Classroom 202", 80, ["lecture"], ["projector", "whiteboard"]),
    ("CB-203", "Classroom 203", 60, ["lecture", "group"], ["projector", "whiteboard"]),
    ("CB-204", "Classroom 204", 60, ["lecture", "group"], ["projector", "whiteboard"]),
    ("CB-205", "Classroom 205", 50, ["lecture"], ["projector", "whiteboard"]),
    # Computer labs
    ("LAB-301", "Computer Lab 301", 45, ["lab", "lecture"], ["computers", "projector", "whiteboard"]),
    ("LAB-302", "Computer Lab 302", 45, ["lab", "lecture"], ["computers", "projector", "whiteboard"]),
    ("LAB-303", "Computer Lab 303", 40, ["lab"], ["computers", "projector"]),
    ("LAB-304", "Computer Lab 304", 40, ["lab", "group"], ["computers", "projector", "whiteboard"]),
    ("LAB-305", "Hardware Lab 305", 30, ["lab"], ["computers", "lab_bench", "projector"]),
    # Seminar rooms
    ("SR-401", "Seminar Room 401", 40, ["seminar", "lecture"], ["projector", "smartboard", "video_conf"]),
    ("SR-402", "Seminar Room 402", 32, ["seminar", "group"], ["projector", "smartboard", "video_conf"]),
    ("SR-403", "Seminar Room 403", 25, ["seminar", "meeting"], ["projector", "video_conf", "whiteboard"]),
    # Group / studio
    ("GR-501", "Group Studio 501", 30, ["group", "seminar"], ["whiteboard", "smartboard", "projector"]),
    ("GR-502", "Group Studio 502", 24, ["group"], ["whiteboard", "projector"]),
    # Meeting rooms
    ("MR-601", "Meeting Room 601", 20, ["meeting", "group"], ["video_conf", "smartboard", "whiteboard"]),
    ("MR-602", "Meeting Room 602", 14, ["meeting"], ["video_conf", "whiteboard"]),
]

# Tight profile: scarce rooms and scarce equipment, so the soft terms have to
# fight over them. Deliberately includes rooms that satisfy a course's ESSENTIAL
# equipment while NOT supporting its session type (CR-210 has computers but is
# not a lab), which is what makes S4 reachable without breaking H6.
TIGHT_ROOMS = [
    ("LH-101", "Lecture Hall 101", 120, ["lecture"], ["projector", "whiteboard", "sound_system"]),
    ("CB-201", "Classroom 201", 80, ["lecture"], ["projector", "whiteboard"]),
    ("CB-205", "Classroom 205", 50, ["lecture"], ["projector"]),
    ("LAB-301", "Computer Lab 301", 45, ["lab"], ["computers", "projector", "whiteboard"]),
    ("CR-210", "Computer Classroom 210", 40, ["lecture"], ["computers", "projector"]),
    ("SR-401", "Seminar Room 401", 40, ["seminar"], ["projector", "smartboard", "video_conf"]),
    ("GR-501", "Group Studio 501", 30, ["group"], ["whiteboard", "projector"]),
    ("MR-601", "Meeting Room 601", 20, ["meeting"], ["video_conf", "whiteboard"]),
    ("FX-110", "Flex Room 110", 60, ["lecture", "group"], ["projector"]),
]

TIGHT_HOURS = range(9, 15)   # 09:00-14:00 -> 30 slots, half of them afternoon

# Narrower windows: 10-18 slots each instead of 15-45.
TIGHT_AVAILABILITY_PATTERNS = [
    ([0, 1, 2], (9, 12)),       # mornings only
    ([2, 3, 4], (12, 15)),      # afternoons only
    ([0, 2, 4], (9, 15)),       # full days
    ([1, 3], (12, 15)),         # afternoons only
    ([0, 1, 3, 4], (9, 12)),    # mornings only
    ([1, 2, 4], (9, 15)),       # full days
    ([0, 3], (12, 15)),         # afternoons only
]

# session_type -> (essential equipment, preferred equipment)
EQUIPMENT_RULES = {
    "lecture": (["projector"], ["whiteboard", "sound_system"]),
    "lab": (["computers"], ["projector", "whiteboard"]),
    "seminar": (["projector"], ["video_conf", "smartboard"]),
    "group": (["whiteboard"], ["smartboard", "projector"]),
    "meeting": (["video_conf"], ["whiteboard", "smartboard"]),
}

# Enrolment ranges kept inside what the rooms for that type can hold (H4).
SIZE_RANGES = {
    "lecture": (30, 100),
    "lab": (18, 40),
    "seminar": (15, 32),
    "group": (12, 24),
    "meeting": (8, 14),
}

# How the course mix is distributed.
SESSION_MIX = (
    ["lecture"] * 50 + ["lab"] * 18 + ["seminar"] * 6 + ["group"] * 4 + ["meeting"] * 2
)

# Tight profile leans hard on labs: only LAB-301 is a real lab, so demand spills
# into CR-210 (has computers, satisfies H6, but is not a lab) and pays S4.
TIGHT_SESSION_MIX = (
    ["lecture"] * 38 + ["lab"] * 30 + ["seminar"] * 8 + ["group"] * 3 + ["meeting"] * 1
)

SUBJECTS = [
    ("CSC", "Computer Science"), ("INT", "Information Technology"),
    ("SWE", "Software Engineering"), ("DSI", "Data Science"), ("MTH", "Mathematics"),
]
TOPICS = [
    "Programming Fundamentals", "Data Structures", "Algorithms", "Database Systems",
    "Operating Systems", "Computer Networks", "Software Design", "Web Development",
    "Mobile Development", "Machine Learning", "Artificial Intelligence", "Cloud Computing",
    "Cyber Security", "Human-Computer Interaction", "Discrete Mathematics", "Linear Algebra",
    "Statistics for Computing", "Computer Architecture", "Compiler Design", "Distributed Systems",
    "Big Data Analytics", "Deep Learning", "Software Testing", "Project Management",
    "Digital Image Processing", "Natural Language Processing", "Embedded Systems",
    "Information Retrieval", "Blockchain Technology", "DevOps Practices",
]
FIRST_NAMES = [
    "Somchai", "Suphaporn", "Anong", "Kittipong", "Narumon", "Prasert", "Wanida",
    "Thanakorn", "Siriporn", "Chaiwat", "Malee", "Nattapong", "Pimchanok", "Worarat",
    "Apinya", "Decha", "Kanya", "Rattana", "Suchart", "Ubon", "Yupin", "Sarawut",
    "Chalermchai", "Duangjai", "Ekkachai", "Fonthip", "Guntapong", "Hathairat",
    "Itthipol", "Jariya", "Kamon", "Lawan", "Manop", "Nipaporn", "Orawan",
]
LAST_NAMES = [
    "Wattana", "Srisai", "Chanthana", "Boonmee", "Ratanakul", "Suwanna", "Phong",
    "Intara", "Kaewkla", "Thongchai", "Sanguan", "Pattana", "Rojana", "Krathu",
    "Wongsa", "Charoen", "Limthong", "Nakorn", "Pruksa", "Sirikul", "Tavee",
    "Udom", "Viriya", "Wanich", "Yodsawat", "Achara", "Bunnag", "Chaiyo",
    "Damrong", "Euaporn", "Fongchai", "Gaysorn", "Hemmarat", "Iamsuri", "Jindarat",
]

# Availability patterns (day set, hour range) - all >= 15 slots so an instructor
# with up to 3 courses always has room (H5 + H1 stay satisfiable).
AVAILABILITY_PATTERNS = [
    ([0, 1, 2, 3, 4], (8, 17)),   # full week
    ([0, 1, 2, 3, 4], (8, 13)),   # mornings only
    ([0, 1, 2, 3, 4], (12, 17)),  # afternoons only
    ([0, 2, 4], (8, 17)),         # Mon/Wed/Fri
    ([1, 3], (8, 17)),            # Tue/Thu
    ([0, 1, 2], (9, 16)),         # early week
    ([2, 3, 4], (9, 16)),         # late week
]


def clear(session):
    session.execute(db.text("""
        TRUNCATE course_assignment, course_equipment_requirement,
                 instructor_availability, room_equipment, course, schedule,
                 room, instructor, equipment, time_slot, constraint_config
        RESTART IDENTITY CASCADE
    """))
    session.commit()


def seed(n_courses, n_instructors, max_courses_per_instructor=3, tight=False):
    rng = random.Random(RNG_SEED)
    session = db.session

    room_spec = TIGHT_ROOMS if tight else ROOMS
    hours = TIGHT_HOURS if tight else HOURS
    patterns = TIGHT_AVAILABILITY_PATTERNS if tight else AVAILABILITY_PATTERNS

    # --- time slots -------------------------------------------------------
    slots = [TimeSlot(day=d, hour=h) for d in DAYS for h in hours]
    session.add_all(slots)
    session.flush()

    # --- equipment --------------------------------------------------------
    equipment = {code: Equipment(code=code, name=name) for code, name in EQUIPMENT}
    session.add_all(equipment.values())
    session.flush()

    # --- rooms ------------------------------------------------------------
    rooms = []
    for code, name, cap, caps, eq_codes in room_spec:
        room = Room(
            code=code, name=name, capacity=cap,
            supports_lecture="lecture" in caps,
            supports_lab="lab" in caps,
            supports_group="group" in caps,
            supports_seminar="seminar" in caps,
            supports_meeting="meeting" in caps,
        )
        session.add(room)
        session.flush()
        session.add_all([
            RoomEquipment(room_id=room.id, equipment_id=equipment[c].id) for c in eq_codes
        ])
        rooms.append(room)

    # --- instructors ------------------------------------------------------
    instructors = []
    used_names = set()
    for i in range(n_instructors):
        while True:
            name = f"Dr. {rng.choice(FIRST_NAMES)} {rng.choice(LAST_NAMES)}"
            if name not in used_names:
                used_names.add(name)
                break
        days, (h_lo, h_hi) = patterns[i % len(patterns)]
        prefer_morning = rng.random() < 0.55
        if tight:
            # Drawn from the whole week, NOT from the instructor's free days, so
            # S2 is not satisfiable for free.
            preferred_days = sorted(rng.sample(list(DAYS), rng.choice([2, 3])))
        else:
            preferred_days = sorted(rng.sample(days, min(len(days), rng.choice([2, 3]))))

        inst = Instructor(
            name=name,
            email=f"{name.split()[1].lower()}.{name.split()[2].lower()}@kmutt.ac.th",
            prefer_morning=prefer_morning,
            preferred_days=preferred_days,
        )
        session.add(inst)
        session.flush()
        session.add_all([
            InstructorAvailability(instructor_id=inst.id, time_slot_id=s.id)
            for s in slots if s.day in days and h_lo <= s.hour < h_hi
        ])
        instructors.append(inst)

    # --- courses ----------------------------------------------------------
    source_mix = TIGHT_SESSION_MIX if tight else SESSION_MIX
    mix = [source_mix[i % len(source_mix)] for i in range(n_courses)]
    rng.shuffle(mix)

    load = {inst.id: 0 for inst in instructors}
    used_codes = set()
    topic_seen = {}
    courses = []
    for i, session_type in enumerate(mix):
        eligible = [x for x in instructors if load[x.id] < max_courses_per_instructor]
        if not eligible:                       # widen if the cap is exhausted
            eligible = instructors
        inst = min(eligible, key=lambda x: load[x.id])
        load[inst.id] += 1

        prefix, _ = SUBJECTS[i % len(SUBJECTS)]
        topic = TOPICS[i % len(TOPICS)]
        for attempt in range(200):
            code = f"{prefix}{rng.randint(1, 4)}{rng.randint(0, 9)}{rng.randint(0, 9)}"
            if code not in used_codes:
                used_codes.add(code)
                break
        lo, hi = SIZE_RANGES[session_type]

        # Repeated topics are separate sections, as in a real catalogue.
        topic_seen[topic] = topic_seen.get(topic, 0) + 1
        title = topic if session_type == "lecture" else f"{topic} ({session_type.title()})"
        if topic_seen[topic] > 1:
            title = f"{title} - Sec. {topic_seen[topic]}"

        course = Course(
            code=code,
            name=title,
            instructor_id=inst.id,
            duration_hours=1,
            expected_students=rng.randint(lo, hi),
            session_type=session_type,
        )
        session.add(course)
        session.flush()

        essential, preferred = EQUIPMENT_RULES[session_type]
        reqs = [
            CourseEquipmentRequirement(
                course_id=course.id, equipment_id=equipment[c].id, is_essential=True
            ) for c in essential
        ]
        # Only some courses bother listing nice-to-haves, so S3 varies.
        for c in preferred:
            if rng.random() < 0.6:
                reqs.append(CourseEquipmentRequirement(
                    course_id=course.id, equipment_id=equipment[c].id, is_essential=False
                ))
        session.add_all(reqs)
        courses.append(course)

    ConstraintConfig.get()
    session.commit()
    return slots, list(equipment.values()), rooms, instructors, courses


def preflight(slots, rooms, instructors, courses):
    """Prove the instance is not trivially infeasible before the solver runs."""
    print("\n--- feasibility pre-flight ---")
    ok = True

    # H4 + H6: every course needs at least one room with capacity and essential kit.
    room_eq = {r.id: r.equipment_ids for r in rooms}
    blocked = []
    for c in courses:
        need = c.essential_equipment_ids
        fits = [r for r in rooms
                if r.capacity >= c.expected_students and need <= room_eq[r.id]]
        if not fits:
            blocked.append(c)
    if blocked:
        ok = False
        print(f"  [FAIL] {len(blocked)} course(s) have no room satisfying H4+H6:")
        for c in blocked[:5]:
            print(f"         {c.code} {c.session_type} students={c.expected_students}")
    else:
        print(f"  [ok]   all {len(courses)} courses have >=1 room satisfying H4 + H6")

    # H5 + H1: instructor must have at least as many free slots as courses.
    load = {}
    for c in courses:
        load[c.instructor_id] = load.get(c.instructor_id, 0) + 1
    tight = [i for i in instructors if len(i.available_slot_ids) < load.get(i.id, 0)]
    if tight:
        ok = False
        print(f"  [FAIL] {len(tight)} instructor(s) have fewer free slots than courses")
    else:
        worst = max(instructors, key=lambda i: load.get(i.id, 0) / max(len(i.available_slot_ids), 1))
        print(f"  [ok]   every instructor has enough free slots "
              f"(tightest: {worst.name} {load.get(worst.id, 0)} course(s) "
              f"/ {len(worst.available_slot_ids)} slots)")

    # Capacity headroom: room-slots vs courses.
    capacity = len(rooms) * len(slots)
    print(f"  [ok]   {len(courses)} courses into {len(rooms)} rooms x {len(slots)} slots "
          f"= {capacity} room-slots ({len(courses) / capacity:.1%} utilisation)")

    # S4 reachability: is a supporting room available per session type?
    print("\n--- per session type ---")
    by_type = {}
    for c in courses:
        by_type.setdefault(c.session_type, []).append(c)
    for st in sorted(by_type):
        cs = by_type[st]
        supporting = [r for r in rooms if r.supports(st)]
        need = set().union(*[c.essential_equipment_ids for c in cs])
        both = [r for r in supporting if need <= room_eq[r.id]]
        print(f"  {st:8} {len(cs):3} courses | {len(supporting):2} rooms support it "
              f"| {len(both):2} also have essential kit | max size {max(c.expected_students for c in cs)}"
              f" vs best room {max((r.capacity for r in supporting), default=0)}")
    return ok


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--reset", action="store_true", help="truncate all tables first")
    ap.add_argument("--size", choices=["small", "default", "large"], default="default")
    ap.add_argument("--courses", type=int, help="override course count")
    ap.add_argument("--instructors", type=int, help="override instructor count")
    ap.add_argument("--tight", action="store_true",
                    help="scarce rooms/slots/equipment so S2-S4 actually bite")
    args = ap.parse_args()

    presets = {"small": (20, 8), "default": (80, 35), "large": (120, 45)}
    n_courses, n_instructors = presets[args.size]
    n_courses = args.courses or n_courses
    n_instructors = args.instructors or n_instructors

    app = create_app()
    with app.app_context():
        if args.reset:
            clear(db.session)
            print("cleared existing data")
        else:
            if db.session.query(Course).count():
                sys.exit("Database already has courses. Re-run with --reset.")

        slots, equipment, rooms, instructors, courses = seed(
            n_courses, n_instructors, tight=args.tight)

        print(f"\nseeded [{'tight' if args.tight else 'loose'}]: {len(courses)} courses, "
              f"{len(instructors)} instructors, {len(rooms)} rooms, {len(slots)} time slots, "
              f"{len(equipment)} equipment types")

        ok = preflight(slots, rooms, instructors, courses)
        print("\n" + ("PRE-FLIGHT PASSED - instance should be feasible"
                      if ok else "PRE-FLIGHT FAILED - instance is infeasible as seeded"))
        sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
