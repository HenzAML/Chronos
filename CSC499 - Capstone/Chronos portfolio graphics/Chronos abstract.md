# Chronos — project abstract

Three lengths, so you can paste whichever the field asks for.

---

## One line (≈15 words)

Chronos turns a semester of courses, instructors and rooms into a conflict-free
timetable in seconds.

---

## Short summary (≈60 words) — for a portfolio card or video description

Chronos is an automated timetabling solution for university departments. It models
a semester as a constraint satisfaction problem and solves it with Google OR-Tools
CP-SAT, producing schedules that respect instructor availability, room capacity and
equipment while scoring soft preferences. A repair mode adapts the timetable when
an input changes, and every run is versioned so alternatives can be compared.

---

## Full abstract (≈250 words) — for the SIT Portfolio

Every semester an academic department must place each course into a room and a time
slot without clashing an instructor, a room, or a class that is already booked. The
number of valid arrangements grows exponentially with the number of courses, rooms
and slots, and the problem is formally NP-hard. Coordinators nevertheless do it by
hand in spreadsheets, spending hours to days each semester, and a conflict found
late forces a partial rebuild that tends to create the next conflict. Nothing in the
manual process measures whether a legal timetable is also a good one.

Chronos is a web application that closes this gap. It models the semester as a
constraint satisfaction problem and solves it with Google OR-Tools CP-SAT. Hard
rules — single placement, no room or instructor double-booking, sufficient capacity
and declared availability — are enforced inside the model, so an invalid timetable
cannot be produced. Instructor and room preferences are handled separately as a
weighted score the coordinator controls, which makes timetable quality something
measurable and tunable rather than a matter of argument.

Beyond generation, Chronos provides a schedule repair mode that adapts an existing
timetable when an input changes, versioning so successive runs can be compared, and
an interactive calendar for review and publication. The system is built entirely
from free and open-source components, so a department can adopt it without licensing
cost. Future work extends the solver into a multi-agent system, where agents
negotiate rescheduling through natural language.

---

**Word counts:** one-line 15 · short 60 · full 248.
