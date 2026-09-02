# Chronos — Project Context

> Last revised: 2026-09-02, after supervisor meeting. See **Supervisor Notes** at the bottom
> for what changed and why.

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
Decision variable: `x[c, r, t] ∈ {0,1}` — assign course c to room r at timeslot t

**Hard constraints (must satisfy):**
- H1: Each course scheduled exactly once
- H2: No room double-booking
- H3: No instructor double-booking
- H4: Room capacity ≥ course enrollment
- H5: Instructor availability respected
- H6: Room provides every piece of equipment the course marks **essential**

**Soft objective (minimize):**
`Z = Σ [w1·S1(c,t) + w2·S2(c,t) + w3·S3(c,r) + w4·S4(c,r)] · x[c,r,t]`

| Term | Penalty for | Depends on | Weight |
|---|---|---|---|
| S1 | class after 12:00 when instructor prefers mornings | (c, t) | w1 |
| S2 | class on a non-preferred day | (c, t) | w2 |
| S3 | each **preferred** (non-essential) equipment item the room lacks | (c, r) | w3 |
| S4 | room does not support the course's session type | (c, r) | w4 |

**Implementation note:** S1/S2 are time-indexed, S3/S4 are room-indexed, but all four attach
to the same `x[c,r,t]` variable. The existing prototype already accumulates penalties per
`(c, r, t)` triple and calls `LinearExpr.WeightedSum`, so S3/S4 slot in without restructuring
the model — see `solve_ortools()` in `docs/research/experiments/experiment_instructor_constraints.py`.

**Infeasibility:** H6 can make an instance genuinely unsolvable (e.g. a course needs essential
lab equipment no room has). `POST /generate` must detect this and report *which* course could
not be placed and *why*, rather than returning a bare failure.

## Database Entities
| Entity | Purpose |
|---|---|
| `Course` | code, name, instructor_id, duration_hours, expected_students, **session_type** |
| `Instructor` | name, prefer_morning, preferred_days |
| `InstructorAvailability` | (instructor, timeslot) rows — hard availability |
| `Room` | code, capacity, **capability flags** (see below) |
| `TimeSlot` | day, hour |
| `Equipment` | catalog of equipment types (projector, computers, whiteboard, …) |
| `RoomEquipment` | join: which equipment a room has |
| `CourseEquipmentRequirement` | join: course → equipment, with **`is_essential`** flag |
| `Schedule` | a generated run |
| `CourseAssignment` | join: Schedule + Course + Room + TimeSlot |
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
- Solver: `POST /generate` → runs CP-SAT, returns schedule **or infeasibility diagnostic**
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

`backend/scripts/seed.py` produces two profiles, both deterministic (RNG seed 20260902):

| | rooms | slots | utilisation | what it exercises |
|---|---|---|---|---|
| default (loose) | 20 | 45 | ~9% | realistic faculty; only S1 ever binds |
| `--tight` | 9 | 30 | ~30% | all of S1–S4 bind; use for demos and experiments |

The loose profile has so much slack that S2/S3/S4 are satisfiable for free and
score zero regardless of weight — fine as a realistic dataset, useless for showing
the constraints do anything. `--tight` cuts rooms to 9 (only **one** real lab),
halves the slots, uses morning-only/afternoon-only instructors, draws
`preferred_days` independently of availability, and raises lab demand to 30 so it
overflows into CR-210 (has computers, so H6 holds, but is not a lab, so S4 is paid).

### Priority order
1. ~~Models + first migration (11 tables, no `User`)~~ — **done 2026-09-02**, revision `6f50d42afae8`
2. ~~Seed script with realistic KMUTT-scale data~~ — **done 2026-09-02**, `backend/scripts/seed.py` (deterministic, with feasibility pre-flight)
3. ~~Port solver into `backend/app/solver/`, add H6 + S3 + S4~~ — **done 2026-09-03**
   (`problem.py` loader, `cpsat.py` model, `preflight.py` diagnostics, `service.py` orchestration)
4. ~~CRUD blueprints, then `POST /generate`~~ — **done 2026-09-03**, 38 routes under `/api`
   (`backend/app/api/`; dev server on **port 5001** — 5000 is taken by macOS AirPlay)
5. ~~Frontend: Timetable first, then the CRUD pages~~ — **done 2026-09-03**
   (`frontend/src/pages/`; React 19 + react-router, Vite proxies `/api` to Flask on 5001)

### Running it

```bash
# terminal 1 - API
cd backend && ./.venv/bin/python wsgi.py        # http://127.0.0.1:5001

# terminal 2 - web
cd frontend && npm run dev                       # http://localhost:5173
```

Note: **use `localhost`, not `127.0.0.1`** for the frontend — Vite binds IPv6 (`::1`)
only. And the API is on **5001**: macOS ControlCenter (AirPlay Receiver) owns 5000
and answers 403, which looks like a broken app rather than a port clash.

### Remaining

- No automated tests (`pytest` is installed but unused; the API is now the frontend's contract)
- Multi-hour courses (`duration_hours > 1`) unsupported — pre-flight rejects them explicitly
- Auth deferred (`User`, `/auth/*`, login page)
