import { useState } from 'react'
import type { ReactNode } from 'react'
import { ApiError, api } from '../api/client'
import { REASON_LABELS } from '../types'
import type { Fix, Unscheduled } from '../types'

export function Spinner({ label = 'Loading…' }: { label?: string }) {
  return <div className="state"><span className="spinner" />{label}</div>
}

export function ErrorBox({ error, onRetry }: { error: unknown; onRetry?: () => void }) {
  const isApi = error instanceof ApiError
  const message = error instanceof Error ? error.message : String(error)
  const details = isApi ? error.details : []
  return (
    <div className="alert alert-error">
      <strong>{message}</strong>
      {details.length > 0 && (
        <ul>{details.map((d, i) => <li key={i}>{d}</li>)}</ul>
      )}
      {onRetry && <button className="btn btn-sm" onClick={onRetry}>Try again</button>}
    </div>
  )
}

export function Empty({ children }: { children: ReactNode }) {
  return (
    <div className="state state-empty">
      <img src="/chronos-mascot.svg" alt="" />
      <div>{children}</div>
    </div>
  )
}

export function Modal(
  { title, onClose, children, wide }:
  { title: string; onClose: () => void; children: ReactNode; wide?: boolean },
) {
  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className={`modal${wide ? ' modal-wide' : ''}`} onClick={(e) => e.stopPropagation()}>
        <header>
          <h2>{title}</h2>
          <button className="icon-btn" onClick={onClose} aria-label="Close">×</button>
        </header>
        <div className="modal-body">{children}</div>
      </div>
    </div>
  )
}

export function Field(
  { label, hint, children, group }:
  { label: string; hint?: string; children: ReactNode; group?: boolean },
) {
  // `group` holds several controls. A <label> around them would send a click
  // on the caption or hint to the first control inside.
  const Tag = group ? 'div' : 'label'
  return (
    <Tag className="field">
      <span className="field-label">{label}</span>
      {children}
      {hint && <span className="field-hint">{hint}</span>}
    </Tag>
  )
}

export function Badge({ kind, children }: { kind?: string; children: ReactNode }) {
  return <span className={`badge${kind ? ` badge-${kind}` : ''}`}>{children}</span>
}

export function StatusBadge({ status }: { status: string }) {
  const kind = status === 'optimal' ? 'good'
    : status === 'feasible' ? 'ok'
    : status === 'partial' ? 'warn'
    : status === 'infeasible' ? 'bad'
    : status === 'failed' ? 'bad' : 'muted'
  return <Badge kind={kind}>{status}</Badge>
}

/** Classes the solver left out, each with its reason. "Find fixes" asks the
 *  server to try single changes and lists the ones that work under each class. */
export function UnscheduledList({ items, scheduleId }: { items: Unscheduled[]; scheduleId: number }) {
  const [fixes, setFixes] = useState<Fix[] | null>(null)
  const [error, setError] = useState<unknown>(null)
  const [finding, setFinding] = useState(false)

  async function findFixes() {
    setFinding(true)
    setError(null)
    try {
      setFixes(await api.schedules.suggestions(scheduleId))
    } catch (e) {
      setError(e)
    } finally {
      setFinding(false)
    }
  }

  return (
    <>
      <div className="fixes-bar">
        <button className="btn btn-sm" onClick={findFixes} disabled={finding}>Find fixes</button>
        {finding && <Spinner label="Trying one change at a time…" />}
      </div>
      {error && <ErrorBox error={error} />}
      <ul className="unscheduled">
        {items.map((u) => (
          <li key={`${u.course_id}-${u.class_index}`}>
            <div className="unscheduled-head">
              <strong>{u.course_code}</strong>
              <span className="muted">{u.course_name}</span>
              <Badge kind="warn">{REASON_LABELS[u.code] ?? u.code}</Badge>
            </div>
            <p>{u.message}</p>
            {fixes && (
              <ul className="fixes">
                {fixes
                  .filter((f) => f.course_id === u.course_id && f.class_index === u.class_index)
                  .map((f) => f.kind === 'none'
                    ? <li key={f.kind} className="muted">{f.message}.</li>
                    : <li key={f.message}><b>{f.message}</b> — verified: {f.placed} classes placed.</li>)}
              </ul>
            )}
          </li>
        ))}
      </ul>
    </>
  )
}

export function ConfirmButton(
  { onConfirm, children, label = 'Delete' }:
  { onConfirm: () => void; children?: ReactNode; label?: string },
) {
  return (
    <button
      className="btn btn-sm btn-danger"
      onClick={() => {
        if (window.confirm(`${label}? This cannot be undone.`)) onConfirm()
      }}
    >
      {children ?? label}
    </button>
  )
}
