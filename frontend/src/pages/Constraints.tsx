import { useState } from 'react'
import { api } from '../api/client'
import { useAsync } from '../components/useAsync'
import { ErrorBox, Spinner } from '../components/ui'
import type { ConstraintConfig, Schedule } from '../types'

const HARD = [
  { key: 'enable_h2_room_conflict', code: 'H2', label: 'No room double-booking' },
  { key: 'enable_h3_instructor_conflict', code: 'H3', label: 'No instructor double-booking' },
  { key: 'enable_h4_capacity', code: 'H4', label: 'Room capacity ≥ enrolment' },
  { key: 'enable_h5_availability', code: 'H5', label: 'Instructor availability respected' },
  { key: 'enable_h6_essential_equipment', code: 'H6', label: 'Room has essential equipment' },
] as const

const SOFT = [
  { key: 'w1_morning', code: 'S1', label: 'Morning preference',
    hint: 'Penalty when a class lands after 12:00 for an instructor who prefers mornings.' },
  { key: 'w2_preferred_day', code: 'S2', label: 'Preferred day',
    hint: 'Penalty when a class falls on a day the instructor did not ask for.' },
  { key: 'w3_equipment', code: 'S3', label: 'Preferred equipment',
    hint: 'Charged per missing nice-to-have item. Essential kit is hard (H6), not this.' },
  { key: 'w4_room_type', code: 'S4', label: 'Room suitability',
    hint: 'Penalty when the room does not support the course’s session type.' },
] as const

export default function Constraints() {
  const { data, error, loading, reload } = useAsync<ConstraintConfig>(
    () => api.constraints.get(), [])
  // `draft` holds only unsaved edits; the saved config comes from `data`.
  // Deriving the working copy avoids mirroring server state into an effect.
  const [draft, setDraft] = useState<ConstraintConfig | null>(null)
  const [saving, setSaving] = useState(false)
  const [saveError, setSaveError] = useState<unknown>(null)
  const [preview, setPreview] = useState<Schedule | null>(null)
  const [previewing, setPreviewing] = useState(false)

  if (loading) return <Spinner />
  if (error) return <ErrorBox error={error} onRetry={reload} />
  if (!data) return null

  const current = draft ?? data
  const dirty = draft !== null && JSON.stringify(draft) !== JSON.stringify(data)
  const set = (k: keyof ConstraintConfig, v: number | boolean) =>
    setDraft({ ...current, [k]: v } as ConstraintConfig)

  async function save() {
    setSaving(true); setSaveError(null)
    try { await api.constraints.update(current); setDraft(null); reload() }
    catch (e) { setSaveError(e) }
    finally { setSaving(false) }
  }

  async function runPreview() {
    setPreviewing(true); setSaveError(null)
    try {
      setPreview(await api.generate({
        name: `Preview ${new Date().toLocaleTimeString()}`,
        ...current,
      }))
    } catch (e) { setSaveError(e) }
    finally { setPreviewing(false) }
  }

  return (
    <>
      <header className="page-head">
        <div>
          <h1>Constraints</h1>
          <p className="muted">
            Hard constraints must hold. Soft weights trade off against each other —
            raising one usually costs another.
          </p>
        </div>
        <div className="row-gap">
          <button className="btn" onClick={runPreview} disabled={previewing}>
            {previewing ? 'Solving…' : 'Preview effect'}
          </button>
          <button className="btn btn-primary" onClick={save} disabled={!dirty || saving}>
            {saving ? 'Saving…' : dirty ? 'Save changes' : 'Saved'}
          </button>
        </div>
      </header>

      {saveError && <ErrorBox error={saveError} />}
      {preview && <PreviewResult schedule={preview} />}

      <section className="panel">
        <h2>Hard constraints</h2>
        <p className="muted small">
          H1 (a class is scheduled at most once) is structural and always enforced.
        </p>
        <div className="toggles">
          {HARD.map((h) => (
            <label key={h.key} className="toggle">
              <input type="checkbox"
                checked={current[h.key] as boolean}
                onChange={(e) => set(h.key, e.target.checked)} />
              <span className="toggle-code">{h.code}</span>
              <span>{h.label}</span>
            </label>
          ))}
        </div>
      </section>

      <section className="panel">
        <h2>Soft weights</h2>
        <div className="sliders">
          {SOFT.map((s) => (
            <div key={s.key} className="slider-row">
              <div className="slider-head">
                <span className="toggle-code">{s.code}</span>
                <strong>{s.label}</strong>
                <output>{current[s.key] as number}</output>
              </div>
              <input type="range" min={0} max={100}
                value={current[s.key] as number}
                onChange={(e) => set(s.key, Number(e.target.value))} />
              <p className="field-hint">{s.hint}</p>
            </div>
          ))}
        </div>
      </section>

      <section className="panel">
        <h2>Solver</h2>
        <label className="field field-inline">
          <span className="field-label">Time limit (seconds)</span>
          <input className="input input-sm" type="number" min={1} max={600}
            value={current.solver_time_limit_seconds}
            onChange={(e) => set('solver_time_limit_seconds', Number(e.target.value))} />
        </label>
      </section>
    </>
  )
}

function PreviewResult({ schedule }: { schedule: Schedule }) {
  const pb = schedule.diagnostics?.penalty_breakdown
  const partial = schedule.status === 'partial'
  const ok = partial || schedule.status === 'optimal' || schedule.status === 'feasible'
  if (!ok) {
    return (
      <div className="alert alert-warn">
        <strong>These settings produce no timetable</strong>
        <ul>{(schedule.message ?? '').split('\n').map((m, i) => <li key={i}>{m}</li>)}</ul>
      </div>
    )
  }
  return (
    <div className={`alert ${partial ? 'alert-warn' : 'alert-ok'}`}>
      <strong>
        Preview: Z = {schedule.soft_score}
        {partial && ` · ${schedule.assignment_count} of ${schedule.class_count} classes placed`}
      </strong>{' '}
      <span className="muted">
        ({schedule.status}, {schedule.solve_seconds?.toFixed(2)}s, saved as #{schedule.id})
      </span>
      {pb && (
        <table className="table table-tight">
          <thead><tr><th>Term</th><th>Weighted</th><th>Violations</th></tr></thead>
          <tbody>
            <tr><td>S1 mornings</td><td>{pb.S1_morning}</td><td>{pb.S1_morning_count}</td></tr>
            <tr><td>S2 preferred day</td><td>{pb.S2_preferred_day}</td><td>{pb.S2_preferred_day_count}</td></tr>
            <tr><td>S3 equipment</td><td>{pb.S3_equipment}</td><td>{pb.S3_equipment_count}</td></tr>
            <tr><td>S4 room type</td><td>{pb.S4_room_type}</td><td>{pb.S4_room_type_count}</td></tr>
          </tbody>
        </table>
      )}
      <p className="field-hint">
        “Violations” counts actual breaches; “weighted” is what the objective charges.
        A zero weight shows 0 cost but the violations remain.
      </p>
    </div>
  )
}
