# Chronos — Project Context

> Last revised: 2026-11-14 (partial schedules, multi-hour classes, cross-platform setup).
> See **Supervisor Notes** for the 2026-09-02 decisions and
> `docs/superpowers/specs/2026-11-14-partial-schedules-design.md` for the latest design.

## What it is
Web-based automated academic timetabling system using constraint programming.
Capstone project for Aung Moe Lin (ID: 66130500803), KMUTT School of IT.

## Stack
| Layer | Tech |
|---|---|
| Frontend | React + TypeScript |
| Backend | Python Flask (REST API) |
| Database | PostgreSQL (local for dev, self-hosted on Hetzner VPS for prod) |
| Solver | Google OR-Tools CP-SAT |

## Core Algorithm
A course meets `classes_per_week` times (default 1). Each class is one continuous block of
`duration_hours`, in one room, on one day. Two classes of one course fall on different days.

Decision variable: `x[class, r, t] ∈ {0,1}` — the class starts in room r at timeslot t

**Hard constraints (never broken):**
- H1: Each class scheduled **at most** once (see *Partial schedules*)
- H2: No room double-booking, for every hour a block covers
- H3: No instructor double-booking, for every hour a block covers
- H4: Room capacity ≥ course enrollment
- H5: Instructor available for the whole block
- H6: Room provides every piece of equipment the course marks **essential**

**Soft objective (minimize):**
`Z = Σ [w1·S1(c,t) + w2·S2(c,t) + w3·S3(c,r) + w4·S4(c,r)] · x[c,r,t]`

| Term | Penalty for | Depends on | Weight |
|---|---|---|---|
| S1 | class after 12:00 when instructor prefers mornings | (c, t) | w1 |
| S2 | class on a non-preferred day | (c, t) | w2 |
| S3 | each **preferred** (non-essential) equipment item the room lacks | (c, r) | w3 |
| S4 | room does not support the course's session type | (c, r) | w4 |

**Partial schedules:** the solver never answers "infeasible". It maximises
`Σ (BIG − penalty) · x`, where BIG exceeds every possible total penalty, so it first places
as many classes as it can and then minimises Z among those schedules. Classes that do not
fit are left out and stored in `Schedule.unscheduled`, each with a reason code, a readable
message and the classes blocking it (`backend/app/solver/explain.py`):

| Code | Meaning |
|---|---|
| `capacity`, `essential_equipment`, `capacity_and_equipment` | no room can ever hold the class |
| `no_block` | no day has that many consecutive slots |
| `availability` | instructor has no window long enough |
| `room_contention` | suitable rooms exist but other classes hold them |
| `instructor_contention` | the instructor is teaching in every window that fits |
| `contention` | a mix of the two above |
| `same_course_day` | no second day free for a twice-a-week course |
| `time_limit` | a free placement exists but the solver ran out of time |

Contention reasons describe what blocks the class in the schedule found; they do not prove
which single change fixes it. Verified what-if suggestions (re-solve with one change) are
the next step — `solve()` takes a plain `Problem`, so a what-if is copy, change, solve again.

S1 on a block: broken if any hour of the block is at 12:00 or later; charged once per class.

## Database Entities
| Entity | Purpose |
|---|---|
| `Course` | code, name, instructor_id, duration_hours (per class), classes_per_week, expected_students, **session_type** |
| `Instructor` | name, prefer_morning, preferred_days |
| `InstructorAvailability` | (instructor, timeslot) rows — hard availability |
| `Room` | code, capacity, **capability flags** (see below) |
| `TimeSlot` | day, hour |
| `Equipment` | catalog of equipment types (projector, computers, whiteboard, …) |
| `RoomEquipment` | join: which equipment a room has |
| `CourseEquipmentRequirement` | join: course → equipment, with **`is_essential`** flag |
| `Schedule` | a generated run; `status` optimal / feasible / partial / failed; `unscheduled` JSON list |
| `CourseAssignment` | one placed class: Schedule + Course + class_index + Room + start TimeSlot + duration_hours |
| `ConstraintConfig` | singleton (id=1) backing the Constraints page: H2–H6 toggles, w1–w4, solver time limit |
| ~~`User`~~ | **deferred** — no auth in v1 |

**Room capability flags** (multi-label — a room may support several):
`supports_lecture`, `supports_lab`, `supports_group`, `supports_seminar`, `supports_meeting`

**Equipment model:** each `CourseEquipmentRequirement` is either
- `is_essential = true` → enforced as **hard** constraint H6, or
- `is_essential = false` → contributes to **soft** penalty S3, one unit per missing item.

## Key Relations
- Course → Instructor (many-to-one)
- Course → Equipment (many-to-many via `CourseEquipmentRequirement`, carries `is_essential`)
- Room → Equipment (many-to-many via `RoomEquipment`)
- Instructor → TimeSlot (many-to-many via `InstructorAvailability`)
- Schedule → CourseAssignment (one-to-many)

## API Endpoints (to build)
- CRUD: `/courses`, `/instructors`, `/rooms`, `/timeslots`, `/equipment`
- `/instructors/:id/availability` — set availability grid
- `/rooms/:id/equipment` — set room equipment
- `/courses/:id/requirements` — set required equipment + essential flags
- Constraints: `/constraints` (weights w1–w4)
- Solver: `POST /generate` → runs CP-SAT, always returns a schedule, with `unscheduled` reasons when partial
- Results: `/schedules`, `/schedules/:id/assignments`
- ~~Auth: `/auth/login`, `/auth/me`~~ — **deferred**

## Frontend Pages
- **Dashboard** — stats overview, recent schedules, Generate button
- **Courses** — full CRUD; session type; equipment requirements w/ essential toggle
- **Instructors** — full CRUD; availability grid + preferences
- **Rooms** — full CRUD; capacity, capability flags, equipment
- **Constraints** — H1–H6 toggles, S1–S4 weight sliders (w1–w4)
- **Timetable** — weekly grid view of generated schedule
- ~~Login~~ — **deferred**

## Users / Roles
- Coordinator (main user — manages everything)
- Administrator

*Deferred: no login in v1. All endpoints are open; roles come after the end-to-end flow works.*

## Solver Flow
1. Frontend sends constraint config → `POST /generate`
2. Flask builds CP-SAT model from DB data
3. OR-Tools solves → returns `x[c,r,t]` assignments (or reports infeasibility)
4. Results saved as `Schedule` + `CourseAssignment` rows
5. Frontend polls/receives schedule, renders timetable grid

## Schedule Output Fields
`schedule_id`, `algorithm`, `hard_violations`, `soft_score`, `optimality_gap`
- `optimality_gap = (Z - Z_LP) / Z_LP` — 0% means provably globally optimal

---

## Supervisor Notes (meeting before 2026-09-02)

| Note | Decision |
|---|---|
| Add room equipment availability as a soft constraint | Adopted, **with an `is_essential` flag**: essential → hard H6, preferred → soft S3 (per-item penalty) |
| Room suitability for group settings / meetings / seminars | Adopted as **multi-label capability flags** on `Room`, matched against `Course.session_type` → soft S4 |
| "Supabase is fine" | Supervisor is indifferent to the DB choice. **Not using Supabase.** Local Postgres for dev, self-hosted Postgres on the Hetzner VPS for prod |
| Show end-to-end scheduling flow; login not needed yet | **Auth deferred.** `User` model, `/auth/*`, and login page are out of v1. v1 = full CRUD → Generate → Timetable |

### v1 scope (the end-to-end demo)
Full CRUD on Courses / Instructors / Rooms / TimeSlots / Equipment → set constraint weights →
Generate → view the timetable grid. No authentication.

### Test instances

`backend/scripts/seed.py` produces three profiles, all deterministic (RNG seed 20260902).
Courses are 1–3 hours long; some lectures meet twice a week.

| | rooms | slots | what it exercises |
|---|---|---|---|
| default (loose) | 20 | 45 | realistic faculty, lots of slack; every class placed |
| `--tight` | 9 | 30 | all of S1–S4 bind; every class still placed |
| `--conflict` | 9 | 30 | tight plus ten `DEMO9xx` courses that cannot all fit — one per reason code. Use for the unhappy-path demo |

### Priority order
1. ~~Models + first migration (11 tables, no `User`)~~ — **done 2026-09-02**, revision `6f50d42afae8`
2. ~~Seed script with realistic KMUTT-scale data~~ — **done 2026-09-02**, `backend/scripts/seed.py` (deterministic, with feasibility pre-flight)
3. ~~Port solver into `backend/app/solver/`, add H6 + S3 + S4~~ — **done 2026-09-03**
   (`problem.py` loader, `cpsat.py` model, `preflight.py` diagnostics, `service.py` orchestration)
4. ~~CRUD blueprints, then `POST /generate`~~ — **done 2026-09-03**, 38 routes under `/api`
   (`backend/app/api/`; dev server on **port 5001** — 5000 is taken by macOS AirPlay)
5. ~~Frontend: Timetable first, then the CRUD pages~~ — **done 2026-09-03**
   (`frontend/src/pages/`; React 19 + react-router, Vite proxies `/api` to Flask on 5001)

### Running it (Windows, macOS, Linux)

Needs Python 3.12, Node 20+, and Docker (or any Postgres server).

```bash
# once
cp .env.example .env                 # holds DATABASE_URL only
docker compose up -d                 # Postgres on localhost:5432
cd backend
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements.txt   # Windows
.venv/bin/python -m pip install -r requirements.txt       # macOS / Linux
```

Below, `PY` means `.venv/Scripts/python` on Windows and `.venv/bin/python` elsewhere.

```bash
# in backend/
PY -m flask --app wsgi db upgrade    # create / update tables
PY scripts/seed.py --reset --conflict   # or --tight, or nothing
PY wsgi.py                           # API on http://127.0.0.1:5001
PY scripts/generate.py               # optional: solve from the command line
PY -m pytest                         # tests (API tests use database chronos_test)

# in frontend/
npm install
npm run dev                          # http://localhost:5173
npx playwright install chromium      # once, for the browser tests
npm run test:e2e                     # browser tests; own servers + database chronos_e2e
                                     # if Windows blocks the download: set E2E_BROWSER=msedge
```

The API listens on 5001 because macOS AirPlay Receiver owns 5000. Open the site as
`localhost`, not `127.0.0.1`.

### Remaining

- Verified what-if suggestions: "Find fixes" rerun on a partial schedule
- AI-written suggestions via OpenRouter, built on the stored reasons
- Per-course priority (which classes to drop first)
- Tests: solver (no database), API (Postgres), browser (Playwright, `frontend/e2e`). No component tests
- Auth deferred (`User`, `/auth/*`, login page) — last phase
