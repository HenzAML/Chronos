import { useEffect, useState } from 'react'
import { api } from '../api/client'
import { useAsync } from '../components/useAsync'
import { Empty, ErrorBox, Spinner, StatusBadge } from '../components/ui'
import { DAY_NAMES } from '../types'
import type { Assignment, Grid, Schedule } from '../types'

const TYPE_CLASS: Record<string, string> = {
  lecture: 'ev-lecture', lab: 'ev-lab', group: 'ev-group',
  seminar: 'ev-seminar', meeting: 'ev-meeting',
}

export default function Timetable() {
  const schedules = useAsync<Schedule[]>(() => api.schedules.list(), [])
  const [selected, setSelected] = useState<number | null>(null)
  const [grid, setGrid] = useState<Grid | null>(null)
  const [gridError, setGridError] = useState<unknown>(null)
  const [loadingGrid, setLoadingGrid] = useState(false)
  const [focus, setFocus] = useState<Assignment | null>(null)

  const list = schedules.data ?? []
  // Default to the newest schedule that actually produced assignments. Derived
  // during render rather than pushed into state by an effect.
  const shownId = selected
    ?? (list.find((s) => s.assignment_count > 0) ?? list[0])?.id
    ?? null

  useEffect(() => {
    if (shownId === null) return
    let cancelled = false
    setLoadingGrid(true)
    api.schedules.grid(shownId)
      .then((g) => { if (!cancelled) { setGrid(g); setGridError(null) } })
      .catch((e) => { if (!cancelled) setGridError(e) })
      .finally(() => { if (!cancelled) setLoadingGrid(false) })
    return () => { cancelled = true }
  }, [shownId])

  if (schedules.loading) return <Spinner />
  if (schedules.error) return <ErrorBox error={schedules.error} onRetry={schedules.reload} />

  if (list.length === 0) {
    return (
      <>
        <PageHead />
        <Empty>
          No schedules yet. Go to <strong>Dashboard</strong> and press
          <strong> Generate schedule</strong>.
        </Empty>
      </>
    )
  }

  const current = list.find((s) => s.id === shownId) ?? null

  return (
    <>
      <PageHead>
        <select className="select" value={shownId ?? ''}
          onChange={(e) => setSelected(Number(e.target.value))}>
          {list.map((s) => (
            <option key={s.id} value={s.id}>
              #{s.id} {s.name ?? 'untitled'} — {s.status}
              {s.soft_score !== null ? ` (Z=${s.soft_score})` : ''}
            </option>
          ))}
        </select>
      </PageHead>

      {current && <ScheduleSummary schedule={current} />}

      {loadingGrid && <Spinner label="Loading timetable…" />}
      {gridError && <ErrorBox error={gridError} />}

      {!loadingGrid && grid && (
        grid.hours.length === 0
          ? <Empty>This schedule has no assignments{current?.status === 'infeasible'
              ? ' because the instance was infeasible — see the message above.' : '.'}</Empty>
          : <GridView grid={grid} onPick={setFocus} />
      )}

      {focus && <DetailPanel assignment={focus} onClose={() => setFocus(null)} />}
    </>
  )
}

function PageHead({ children }: { children?: React.ReactNode }) {
  return (
    <header className="page-head">
      <div>
        <h1>Timetable</h1>
        <p className="muted">Weekly grid of a generated schedule.</p>
      </div>
      {children}
    </header>
  )
}

function ScheduleSummary({ schedule }: { schedule: Schedule }) {
  const gap = schedule.optimality_gap
  return (
    <div className="summary">
      <div className="summary-stats">
        <Stat label="Status"><StatusBadge status={schedule.status} /></Stat>
        <Stat label="Soft score Z">{schedule.soft_score ?? '—'}</Stat>
        <Stat label="Optimality gap">
          {gap === null ? '—' : gap === 0 ? <span className="good">0% · proven optimal</span>
            : `${(gap * 100).toFixed(2)}%`}
        </Stat>
        <Stat label="Solve time">
          {schedule.solve_seconds !== null ? `${schedule.solve_seconds.toFixed(2)}s` : '—'}
        </Stat>
        <Stat label="Assignments">{schedule.assignment_count}</Stat>
        <Stat label="Weights">
          <code className="tiny">
            {schedule.weights.w1_morning}/{schedule.weights.w2_preferred_day}/
            {schedule.weights.w3_equipment}/{schedule.weights.w4_room_type}
          </code>
        </Stat>
      </div>
      {schedule.message && (
        <div className="alert alert-warn">
          <strong>Solver could not produce a timetable</strong>
          <ul>{schedule.message.split('\n').map((m, i) => <li key={i}>{m}</li>)}</ul>
        </div>
      )}
    </div>
  )
}

function Stat({ label, children }: { label: string; children: React.ReactNode }) {
  return <div className="stat"><span className="stat-label">{label}</span><span className="stat-value">{children}</span></div>
}

function GridView({ grid, onPick }: { grid: Grid; onPick: (a: Assignment) => void }) {
  const { days, hours } = grid
  return (
    <div className="grid-scroll">
      <table className="timetable">
        <thead>
          <tr>
            <th className="time-col">Time</th>
            {days.map((d) => <th key={d}>{DAY_NAMES[d]}</th>)}
          </tr>
        </thead>
        <tbody>
          {hours.map((h) => (
            <tr key={h}>
              <th className="time-col">{String(h).padStart(2, '0')}:00</th>
              {days.map((d) => {
                const cell = grid.grid[String(d)]?.[String(h)] ?? []
                return (
                  <td key={d}>
                    {cell.map((a) => (
                      <button key={a.id} className={`event ${TYPE_CLASS[a.course.session_type] ?? ''}`}
                        onClick={() => onPick(a)} title={`${a.course.name} · ${a.course.instructor ?? ''}`}>
                        <strong>{a.course.code}</strong>
                        <span>{a.room.code}</span>
                      </button>
                    ))}
                  </td>
                )
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function DetailPanel({ assignment, onClose }: { assignment: Assignment; onClose: () => void }) {
  const { course, room, time_slot } = assignment
  const tight = room.capacity - course.expected_students
  return (
    <aside className="detail">
      <header>
        <strong>{course.code}</strong>
        <button className="icon-btn" onClick={onClose} aria-label="Close">×</button>
      </header>
      <p className="detail-title">{course.name}</p>
      <dl>
        <dt>When</dt><dd>{time_slot.label}</dd>
        <dt>Room</dt><dd>{room.code}</dd>
        <dt>Instructor</dt><dd>{course.instructor ?? '—'}</dd>
        <dt>Type</dt><dd>{course.session_type}</dd>
        <dt>Seats</dt>
        <dd>
          {course.expected_students} / {room.capacity}
          {tight >= 0 ? <span className="muted"> ({tight} spare)</span>
                      : <span className="bad"> (over capacity!)</span>}
        </dd>
      </dl>
    </aside>
  )
}
