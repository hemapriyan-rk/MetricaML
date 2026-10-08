import { pct } from '../../format'

export default function TargetStep({ profile, cols, target, problem, onTarget, onProblem }) {
  const candidates = profile.target_candidates
  const names = new Set(candidates.map((c) => c.name))
  const others = profile.columns.filter((c) => !names.has(c.name) && !['constant', 'sparse', 'datetime'].includes(c.recommendation))
  const col = cols[target]
  const numericTarget = ['integer', 'float'].includes(col?.kind)

  return (
    <div>
      <h2>What do you want to predict?</h2>
      <p className="muted">Pick the target column. MetricaML suggests the likeliest ones, but the choice is yours.</p>

      <fieldset className="choices">
        <legend className="sr">Target column</legend>
        {candidates.map((c, i) => (
          <label key={c.name} className={`choice ${target === c.name ? 'on' : ''}`}>
            <input type="radio" name="target" checked={target === c.name} onChange={() => onTarget(c.name)} />
            <span className="choice-body">
              <strong>{c.name}</strong>
              <span className="muted">{c.reason}</span>
            </span>
            {i === 0 && <span className="chip chip-cobalt">Suggested</span>}
            <span className="chip chip-plain">{c.problem_type}</span>
          </label>
        ))}
      </fieldset>

      {others.length > 0 && (
        <label className="field inline-field">
          <span>Or choose another column</span>
          <select value={names.has(target) ? '' : target} onChange={(e) => e.target.value && onTarget(e.target.value)}>
            <option value="">Select a column…</option>
            {others.map((c) => <option key={c.name} value={c.name}>{c.name} ({c.type.toLowerCase()})</option>)}
          </select>
        </label>
      )}

      {col && <TargetGlance col={col} rows={profile.rows} />}

      <h3 className="h4">Problem type</h3>
      <div className="segmented big" role="radiogroup" aria-label="Problem type">
        {[['classification', 'Classification', 'Predict a category, like Yes or No'],
          ['regression', 'Regression', 'Predict a number, like a price']].map(([key, label, hint]) => {
          const disabled = key === 'regression' && !numericTarget
          return (
            <button key={key} role="radio" aria-checked={problem === key} className={problem === key ? 'on' : ''}
                    disabled={disabled} onClick={() => onProblem(key)} title={disabled ? `${target} isn’t numeric` : undefined}>
              <strong>{label}</strong><span>{disabled ? 'Needs a numeric target' : hint}</span>
            </button>
          )
        })}
      </div>
      <p className="note">
        {problem === 'classification' && numericTarget && col.unique > 15
          ? `${target} has ${col.unique} different values. That’s a lot of classes; regression usually suits a column like this better.`
          : `MetricaML detected ${problem} from the values in ${target}. You can override it.`}
      </p>
    </div>
  )
}

function TargetGlance({ col, rows }) {
  if (col.top_values) {
    return (
      <div className="glance">
        <h3 className="h4">Values in {col.name}</h3>
        <ul className="mini-bars">
          {col.top_values.map((v) => (
            <li key={v.value}>
              <span className="bar-name" title={v.value}>{v.value}</span>
              <span className="bar-track"><span className="bar-fill" style={{ width: `${v.count / rows * 100}%` }} /></span>
              <span className="bar-val">{pct(v.count / rows, 0)}</span>
            </li>
          ))}
        </ul>
        {col.unique > col.top_values.length && <p className="muted small">Showing the {col.top_values.length} most common of {col.unique} values.</p>}
      </div>
    )
  }
  if (col.stats) {
    const f = (n) => Number(n.toPrecision(4)).toLocaleString('en')
    return (
      <dl className="facts inline">
        <div><dt>Lowest</dt><dd>{f(col.stats.min)}</dd></div>
        <div><dt>Average</dt><dd>{f(col.stats.mean)}</dd></div>
        <div><dt>Highest</dt><dd>{f(col.stats.max)}</dd></div>
        <div><dt>Distinct values</dt><dd>{col.unique.toLocaleString('en')}</dd></div>
      </dl>
    )
  }
  return null
}
