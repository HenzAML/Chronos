import { useState } from 'react'
import { api } from '../api/client'
import { useAsync } from '../components/useAsync'
import { ConfirmButton, Empty, ErrorBox, Field, Modal, Spinner } from '../components/ui'
import { CAPABILITIES } from '../types'
import type { CapabilityKey, Equipment, Room, RoomInput } from '../types'

interface Data { rooms: Room[]; equipment: Equipment[] }

const blank = (): RoomInput & { equipment_ids: number[] } => ({
  code: '', name: '', capacity: 30,
  supports_lecture: true, supports_lab: false, supports_group: false,
  supports_seminar: false, supports_meeting: false,
  equipment_ids: [],
})

export default function Rooms() {
  const { data, error, loading, reload } = useAsync<Data>(async () => ({
    rooms: await api.rooms.list(), equipment: await api.equipment.list(),
  }), [])
  const [editing, setEditing] = useState<(RoomInput & { equipment_ids: number[] }) | null>(null)
  const [formError, setFormError] = useState<unknown>(null)
  const [busy, setBusy] = useState(false)

  if (loading) return <Spinner />
  if (error) return <ErrorBox error={error} onRetry={reload} />
  if (!data) return null

  function openNew() { setFormError(null); setEditing(blank()) }
  function openEdit(r: Room) {
    setFormError(null)
    setEditing({ ...r, equipment_ids: r.equipment.map((e) => e.id) })
  }

  async function save() {
    if (!editing) return
    setBusy(true); setFormError(null)
    const payload = {
      code: editing.code, name: editing.name, capacity: editing.capacity,
      supports_lecture: editing.supports_lecture, supports_lab: editing.supports_lab,
      supports_group: editing.supports_group, supports_seminar: editing.supports_seminar,
      supports_meeting: editing.supports_meeting,
      equipment_ids: editing.equipment_ids,
    }
    try {
      if (editing.id) await api.rooms.update(editing.id, payload)
      else await api.rooms.create(payload)
      setEditing(null); reload()
    } catch (e) { setFormError(e) } finally { setBusy(false) }
  }

  async function remove(id: number) {
    try { await api.rooms.remove(id); reload() } catch (e) { setFormError(e) }
  }

  return (
    <>
      <header className="page-head">
        <div><h1>Rooms</h1><p className="muted">Capacity, suitability and equipment.</p></div>
        <button className="btn btn-primary" onClick={openNew}>New room</button>
      </header>

      {formError != null && !editing && <ErrorBox error={formError} />}

      {data.rooms.length === 0 ? <Empty>No rooms yet.</Empty> : (
        <table className="table">
          <thead>
            <tr><th>Code</th><th>Name</th><th>Capacity</th><th>Suitable for</th>
                <th>Equipment</th><th /></tr>
          </thead>
          <tbody>
            {data.rooms.map((r) => (
              <tr key={r.id}>
                <td><strong>{r.code}</strong></td>
                <td>{r.name ?? <span className="muted">—</span>}</td>
                <td>{r.capacity}</td>
                <td>
                  <div className="chips">
                    {CAPABILITIES.filter((c) => r[c.key]).map((c) => (
                      <span key={c.key} className="chip">{c.label}</span>
                    ))}
                    {!CAPABILITIES.some((c) => r[c.key]) && <span className="muted">none</span>}
                  </div>
                </td>
                <td>
                  <div className="chips">
                    {r.equipment.map((e) => <span key={e.id} className="chip chip-alt">{e.name}</span>)}
                    {r.equipment.length === 0 && <span className="muted">none</span>}
                  </div>
                </td>
                <td className="actions">
                  <button className="btn btn-sm" onClick={() => openEdit(r)}>Edit</button>
                  <ConfirmButton onConfirm={() => remove(r.id)} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      {editing && (
        <Modal title={editing.id ? `Edit ${editing.code}` : 'New room'}
          onClose={() => setEditing(null)} wide>
          {formError != null && <ErrorBox error={formError} />}
          <div className="form-grid">
            <Field label="Code"><input className="input" value={editing.code ?? ''}
              onChange={(e) => setEditing({ ...editing, code: e.target.value })} /></Field>
            <Field label="Name"><input className="input" value={editing.name ?? ''}
              onChange={(e) => setEditing({ ...editing, name: e.target.value })} /></Field>
            <Field label="Capacity"><input className="input" type="number" min={1}
              value={editing.capacity ?? 0}
              onChange={(e) => setEditing({ ...editing, capacity: Number(e.target.value) })} /></Field>
          </div>

          <Field group label="Suitable for"
            hint="A room may support several session types. Mismatch costs soft penalty S4.">
            <div className="checks">
              {CAPABILITIES.map((c) => (
                <label key={c.key} className="check">
                  <input type="checkbox" checked={Boolean(editing[c.key as CapabilityKey])}
                    onChange={(e) => setEditing({ ...editing, [c.key]: e.target.checked })} />
                  {c.label}
                </label>
              ))}
            </div>
          </Field>

          <Field group label="Equipment"
            hint="Courses needing kit this room lacks pay S3 — or are barred outright if essential (H6).">
            <div className="checks">
              {data.equipment.map((eq) => (
                <label key={eq.id} className="check">
                  <input type="checkbox"
                    checked={editing.equipment_ids.includes(eq.id)}
                    onChange={(e) => setEditing({
                      ...editing,
                      equipment_ids: e.target.checked
                        ? [...editing.equipment_ids, eq.id]
                        : editing.equipment_ids.filter((i) => i !== eq.id),
                    })} />
                  {eq.name}
                </label>
              ))}
            </div>
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
