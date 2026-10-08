// Small shared building blocks.
export function Spinner({ label }) {
  return <span className="spinner" role="status" aria-label={label || 'Loading'} />
}

export function Status({ status }) {
  const text = { completed: 'Completed', running: 'Running', failed: 'Failed' }[status] || status
  return <span className={`status status-${status}`}>{text}</span>
}

export function Alert({ children, tone = 'bad' }) {
  if (!children) return null
  return <div className={`alert alert-${tone}`} role={tone === 'bad' ? 'alert' : 'status'}>{children}</div>
}

export function Brand({ light }) {
  return (
    <span className={`brand ${light ? 'brand-light' : ''}`}>
      <svg viewBox="0 0 32 32" width="26" height="26" aria-hidden="true">
        <rect width="32" height="32" rx="7" fill="currentColor" className="brand-tile" />
        <g stroke="var(--brand-tick)" strokeWidth="2" strokeLinecap="round"><path d="M7 22v-4M11 22v-7M15 22v-4M19 22v-7M23 22v-4" /></g>
        <path d="M17 6l3.5 5h-7z" fill="#E89B0C" />
      </svg>
      <span className="brand-word">MetricaML</span>
    </span>
  )
}

export const Icon = {
  grid: <svg viewBox="0 0 20 20" aria-hidden="true"><path d="M3 3h6v6H3zM11 3h6v6h-6zM3 11h6v6H3zM11 11h6v6h-6z" /></svg>,
  plus: <svg viewBox="0 0 20 20" aria-hidden="true"><path d="M10 4v12M4 10h12" /></svg>,
  list: <svg viewBox="0 0 20 20" aria-hidden="true"><path d="M7 5h10M7 10h10M7 15h10M3 5h.01M3 10h.01M3 15h.01" /></svg>,
  user: <svg viewBox="0 0 20 20" aria-hidden="true"><circle cx="10" cy="7" r="3.2" /><path d="M3.5 17c.8-3 3.2-4.5 6.5-4.5s5.700 1.500 6.500 4.500" /></svg>,
  upload: <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 16V4M7 9l5-5 5 5M4 16v3a1 1 0 001 1h14a1 1 0 001-1v-3" /></svg>,
  check: <svg viewBox="0 0 20 20" aria-hidden="true"><path d="M4 10.500l4 4 8-9" /></svg>,
  cross: <svg viewBox="0 0 20 20" aria-hidden="true"><path d="M5 5l10 10M15 5L5 15" /></svg>,
  download: <svg viewBox="0 0 20 20" aria-hidden="true"><path d="M10 3v10M6 9l4 4 4-4M4 16h12" /></svg>,
  out: <svg viewBox="0 0 20 20" aria-hidden="true"><path d="M8 4H5a1 1 0 00-1 1v10a1 1 0 001 1h3M13 6l4 4-4 4M17 10H8" /></svg>,
}
