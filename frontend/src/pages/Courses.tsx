import { useMemo, useState } from 'react'
import { api } from '../api/client'
import { useAsync } from '../components/useAsync'
import { ConfirmButton, Empty, ErrorBox, Field, Modal, Spinner } from '../components/ui'
import { SESSION_TYPES } from '../types'
import type { Course, Equipment, Instructor, SessionType } from '../types'

interface Data { courses: Course[]; instructors: Instructor[]; equipment: Equipment[] }
type Req = { equipment_id: number; is_essential: boolean }
type Draft = Partial<Omit<Course, 'equipment_requirements'>> & { equipment_requirements: Req[] }

export default function Courses() {
  const { data, error, loading, reload } = useAsync<Data>(async () => {
    const [courses, instructors, equipment] = await Promise.all([
      api.courses.list(), api.instructors.list(), api.equipment.list(),
    ])
    return { courses, instructors, equipment }
  }, [])
  const [editing, setEditing] = useState<Draft | null>(null)
  const [formError, setFormError] = useState<unknown>(null)
  const [busy, setBusy] = useState(false)
  const [filter, setFilter] = useState<'' | SessionType>('')
  const [query, setQuery] = useState('')

  const visible = useMemo(() => {
    const list = data?.courses ?? []
    const q = query.trim().toLowerCase()
    return list.filter((c) =>
      (!filter || c.session_type === filter) &&
      (!q || c.code.toLowerCase().includes(q) || c.name.toLowerCase().includes(q)))
  }, [data, filter, query])

  if (loading) return <Spinner />
  if (error) return <ErrorBox error={error} onRetry={reload} />
  if (!data) return null

  const blank = (): Draft => ({
    code: '', name: '', expected_students: 30, duration_hours: 1,
    session_type: 'lecture',
    instructor_id: data.instructors[0]?.id,
    equipment_requirements: [],
  })

  function openEdit(c: Course) {
    setFormError(null)
    setEditing({
      ...c,
      equipment_requirements: (c.equipment_requirements ?? [])
        .map((r) => ({ equipment_id: r.equipment_id, is_essential: r.is_essential })),
    })
  }

  async function save() {
    if (!editing) return
    setBusy(true); setFormError(null)
    const payload = {
      code: editing.code, name: editing.name,
      instructor_id: editing.instructor_id,
      expected_students: editing.expected_students,
      duration_hours: editing.duration_hours,
      session_type: editing.session_type,
      equipment_requirements: editing.equipment_requirements,
    }
    try {
      if (editing.id) await api.courses.update(editing.id, payload)
      else await api.courses.create(payload)
      setEditing(null); reload()
    } catch (e) { setFormError(e) } finally { setBusy(false) }
  }

  async function remove(id: number) {
    try { await api.courses.remove(id); reload() } catch (e) { setFormError(e) }
  }

  function reqFor(d: Draft, eqId: number) {
    return d.equipment_requirements.find((r) => r.equipment_id === eqId)
  }

  function setReq(eqId: number, mode: 'none' | 'preferred' | 'essential') {
    if (!editing) return
    const rest = editing.equipment_requirements.filter((r) => r.equipment_id !== eqId)
    const next = mode === 'none' ? rest
      : [...rest, { equipment_id: eqId, is_essential: mode === 'essential' }]
    setEditing({ ...editing, equipment_requirements: next })
  }

  return (
    <>
      <header className="page-head">
        <div><h1>Courses</h1><p className="muted">{data.courses.length} in the catalogue.</p></div>
        <button className="btn btn-primary"
          onClick={() => { setFormError(null); setEditing(blank()) }}
          disabled={!data.instructors.length}>New course</button>
      </header>

      {!data.instructors.length && (
        <div className="alert alert-warn">Add an instructor before creating courses.</div>
      )}
      {formError != null && !editing && <ErrorBox error={formError} />}

      <div className="toolbar">
        <input className="input" placeholder="Search code or name…"
          value={query} onChange={(e) => setQuery(e.target.value)} />
        <select className="select" value={filter}
          onChange={(e) => setFilter(e.target.value as '' | SessionType)}>
          <option value="">All types</option>
          {SESSION_TYPES.map((t) => <option key={t} value={t}>{t}</option>)}
        </select>
        <span className="muted">{visible.length} shown</span>
      </div>

      {visible.length === 0 ? <Empty>No courses match.</Empty> : (
        <table className="table">
          <thead>
            <tr><th>Code</th><th>Name</th><th>Type</th><th>Students</th>
                <th>Instructor</th><th>Equipment</th><th /></tr>
          </thead>
          <tbody>
            {visible.map((c) => (
              <tr key={c.id}>
                <td><strong>{c.code}</strong></td>
                <td>{c.name}</td>
                <td><span className={`chip type-${c.session_type}`}>{c.session_type}</span></td>
                <td>{c.expected_students}</td>
                <td>{c.instructor?.name ?? <span className="muted">—</span>}</td>
                <td>
                  <div className="chips">
                    {(c.equipment_requirements ?? []).map((r) => (
                      <span key={r.equipment_id}
                        className={`chip ${r.is_essential ? 'chip-essential' : 'chip-alt'}`}
                        title={r.is_essential ? 'Essential — hard constraint H6' : 'Preferred — soft penalty S3'}>
                        {r.name}{r.is_essential ? ' *' : ''}
                      </span>
                    ))}
                    {!(c.equipment_requirements ?? []).length && <span className="muted">none</span>}
                  </div>
                </td>
                <td className="actions">
                  <button className="btn btn-sm" onClick={() => openEdit(c)}>Edit</button>
                  <ConfirmButton onConfirm={() => remove(c.id)} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      {editing && (
        <Modal title={editing.id ? `Edit ${editing.code}` : 'New course'}
          onClose={() => setEditing(null)} wide>
          {formError != null && <ErrorBox error={formError} />}
          <div className="form-grid">
            <Field label="Code"><input className="input" value={editing.code ?? ''}
              onChange={(e) => setEditing({ ...editing, code: e.target.value })} /></Field>
            <Field label="Name"><input className="input" value={editing.name ?? ''}
              onChange={(e) => setEditing({ ...editing, name: e.target.value })} /></Field>
            <Field label="Session type" hint="Matched against room suitability (S4).">
              <select className="select" value={editing.session_type}
                onChange={(e) => setEditing({ ...editing, session_type: e.target.value as SessionType })}>
                {SESSION_TYPES.map((t) => <option key={t} value={t}>{t}</option>)}
              </select>
            </Field>
            <Field label="Expected students"><input className="input" type="number" min={1}
              value={editing.expected_students ?? 0}
              onChange={(e) => setEditing({ ...editing, expected_students: Number(e.target.value) })} /></Field>
            <Field label="Instructor">
              <select className="select" value={editing.instructor_id ?? ''}
                onChange={(e) => setEditing({ ...editing, instructor_id: Number(e.target.value) })}>
                {data.instructors.map((i) => <option key={i.id} value={i.id}>{i.name}</option>)}
              </select>
            </Field>
          </div>

          <Field label="Equipment requirements"
            hint="Essential is enforced as a hard constraint (H6) and can make the instance infeasible. Preferred only adds soft penalty S3.">
            <table className="table table-tight">
              <thead><tr><th>Item</th><th>Not needed</th><th>Preferred</th><th>Essential</th></tr></thead>
              <tbody>
                {data.equipment.map((eq) => {
                  const r = reqFor(editing, eq.id)
                  const mode = !r ? 'none' : r.is_essential ? 'essential' : 'preferred'
                  return (
                    <tr key={eq.id}>
                      <td>{eq.name}</td>
                      {(['none', 'preferred', 'essential'] as const).map((m) => (
                        <td key={m} className="center">
                          <input type="radio" name={`eq-${eq.id}`} checked={mode === m}
                            onChange={() => setReq(eq.id, m)} />
                        </td>
                      ))}
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </Field>

          <div className="modal-actions">
            <button className="btn" onClick={() => setEditing(null)}>Cancel</button>
            <button className="btn btn-primary" onClick={save} disabled={busy}>
              {busy ? 'Saving…' : 'Save'}
            </button>
          </div>
        </Modal>
      )}
    </>
  )
}
