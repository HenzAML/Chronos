# Partial schedules, multi-hour classes, specific reasons

Date: 2026-11-14. Status: approved by Henry in session, built straight after.

## Goal

The solver must always return the best schedule it can. When classes cannot all
fit, it leaves the conflicted ones out and says exactly why, per class. It never
answers with a bare "infeasible".

## Decisions

| Question | Decision |
|---|---|
| Multi-hour courses | A course has `classes_per_week` (default 1). Each class is one continuous block of `duration_hours`, one day, one room. |
| Two classes a week | Same length, must fall on different days. |
| What gets left out | Place as many classes as possible; all courses count equally. Ties broken by preference score. Per-course priority comes later. |
| Half-placed course | Allowed. Each class is placed on its own; "1 of 2 classes placed" is a valid result. |
| Reasons | Blocker analysis of the final schedule (below). Verified what-if reruns come later; the design leaves the hook. |
| Morning preference on a block | Broken if any hour of the block is at 12:00 or later. Charged once per class. |

## Data model (one migration)

- `course.classes_per_week` int, default 1, > 0.
- `course_assignment.class_index` int (1-based) and `duration_hours` int (copied
  from the course at solve time, so old schedules survive course edits).
  `time_slot_id` is the start hour. Unique key becomes
  (schedule, course, class_index).
- `schedule.unscheduled` JSON list. One entry per class left out:
  `{course_id, course_code, course_name, class_index, code, message, blockers}`.
- `schedule.status` adds `partial`. `optimal`/`feasible` now mean every class was
  placed. `failed` is only for no data or a solver crash. `infeasible` stays in
  the allowed set for old rows but is no longer produced.

## Solver model

Variable `x[class, room, start]`, created only when:

- the block's hours exist as consecutive slots on one day,
- the instructor is available for every hour (H5),
- the room is big enough (H4) and has the essential equipment (H6).

Constraints:

- each class placed at most once,
- H2: per room and hour, at most one covering block,
- H3: per instructor and hour, at most one covering block,
- classes of one course: at most one per day.

Objective, one solve: `minimise BIG * unplaced + soft`, where `BIG` is larger
than the sum of every class's worst soft penalty. So the solver first places the
most classes, then optimises preferences. The empty schedule is always valid, so
CP-SAT cannot return INFEASIBLE.

## Reasons (`app/solver/explain.py`)

For each unplaced class:

- **No candidate placement** - structural. Codes: `capacity`,
  `essential_equipment`, `capacity_and_equipment`, `no_block` (no day has that
  many consecutive slots), `availability` (instructor has no slots or no window
  long enough), `no_instructor`.
- **Candidates exist, all blocked** - contention. For each candidate, record
  which placed class holds the room or the instructor during the block. Codes:
  `room_contention`, `instructor_contention`, `contention` (mixed),
  `same_course_day`. `blockers` lists
  `{kind: room|instructor, course_code, class_index, room_code, day, hour, duration_hours}`.
  The message names the qualifying rooms and who holds them when.
- If the solver stopped on the time limit and a candidate is actually free, the
  code is `time_limit` and the message says to raise the limit.

Reasons describe what blocks the class in this schedule. They do not prove which
single change fixes it; that is the later what-if rerun.

## Hook for verified suggestions (not built now)

`solve()` takes a plain `Problem`, so a what-if is: copy the problem, change one
thing, solve again. The stored `blockers` say which changes are worth trying. A
later endpoint (`POST /schedules/:id/suggestions`) does this on user request.

## API

- `POST /generate` always returns 200 with a schedule. New fields: `unscheduled`,
  `unscheduled_count`, `class_count`.
- Assignment JSON gains `class_index`, `duration_hours`, `end_hour`.
- Grid endpoint lists a block under its start hour; `hours` covers every hour a
  block touches.
- Courses accept and return `classes_per_week`.

## Website

- Timetable: blocks span their hours; a panel lists unscheduled classes with
  reasons; partial status is flagged.
- Dashboard: generate result shows placed/unplaced counts and reasons.
- Courses: `duration_hours` and `classes_per_week` fields.

## Setup

- `docker-compose.yml` with Postgres for any OS. `.env` holds `DATABASE_URL` only.
- Run notes cover Windows, macOS, Linux.

## Seed data

- Default and `--tight` profiles gain multi-hour and twice-a-week courses.
- New `--conflict` profile yields unscheduled classes of each reason type.

## Tests

Seams: `solve(problem, weights, toggles)` (no database, hand-built problems) and
the HTTP API (Flask test client against a Postgres test database).

- Solver: happy path, each structural reason, room contention, instructor
  contention, blocks do not overlap, twice-a-week on different days, partial
  placement, places the maximum number, each rule switched off.
- API: generate happy path, generate partial path, courses CRUD with the new
  field, grid shape, error responses.

## Out of scope

AI suggestions (OpenRouter), what-if reruns, per-course priority, login.
