export const pct = (v, digits = 1) => (v == null ? '–' : `${(v * 100).toFixed(digits)}%`)

export function num(v, digits = 3) {
  if (v == null) return '–'
  const abs = Math.abs(v)
  if (abs >= 1e6) return new Intl.NumberFormat('en', { notation: 'compact', maximumFractionDigits: 2 }).format(v)
  if (abs >= 1000) return v.toLocaleString('en', { maximumFractionDigits: 0 })
  if (abs >= 100) return v.toLocaleString('en', { maximumFractionDigits: 1 })
  return Number(v.toPrecision(digits)).toLocaleString('en', { maximumFractionDigits: 6 })
}

export const compact = (v) =>
  new Intl.NumberFormat('en', { notation: 'compact', maximumFractionDigits: 1 }).format(v)

export function bytes(n) {
  if (n < 1024) return `${n} B`
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`
  return `${(n / 1024 / 1024).toFixed(1)} MB`
}

export function seconds(s) {
  if (s == null) return '–'
  if (s < 10) return `${s.toFixed(1)} s`
  if (s < 90) return `${Math.round(s)} s`
  return `${Math.floor(s / 60)} min ${Math.round(s % 60)} s`
}

export function when(iso) {
  if (!iso) return ''
  const d = new Date(iso)
  const diff = (Date.now() - d.getTime()) / 1000
  if (diff < 60) return 'just now'
  if (diff < 3600) return `${Math.floor(diff / 60)} min ago`
  if (diff < 86400) return `${Math.floor(diff / 3600)} h ago`
  return d.toLocaleDateString('en', { day: 'numeric', month: 'short', year: d.getFullYear() === new Date().getFullYear() ? undefined : 'numeric' })
}

export const primaryText = (exp) => {
  if (exp.primary_value == null) return null
  return exp.primary_metric === 'r2' ? exp.primary_value.toFixed(3) : pct(exp.primary_value)
}

export const primaryLabel = (exp) => (exp.primary_metric === 'r2' ? 'R²' : 'Accuracy')

export const firstName = (name) => (name || '').trim().split(/\s+/)[0] || 'there'

export const slug = (s) => s.replace(/_/g, ' ')
