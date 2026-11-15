# Chronos — session handoff (2026-11-15)

Context for the next Claude session. Read this first, then `CHRONOS_CONTEXT.md` (project
reference, kept up to date) and `docs/superpowers/specs/2026-11-14-partial-schedules-design.md`
(the approved design for the solver work).

## What Chronos is

University timetabling capstone (KMUTT SIT, CSC499, CS D-Day 2026). One developer.
Flask 3 + SQLAlchemy 2 + Alembic + PostgreSQL backend, Google OR-Tools CP-SAT solver,
React 19 + TypeScript + Vite frontend. No login yet.

## The user's goal

Demo scheduling "in any way possible", happy and unhappy path, with graceful errors.
The solver must never just say "impossible": it returns the best schedule it can, leaves the
conflicting classes out, and says specifically why each was left out and what to do.

## Decisions the user made (do not reopen)

- A course has `classes_per_week` (default 1, rarely 2). Each class is one continuous block of
  `duration_hours` in one room on one day. Two classes of a course fall on different days.
- Objective: place as many classes as possible first, then minimise the soft score.
  Per-course priority comes later.
- A twice-a-week course may be placed partially (one class in, one left out).
- Reasons now come from blocker analysis of the schedule found. Later: a user-triggered
  "rerun" that re-solves with one change to give verified fixes.
- AI-written suggestions via OpenRouter: later, built on the stored reasons.
- Login: last phase.
- Setup must work on Windows, macOS and Linux. `.env` holds only `DATABASE_URL`.
- Postgres runs in Docker (`docker-compose.yml`).
- Commit on `main`, do not push.
- Design: follow the real poster in `CSC499 - Capstone/Chronos Design/`, "playful like the
  poster" (gradients, wave, big mascot, yellow sparks). Mascot SVG = trace of the JPG with
  the green background removed.

## What was built (all committed on `main`, nothing pushed)

| Commit | What |
|---|---|
| `b3cb77f` | Design spec |
| `ca35882` | Solver rewrite, models, migration, Docker, seed profiles, backend tests |
| `44b539f` | Website shows partial schedules and multi-hour classes; cross-platform docs |
| `edc9c9e` | Playwright browser tests (3 scheduling flows) |
| `b26cb8d` | Browser tests for Rooms, Instructors, Constraints, failure screens; 2 bug fixes |
| `bf6f8d4` | First restyle (indigo, from an early poster) — superseded |
| `43587ac` | Restyle after the real poster; traced SVG logos |

### Solver (`backend/app/solver/`)

- `cpsat.py` — variable `x[class, room, start]`. Each class placed at most once. Room and
  instructor clashes checked for every hour of a block. Objective `maximise Σ (BIG − penalty)·x`
  with BIG larger than any total penalty, so count wins over preference. Never returns
  infeasible. Statuses: `optimal` / `feasible` (all placed), `partial`, `failed` (no data or crash).
- `explain.py` — one reason per unplaced class: code, readable message with a suggestion, and
  the blocking classes. Codes: `capacity`, `essential_equipment`, `capacity_and_equipment`,
  `no_block`, `availability`, `no_instructor`, `room_contention`, `instructor_contention`,
  `contention`, `same_course_day`, `time_limit`.
- `problem.py` — plain dataclasses; `solve()` never touches the database. This is the hook for
  the later what-if rerun: copy the `Problem`, change one thing, solve again.
- `service.py` — loads from the DB, solves, saves `Schedule.unscheduled` (JSON) and
  assignments with `class_index` and `duration_hours`. A solver crash becomes a `failed`
  schedule with a message.
- `preflight.py` was deleted; `explain.py` replaces it.

### Data and API

- New columns: `Course.classes_per_week`, `CourseAssignment.class_index` / `duration_hours`,
  `Schedule.unscheduled`; status `partial`. Migration
  `backend/migrations/versions/a1c2e3f4b5d6_classes_per_week_partial_schedules.py`.
- `POST /api/generate` always returns a schedule; the grid endpoint includes `unscheduled`.
- `requirements.txt` pins `SQLAlchemy>=2.0,<2.1` (2.1 defaults to psycopg3, which is not installed).
- `backend/scripts/seed.py --reset [--tight | --conflict]`. `--conflict` adds ten `DEMO9xx`
  courses that cannot all fit, one per reason type: 86 of 93 classes placed, 7 left out.
- `backend/scripts/generate.py` — solve from the command line and print reasons.

### Website (`frontend/src/`)

- Dashboard and Timetable show a warning panel listing each left-out class with its reason.
- Timetable draws a multi-hour class in every hour it covers; later hours faded with "cont.".
- Courses form has class length and classes per week.
- Constraints "Preview effect" handles partial results (was a bug: said "no timetable").
- `Field` in `components/ui.tsx` takes `group` for multi-control groups (was a bug: a label
  around a group sent clicks on the caption to the first control).
- Theme: tokens in `index.css`, components in `App.css`. Blue `#0b6fe0` / `#1c94fc`, navy
  `#01204b`, yellow `#fec60d`, sky tints. Poppins (display) and Inter (body), bundled via
  `@fontsource`, no CDN.
- Assets in `frontend/public/`: `chronos-wordmark.svg`, `chronos-mascot.svg`, `favicon.svg`
  (the mascot).

### Tests

- Backend: 25 pass. `backend/tests/test_solver.py` (17, no database) and `test_api.py`
  (8, Postgres database `chronos_test`, created automatically).
- Browser: 12 pass. `frontend/e2e/scheduling.spec.ts` and `pages.spec.ts`. They start their own
  API (port 5002) and Vite (5174) on database `chronos_e2e`; dev data is untouched.
- TDD was red-first for the solver only. API tests were written after the code.

## How to run

```bash
docker compose up -d                              # Postgres on localhost:5432
# backend/   (Windows: .venv/Scripts/python, else .venv/bin/python)
PY -m flask --app wsgi db upgrade
PY scripts/seed.py --reset --conflict             # or --tight, or nothing
PY wsgi.py                                        # API on http://127.0.0.1:5001
PY -m pytest
# frontend/
npm run dev                                       # http://localhost:5173
E2E_BROWSER=msedge npm run test:e2e               # PowerShell: $env:E2E_BROWSER='msedge'
```

## Gotchas on this machine (Windows 11)

- Docker Desktop is often not running. Start it, wait for `docker info`, then `docker compose up -d`.
- Windows Application Control blocks Playwright's downloaded browsers (unsigned). Use the
  installed browser: `E2E_BROWSER=msedge` or `chrome`. Do not try to bypass the policy.
- Git Bash heredocs with mixed quotes or backticks fail to parse. Write files with the
  Write tool, or put patch scripts in a file and run them.
- Dev servers started by a session die when the session ends; restart them.
- The dev database currently holds the `--conflict` seed.

## Known issues and gaps

- One Chrome e2e run failed 6 of 12 (tests 7–12 in a row); three reruns passed. Cause unknown.
- Mascot SVG is a trace of a 626 px JPG: slightly soft edges, nose dark maroon instead of red,
  449 KB. A larger source would trace better.
- The class detail box on the Timetable floats over the bottom-right of the grid.
- A multi-hour class is one chip per hour, not one tall box.
- Not tested: Firefox, Safari, macOS, Linux, phone-size screens, a solve that hits the time
  limit. Rooms page and course form were not looked at in the final design.
- No frontend unit tests. One old lint warning in `frontend/src/pages/Timetable.tsx` (setState
  in an effect).
- `docs/research/README.md` is stale.
- `CSC499 - Capstone/` (personal documents, posters, logos) and `__MACOSX/` sit in the repo
  folder untracked. Left out of git on purpose; the user has not said whether to ignore them.
  The traced SVG originals live only there: `Chronos Design/Chronos Typography Logo.svg` and
  `Chronos Mascot Logo.svg`.

## Plan: what comes next (not started; wait for the user)

1. User reviews the website by hand and sends a round of fixes.
2. Verified what-if suggestions: a "Find fixes" button on a partial schedule, e.g.
   `POST /schedules/:id/suggestions`. For each left-out class, try single changes (free a
   room, widen availability, shorten the class), re-solve, and report the ones that work.
3. AI-written suggestions through OpenRouter, using the stored reasons and verified fixes.
4. Per-course priority: which classes to drop first when not all fit.
5. Login (`User`, `/auth/*`, login page) — last.

## How the user likes to work

- Short, plain answers ("caveman" style was requested). Say what was skipped or not checked.
- Smallest change that fully solves the task ("ponytail" mode): no extra features or abstractions.
- Asks for clarifying questions before big work, then is often away: batch questions, then build.
- Wants automated tests for everything.
