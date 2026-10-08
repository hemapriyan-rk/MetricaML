import { useApp } from '../../app-context'

export default function AlgorithmStep({ problem, algo, params, onAlgo, onParams }) {
  const { config } = useApp()
  const list = config.algorithms[problem]
  const spec = list.find((a) => a.key === algo)

  return (
    <div>
      <h2>Choose an algorithm</h2>
      <p className="muted">{problem === 'classification' ? 'Classification' : 'Regression'} algorithms available on this server.</p>

      <fieldset className="choices">
        <legend className="sr">Algorithm</legend>
        {list.map((a) => (
          <label key={a.key} className={`choice ${algo === a.key ? 'on' : ''}`}>
            <input type="radio" name="algorithm" checked={algo === a.key} onChange={() => onAlgo(a.key)} />
            <span className="choice-body"><strong>{a.label}</strong><span className="muted">{a.description}</span></span>
          </label>
        ))}
      </fieldset>

      {spec && (
        <div className="params">
          <h3 className="h4">{spec.label} settings</h3>
          <div className="form-grid">
            {spec.params.map((p) => (
              <label className="field" key={p.name}>
                <span>{p.label}</span>
                {p.type === 'choice' ? (
                  <select value={params[p.name]} onChange={(e) => onParams({ ...params, [p.name]: e.target.value })}>
                    {p.choices.map((c) => <option key={c} value={c}>{c.replace(/_/g, ' ')}</option>)}
                  </select>
                ) : (
                  <input type="number" min={p.min} max={p.max} step={p.type === 'int' ? 1 : p.step}
                         value={params[p.name]} onChange={(e) => onParams({ ...params, [p.name]: e.target.value === '' ? '' : Number(e.target.value) })} />
                )}
                <small>{p.type !== 'choice' ? `${p.hint ? p.hint + '. ' : ''}Between ${p.min} and ${p.max}.` : p.hint}</small>
              </label>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
