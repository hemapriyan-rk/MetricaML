import { RECOMMENDATION } from './helpers'

export default function FeaturesStep({ profile, target, features, onChange }) {
  const selectable = profile.columns.filter((c) => c.name !== target)
  const chosen = new Set(features)
  const toggle = (name) => onChange(selectable.map((c) => c.name).filter((n) => (n === name ? !chosen.has(n) : chosen.has(n))))
  const recommended = selectable.filter((c) => !c.exclude_default).map((c) => c.name)

  return (
    <div>
      <div className="step-head">
        <div>
          <h2>Which columns should the model learn from?</h2>
          <p className="muted"><b className="count">{features.length}</b> of {selectable.length} columns selected. Identifiers and empty columns are left out for you.</p>
        </div>
        <div className="btn-row">
          <button className="btn btn-sm" onClick={() => onChange(recommended)}>Select recommended</button>
          <button className="btn btn-sm" onClick={() => onChange(selectable.map((c) => c.name))}>Select all</button>
          <button className="btn btn-sm" onClick={() => onChange([])}>Clear</button>
        </div>
      </div>

      <ul className="feature-list">
        <li className="feature target-row">
          <input type="checkbox" checked={false} disabled aria-label={`${target} (target)`} />
          <span className="feature-name">{target}</span>
          <span className="chip chip-cobalt">Target</span>
        </li>
        {selectable.map((c) => {
          const rec = RECOMMENDATION[c.recommendation]
          const flagged = c.exclude_default
          return (
            <li key={c.name} className={`feature ${chosen.has(c.name) ? 'on' : ''}`}>
              <label>
                <input type="checkbox" checked={chosen.has(c.name)} onChange={() => toggle(c.name)} />
                <span className="feature-name">{c.name}</span>
                <span className="feature-type muted">{c.type}{c.missing ? `, ${c.missing} missing` : ''}</span>
                {flagged && <span className={`chip chip-${rec.tone}`}>{rec.text}</span>}
              </label>
            </li>
          )
        })}
      </ul>
      {features.length === 0 && <p className="note warn">Select at least one column to continue.</p>}
    </div>
  )
}
