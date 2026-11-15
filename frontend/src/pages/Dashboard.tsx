import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../api/client'
import { useAsync } from '../components/useAsync'
import { ErrorBox, Spinner, StatusBadge, UnscheduledList } from '../components/ui'
import type { Course, Instructor, Room, Schedule, TimeSlot } from '../types'

interface Overview {
  courses: Course[]
  instructors: Instructor[]
  rooms: Room[]
  slots: TimeSlot[]
  schedules: Schedule[]
}

export default function Dashboard() {
  const nav = useNavigate()
  const { data, error, loading, reload } = useAsync<Overview>(async () => {
    const [courses, instructors, rooms, slots, schedules] = await Promise.all([
      api.courses.list(), api.instructors.list(), api.rooms.list(),
      api.timeslots.list(), api.schedules.list(),
    ])
    return { courses, instructors, rooms, slots, schedules }
  }, [])

  const [running, setRunning] = useState(false)
  const [runError, setRunError] = useState<unknown>(null)
  const [lastRun, setLastRun] = useState<Schedule | null>(null)

  async function generate() {
    setRunning(true)
    setRunError(null)
    try {
      const schedule = await api.generate({ name: `Run ${new Date().toLocaleString()}` })
      setLastRun(schedule)
      reload()
    } catch (e) {
      setRunError(e)
    } finally {
      setRunning(false)
    }
  }

  if (loading) return <Spinner />
  if (error) return <ErrorBox error={error} onRetry={reload} />
  if (!data) return null

  const { courses, instructors, rooms, slots, schedules } = data
  const capacity = rooms.length * slots.length
  // Room-hours the catalogue needs: every class of every course, full length.
  const demand = courses.reduce((n, c) => n + c.duration_hours * c.classes_per_week, 0)

  return (
    <>
      <header className="page-head hero">
        <img className="hero-mascot" src="/chronos-mascot.svg" alt="" />
        <div>
          <h1>Dashboard</h1>
          <p className="hero-tag">Smarter schedules. Better learning.</p>
          <p className="muted">Overview and schedule generation.</p>
        </div>
        <button className="btn btn-primary" onClick={generate} disabled={running || !courses.length}>
          {running ? 'Solving…' : 'Generate schedule'}
        </button>
      </header>

      {runError && <ErrorBox error={runError} />}
      {lastRun && <RunResult schedule={lastRun} onView={() => nav('/timetable')} />}

      <section className="tiles">
        <Tile label="Courses" value={courses.length} to="/courses" nav={nav} />
        <Tile label="Instructors" value={instructors.length} to="/instructors" nav={nav} />
        <Tile label="Rooms" value={rooms.length} to="/rooms" nav={nav} />
        <Tile label="Time slots" value={slots.length} />
        <Tile label="Room-slots" value={capacity}
          hint={capacity ? `${((demand / capacity) * 100).toFixed(0)}% needed by classes` : undefined} />
        <Tile label="Schedules" value={schedules.length} to="/timetable" nav={nav} />
      </section>

      <section className="panel">
        <h2>Recent schedules</h2>
        {schedules.length === 0
          ? <p className="muted">Nothing generated yet.</p>
          : (
            <table className="table">
              <thead>
                <tr><th>#</th><th>Name</th><th>Status</th><th>Z</th><th>Gap</th>
                    <th>Time</th><th>Classes placed</th><th /></tr>
              </thead>
              <tbody>
                {schedules.slice(0, 8).map((s) => (
                  <tr key={s.id}>
                    <td>{s.id}</td>
                    <td>{s.name ?? <span className="muted">untitled</span>}</td>
                    <td><StatusBadge status={s.status} /></td>
                    <td>{s.soft_score ?? '—'}</td>
                    <td>{s.optimality_gap === null ? '—'
                      : s.optimality_gap === 0 ? '0%' : `${(s.optimality_gap * 100).toFixed(1)}%`}</td>
                    <td>{s.solve_seconds !== null ? `${s.solve_seconds.toFixed(2)}s` : '—'}</td>
                    <td>{s.assignment_count} / {s.class_count}</td>
                    <td><button className="btn btn-sm" onClick={() => nav('/timetable')}>View</button></td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
      </section>
    </>
  )
}

function Tile(
  { label, value, hint, to, nav }:
  { label: string; value: number; hint?: string; to?: string; nav?: (p: string) => void },
) {
  const clickable = to && nav
  return (
    <div className={`tile${clickable ? ' tile-link' : ''}`}
      onClick={clickable ? () => nav!(to!) : undefined}>
      <span className="tile-value">{value}</span>
      <span className="tile-label">{label}</span>
      {hint && <span className="tile-hint">{hint}</span>}
    </div>
  )
}

function RunResult({ schedule, onView }: { schedule: Schedule; onView: () => void }) {
  const complete = schedule.status === 'optimal' || schedule.status === 'feasible'
  const ok = complete || schedule.status === 'partial'
  const pb = schedule.diagnostics?.penalty_breakdown
  const left = schedule.unscheduled ?? []
  return (
    <div className={`alert ${complete ? 'alert-ok' : ok ? 'alert-warn' : 'alert-error'}`}>
      <div className="run-head">
        <strong>
          {complete ? `Schedule #${schedule.id} generated — ${schedule.status}`
            : ok ? `Schedule #${schedule.id}: best timetable found, ${left.length} of ${schedule.class_count} classes left out`
            : 'No timetable produced'}
        </strong>
        {ok && <button className="btn btn-sm" onClick={onView}>Open timetable</button>}
      </div>
      {ok ? (
        <>
          <p>
            Z = {schedule.soft_score} · {schedule.assignment_count} of {schedule.class_count} classes placed ·{' '}
            {schedule.solve_seconds?.toFixed(2)}s
            {schedule.optimality_gap === 0 && ' · proven optimal'}
          </p>
          {pb && (
            <ul className="penalties">
              <li>S1 mornings <b>{pb.S1_morning}</b> <span className="muted">({pb.S1_morning_count})</span></li>
              <li>S2 days <b>{pb.S2_preferred_day}</b> <span className="muted">({pb.S2_preferred_day_count})</span></li>
              <li>S3 equipment <b>{pb.S3_equipment}</b> <span className="muted">({pb.S3_equipment_count})</span></li>
              <li>S4 room type <b>{pb.S4_room_type}</b> <span className="muted">({pb.S4_room_type_count})</span></li>
            </ul>
          )}
          {left.length > 0 && <UnscheduledList key={schedule.id} items={left} scheduleId={schedule.id} />}
        </>
      ) : (
        <p>{schedule.message ?? 'Unknown reason.'}</p>
      )}
    </div>
  )
}
