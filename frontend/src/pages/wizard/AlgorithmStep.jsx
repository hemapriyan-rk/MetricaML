import { useApp } from '../../app-context'

export const COMPARE_KEY = 'auto_compare'

export default function AlgorithmStep({ problem, algo, params, onAlgo, onParams }) {
  const { config } = useApp()
  const list = config.algorithms[problem]
  const spec = list.find((a) => a.key === algo)
  const families = [...new Set(list.map((a) => a.family))]

  return (
    <div>
      <h2>Choose an algorithm</h2>
      <p className="muted">{list.length} {problem} algorithms are available on this server. Not sure which to pick? Let MetricaML compare them all.</p>

      <fieldset className="choices">
        <legend className="sr">Algorithm</legend>
        <label className={`choice choice-compare ${algo === COMPARE_KEY ? 'on' : ''}`}>
          <input type="radio" name="algorithm" checked={algo === COMPARE_KEY} onChange={() => onAlgo(COMPARE_KEY)} />
          <span className="choice-body">
            <strong>{`Compare all ${list.length} algorithms`}</strong>
            <span className="muted">Trains each one with its default settings, ranks them on a validation slice, then trains the winner on all the data and measures it on the test rows.</span>
          </span>
          <span className="chip chip-cobalt">Automatic</span>
        </label>

        {families.map((family) => (
          <div className="family" key={family}>
            <h3 className="h4">{family}</h3>
            {list.filter((a) => a.family === family).map((a) => (
              <label key={a.key} className={`choice ${algo === a.key ? 'on' : ''}`}>
                <input type="radio" name="algorithm" checked={algo === a.key} onChange={() => onAlgo(a.key)} />
                <span className="choice-body"><strong>{a.label}</strong><span className="muted">{a.description}</span></span>
              </label>
            ))}
          </div>
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
