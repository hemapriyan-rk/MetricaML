export function defaultParams(spec) {
  return Object.fromEntries(spec.params.map((p) => [p.name, p.default]))
}

export function guessProblem(col) {
  if (!col) return 'classification'
  if (['categorical', 'boolean', 'text'].includes(col.kind)) return 'classification'
  if (col.kind === 'integer' && col.unique <= 10) return 'classification'
  return 'regression'
}

export const RECOMMENDATION = {
  feature: { text: 'Feature', tone: 'plain' },
  target_candidate: { text: 'Target candidate', tone: 'cobalt' },
  id: { text: 'Identifier, leave out', tone: 'amber' },
  constant: { text: 'Same value everywhere, leave out', tone: 'amber' },
  sparse: { text: 'Mostly empty, leave out', tone: 'amber' },
  datetime: { text: 'Date, leave out', tone: 'amber' },
  text: { text: 'Free text, leave out', tone: 'amber' },
}

export const PREP_LABELS = {
  missing: { median: 'median', mean: 'mean', most_frequent: 'most frequent value' },
  encoding: { onehot: 'one-hot encoding', ordinal: 'ordinal encoding' },
  scaling: { standard: 'standard scaling', minmax: 'min–max scaling', none: 'no scaling' },
}
