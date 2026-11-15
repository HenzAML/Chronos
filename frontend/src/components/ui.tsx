import type { ReactNode } from 'react'
import { ApiError } from '../api/client'
import { REASON_LABELS } from '../types'
import type { Unscheduled } from '../types'

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

/** Classes the solver left out, each with its reason. */
export function UnscheduledList({ items }: { items: Unscheduled[] }) {
  return (
    <ul className="unscheduled">
      {items.map((u) => (
        <li key={`${u.course_id}-${u.class_index}`}>
          <div className="unscheduled-head">
            <strong>{u.course_code}</strong>
            <span className="muted">{u.course_name}</span>
            <Badge kind="warn">{REASON_LABELS[u.code] ?? u.code}</Badge>
          </div>
          <p>{u.message}</p>
        </li>
      ))}
    </ul>
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
