import { useMemo, useState } from 'react'
import { api } from '../api/client'
import { useAsync } from '../components/useAsync'
import { ConfirmButton, Empty, ErrorBox, Field, Modal, Spinner } from '../components/ui'
import { DAY_NAMES } from '../types'
import type { Instructor, TimeSlot } from '../types'

interface Data { instructors: Instructor[]; slots: TimeSlot[] }
type Draft = Partial<Instructor> & { availability_slot_ids: number[] }

export default function Instructors() {
  const { data, error, loading, reload } = useAsync<Data>(async () => ({
    instructors: await api.instructors.list(), slots: await api.timeslots.list(),
  }), [])
  const [editing, setEditing] = useState<Draft | null>(null)
  const [formError, setFormError] = useState<unknown>(null)
  const [busy, setBusy] = useState(false)

  const { days, hours } = useMemo(() => {
    const s = data?.slots ?? []
    return {
      days: [...new Set(s.map((x) => x.day))].sort((a, b) => a - b),
      hours: [...new Set(s.map((x) => x.hour))].sort((a, b) => a - b),
    }
  }, [data])

  if (loading) return <Spinner />
  if (error) return <ErrorBox error={error} onRetry={reload} />
  if (!data) return null

  const slotAt = (d: number, h: number) =>
    data.slots.find((s) => s.day === d && s.hour === h)

  function openEdit(i: Instructor) {
    setFormError(null)
    setEditing({ ...i, availability_slot_ids: i.availability_slot_ids ?? [] })
  }

  async function save() {
    if (!editing) return
    setBusy(true); setFormError(null)
    const payload = {
      name: editing.name, email: editing.email,
      prefer_morning: editing.prefer_morning,
      preferred_days: editing.preferred_days ?? [],
    }
    try {
      const saved = editing.id
        ? await api.instructors.update(editing.id, payload)
        : await api.instructors.create(payload)
      await api.instructors.setAvailability(saved.id, editing.availability_slot_ids)
      setEditing(null); reload()
    } catch (e) { setFormError(e) } finally { setBusy(false) }
  }

  async function remove(id: number) {
    try { await api.instructors.remove(id); reload() } catch (e) { setFormError(e) }
  }

  function toggleSlot(id: number) {
    if (!editing) return
    const has = editing.availability_slot_ids.includes(id)
    setEditing({
      ...editing,
      availability_slot_ids: has
        ? editing.availability_slot_ids.filter((x) => x !== id)
        : [...editing.availability_slot_ids, id],
    })
  }

  function toggleDay(d: number) {
    if (!editing) return
    const ids = data!.slots.filter((s) => s.day === d).map((s) => s.id)
    const allOn = ids.every((i) => editing.availability_slot_ids.includes(i))
    setEditing({
      ...editing,
      availability_slot_ids: allOn
        ? editing.availability_slot_ids.filter((i) => !ids.includes(i))
        : [...new Set([...editing.availability_slot_ids, ...ids])],
    })
  }

  return (
    <>
      <header className="page-head">
        <div><h1>Instructors</h1><p className="muted">Availability is hard (H5); preferences are soft (S1, S2).</p></div>
        <button className="btn btn-primary" onClick={() => {
          setFormError(null)
          setEditing({ name: '', email: '', prefer_morning: false, preferred_days: [], availability_slot_ids: [] })
        }}>New instructor</button>
      </header>

      {formError != null && !editing && <ErrorBox error={formError} />}

      {data.instructors.length === 0 ? <Empty>No instructors yet.</Empty> : (
        <table className="table">
          <thead>
            <tr><th>Name</th><th>Email</th><th>Prefers mornings</th>
                <th>Preferred days</th><th>Available slots</th><th>Courses</th><th /></tr>
          </thead>
          <tbody>
            {data.instructors.map((i) => (
              <tr key={i.id}>
                <td><strong>{i.name}</strong></td>
                <td className="muted">{i.email ?? '—'}</td>
                <td>{i.prefer_morning ? 'Yes' : 'No'}</td>
                <td>
                  <div className="chips">
                    {i.preferred_days.length
                      ? i.preferred_days.map((d) => <span key={d} className="chip">{DAY_NAMES[d]}</span>)
                      : <span className="muted">any</span>}
                  </div>
                </td>
                <td>{i.availability_slot_ids?.length ?? 0}</td>
                <td>{i.course_count ?? 0}</td>
                <td className="actions">
                  <button className="btn btn-sm" onClick={() => openEdit(i)}>Edit</button>
                  <ConfirmButton onConfirm={() => remove(i.id)} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      {editing && (
        <Modal title={editing.id ? `Edit ${editing.name}` : 'New instructor'}
          onClose={() => setEditing(null)} wide>
          {formError != null && <ErrorBox error={formError} />}
          <div className="form-grid">
            <Field label="Name"><input className="input" value={editing.name ?? ''}
              onChange={(e) => setEditing({ ...editing, name: e.target.value })} /></Field>
            <Field label="Email"><input className="input" value={editing.email ?? ''}
              onChange={(e) => setEditing({ ...editing, email: e.target.value })} /></Field>
          </div>

          <Field group label="Preferences" hint="Soft only — the solver trades these off (S1, S2).">
            <label className="check">
              <input type="checkbox" checked={Boolean(editing.prefer_morning)}
                onChange={(e) => setEditing({ ...editing, prefer_morning: e.target.checked })} />
              Prefers mornings (before 12:00)
            </label>
            <div className="checks">
              {DAY_NAMES.slice(0, 5).map((d, idx) => (
                <label key={d} className="check">
                  <input type="checkbox"
                    checked={(editing.preferred_days ?? []).includes(idx)}
                    onChange={(e) => setEditing({
                      ...editing,
                      preferred_days: e.target.checked
                        ? [...(editing.preferred_days ?? []), idx]
                        : (editing.preferred_days ?? []).filter((x) => x !== idx),
                    })} />
                  {d}
                </label>
              ))}
            </div>
          </Field>

          <Field group label={`Availability — ${editing.availability_slot_ids.length} slot(s) selected`}
            hint="Hard constraint H5: the instructor can only be scheduled in ticked slots.">
            {data.slots.length === 0 ? <p className="muted">No time slots defined yet.</p> : (
              <div className="grid-scroll">
                <table className="availability">
                  <thead>
                    <tr>
                      <th />
                      {days.map((d) => (
                        <th key={d}>
                          <button className="link-btn" onClick={() => toggleDay(d)}>{DAY_NAMES[d]}</button>
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {hours.map((h) => (
                      <tr key={h}>
                        <th>{String(h).padStart(2, '0')}:00</th>
                        {days.map((d) => {
                          const slot = slotAt(d, h)
                          if (!slot) return <td key={d} className="off" />
                          const on = editing.availability_slot_ids.includes(slot.id)
                          return (
                            <td key={d}>
                              <button type="button"
                                className={`slot${on ? ' slot-on' : ''}`}
                                onClick={() => toggleSlot(slot.id)}
                                aria-label={`${DAY_NAMES[d]} ${h}:00`} />
                            </td>
                          )
                        })}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
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
