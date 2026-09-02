import type { ReactNode } from 'react'
import { ApiError } from '../api/client'

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
  return <div className="state state-empty">{children}</div>
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
  { label, hint, children }: { label: string; hint?: string; children: ReactNode },
) {
  return (
    <label className="field">
      <span className="field-label">{label}</span>
      {children}
      {hint && <span className="field-hint">{hint}</span>}
    </label>
  )
}

export function Badge({ kind, children }: { kind?: string; children: ReactNode }) {
  return <span className={`badge${kind ? ` badge-${kind}` : ''}`}>{children}</span>
}

export function StatusBadge({ status }: { status: string }) {
  const kind = status === 'optimal' ? 'good'
    : status === 'feasible' ? 'ok'
    : status === 'infeasible' ? 'bad'
    : status === 'failed' ? 'bad' : 'muted'
  return <Badge kind={kind}>{status}</Badge>
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
