import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { api } from '../api'
import { Alert, Icon } from '../components/bits'
import { ClassBars, ConfusionMatrix, Histogram, ImportanceBars, PerClassTable, Scatter } from '../components/Charts'
import HostPanel from '../components/HostPanel'
import Ruler from '../components/Ruler'
import { bytes, num, pct, seconds, slug, when } from '../format'
import { PREP_LABELS } from './wizard/helpers'

export default function Results({ exp }) {
  const r = exp.results
  const isClass = r.problem_type === 'classification'
  const navigate = useNavigate()
  const [error, setError] = useState('')

  async function remove() {
    if (!window.confirm(`Delete experiment #${exp.id} and its files? This can't be undone.`)) return
    try { await api.deleteExperiment(exp.id); navigate('/experiments') } catch (e) { setError(e.message) }
  }

  return (
    <div className="page wide results">
      <header className="page-head">
        <div>
          <p className="crumb"><Link to="/experiments">My experiments</Link></p>
          <h1>Experiment #{exp.id}: {r.algorithm.label}</h1>
          <p className="lede">
            Predicting <b>{r.target}</b> in {r.dataset.filename}. Finished {when(exp.finished_at)} in {seconds(exp.duration_s)}
            {r.host.instance_type ? ` on ${r.host.provider} ${r.host.instance_type}` : ` on ${r.host.provider.toLowerCase()}`}.
          </p>
        </div>
        <div className="btn-row">
          <a className="btn btn-primary" href={`/api/experiments/${exp.id}/download/all`}>{Icon.download} Download everything</a>
        </div>
      </header>
      <Alert>{error}</Alert>

      {isClass ? <ClassificationHero r={r} /> : <RegressionHero r={r} />}

      <div className="blocks">
        {isClass ? (
          <>
            <Block title="Confusion matrix" help={`Each row is what a ${r.target} really was; each column is what the model said. Blue cells are correct predictions; amber cells are mistakes.`}>
              <ConfusionMatrix labels={r.charts.confusion.labels} matrix={r.charts.confusion.matrix} />
            </Block>
            <Block title="Feature importance" help="How much the score drops when one feature's values are shuffled. A bigger drop means the model leans on that feature more.">
              <ImportanceBars items={r.charts.importance} />
            </Block>
            <Block title="Class distribution" help="How many held-out rows belong to each class, next to how many the model assigned to it. Similar bars mean the model isn't favouring a class.">
              <ClassBars {...r.charts.class_distribution} />
            </Block>
            <Block title="Results by class" help={`Weighted metrics above average these rows by how common each class is.`}>
              <PerClassTable rows={r.extra.per_class} />
            </Block>
          </>
        ) : (
          <>
            <Block title="Actual vs predicted" help="Each dot is a held-out row. Dots on the dashed line were predicted exactly; the further away, the bigger the miss.">
              <Scatter points={r.charts.scatter} xLabel={r.target} yLabel={r.target} />
            </Block>
            <Block title="Residual distribution" help="How far off the predictions were. A tall bar over zero with a balanced shape means the model isn't consistently too high or too low.">
              <Histogram edges={r.charts.residuals.edges} counts={r.charts.residuals.counts} xLabel={r.target} />
            </Block>
            <Block title="Feature importance" help="How much R² drops when one feature's values are shuffled. A bigger drop means the model leans on that feature more.">
              <ImportanceBars items={r.charts.importance} />
            </Block>
          </>
        )}

        <Block title="Sample predictions" help="The first rows of the held-out set, with the model's answer beside the truth.">
          <div className="table-scroll">
            <table className="data">
              <thead><tr><th>Row</th><th>Actual</th><th>Predicted</th><th /></tr></thead>
              <tbody>
                {r.sample_predictions.map((s) => {
                  const ok = isClass ? s.actual === s.predicted : null
                  return (
                    <tr key={s.row_index}>
                      <td className="muted">{s.row_index}</td>
                      <td>{isClass ? s.actual : num(s.actual)}</td>
                      <td>{isClass ? s.predicted : num(s.predicted)}</td>
                      <td>{ok === null ? <span className="muted">off by {num(Math.abs(s.actual - s.predicted))}</span>
                        : <span className={`chip chip-${ok ? 'good' : 'bad'}`}>{ok ? 'Correct' : 'Missed'}</span>}</td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        </Block>

        <Block title="How this run was set up" help="Everything here is saved in experiment_config.json, so the run can be repeated.">
          <RunRecord r={r} />
        </Block>

        <Block title="Files" help="Everything produced by this experiment is stored on the server and can be downloaded.">
          <ul className="files">
            {exp.artifacts.map((a) => (
              <li key={a.name}>
                <span className="file-name">{a.name}</span>
                <span className="muted">{a.description}</span>
                <span className="muted file-size">{bytes(a.size)}</span>
                <a className="btn btn-sm" href={`/api/experiments/${exp.id}/download/${a.name}`}>{Icon.download} Download</a>
              </li>
            ))}
          </ul>
          <details className="snippet">
            <summary>Use the trained model in Python</summary>
            <pre>{`import joblib
import pandas as pd

bundle = joblib.load("model.joblib")
rows = pd.DataFrame([{ ${r.features.selected.slice(0, 3).map((f) => `"${f}": ...`).join(', ')}${r.features.selected.length > 3 ? ', ...' : ''} }])
prediction = bundle["pipeline"].predict(rows)${isClass ? '\nlabel = bundle["classes"][prediction[0]]' : ''}`}</pre>
          </details>
        </Block>

        <Block title="Where it ran" help="The virtual machine that did the work.">
          <HostPanel host={r.host} title="Compute" />
        </Block>
      </div>

      <div className="danger-zone">
        <button className="btn btn-sm btn-danger" onClick={remove}>Delete this experiment</button>
      </div>
    </div>
  )
}

function Block({ title, help, children }) {
  return (
    <section className="block">
      <div className="block-text"><h2 className="h3">{title}</h2><p className="muted">{help}</p></div>
      <div className="block-body">{children}</div>
    </section>
  )
}

function ClassificationHero({ r }) {
  const m = r.metrics
  const gain = (m.accuracy - r.baseline.value) * 100
  const gap = (r.extra.train_accuracy - m.accuracy) * 100
  return (
    <section className="hero-result" aria-label="Headline result">
      <div className="hero-main">
        <p className="hero-label">Accuracy on {r.dataset.rows_test.toLocaleString('en')} held-out rows</p>
        <p className="hero-number">{pct(m.accuracy)}</p>
        <Ruler value={m.accuracy} baseline={r.baseline.value} size="lg" baselineLabel={r.baseline.description} />
        <p className="hero-read">
          {gain > 0.05
            ? <>That is {gain.toFixed(1)} points better than the open mark: <b>{pct(r.baseline.value)}</b>, what {r.baseline.description.toLowerCase()} would score.</>
            : <>That is no better than the open mark: <b>{pct(r.baseline.value)}</b>, what {r.baseline.description.toLowerCase()} would score. Try different features or another algorithm.</>}
          {gap > 10 && <> The model scored {pct(r.extra.train_accuracy, 0)} on its training rows, so it may be memorising rather than learning.</>}
        </p>
      </div>
      <dl className="hero-side">
        {[['precision', 'Precision'], ['recall', 'Recall'], ['f1', 'F1 score']].map(([k, label]) => (
          <div key={k}>
            <dt>{label}</dt>
            <dd>{pct(m[k])}</dd>
            <Ruler value={m[k]} size="sm" ticks={false} label={`${label} ${pct(m[k])}`} />
          </div>
        ))}
        <p className="muted small">Weighted across {r.classes.length} classes.</p>
      </dl>
    </section>
  )
}

function RegressionHero({ r }) {
  const m = r.metrics
  const t = r.extra.target_stats
  const share = Math.max(m.r2, 0)
  const better = (1 - m.rmse / r.baseline.value) * 100
  const gap = r.extra.train_r2 - m.r2
  return (
    <section className="hero-result" aria-label="Headline result">
      <div className="hero-main">
        <p className="hero-label">R² on {r.dataset.rows_test.toLocaleString('en')} held-out rows</p>
        <p className="hero-number">{m.r2.toFixed(3)}</p>
        <Ruler value={share} baseline={0} size="lg" numbers={['0', '0.2', '0.4', '0.6', '0.8', '1']} label={`R² ${m.r2.toFixed(3)} on a scale from 0 to 1`} />
        <p className="hero-read">
          {m.r2 >= 0
            ? <>The model explains {pct(share, 0)} of the variation in {r.target}. Its typical error (RMSE) is {num(m.rmse)}, {better > 0 ? `${better.toFixed(0)}% smaller than` : 'no better than'} just predicting the average ({num(r.baseline.value)}).</>
            : <>An R² below zero means the model did worse than predicting the average {r.target}. Try different features or another algorithm.</>}
          {gap > 0.15 && <> It scored {r.extra.train_r2.toFixed(2)} on the training rows, so it may be memorising rather than learning.</>}
        </p>
      </div>
      <dl className="hero-side">
        <div><dt>MAE</dt><dd>{num(m.mae)}</dd><p className="muted small">Average miss, in {r.target} units.</p></div>
        <div><dt>RMSE</dt><dd>{num(m.rmse)}</dd><p className="muted small">Like MAE but punishes big misses. {r.target} ranges {num(t.min)} to {num(t.max)}.</p></div>
        <div><dt>MSE</dt><dd>{num(m.mse)}</dd><p className="muted small">The squared error RMSE is built from.</p></div>
      </dl>
    </section>
  )
}

function RunRecord({ r }) {
  const prep = r.preprocessing
  const d = r.dataset
  const total = Object.values(r.stage_seconds).reduce((a, b) => a + b, 0) || 1
  return (
    <div className="record">
      <dl className="facts facts-wide">
        <div><dt>Algorithm</dt><dd>{r.algorithm.label}<span className="muted">{Object.entries(r.algorithm.params).map(([k, v]) => `${slug(k)} ${slug(String(v))}`).join(', ')}</span></dd></div>
        <div><dt>Data used</dt><dd>{d.rows_used.toLocaleString('en')} rows: {d.rows_train.toLocaleString('en')} to train, {d.rows_test.toLocaleString('en')} to test{d.rows_missing_target ? `. ${d.rows_missing_target} rows without a target were skipped` : ''}</dd></div>
        <div><dt>Features</dt><dd>{r.features.selected.length} selected, {r.features.after_encoding} after encoding<span className="muted">{r.features.selected.join(', ')}</span></dd></div>
        <div><dt>Preparation</dt><dd>{PREP_LABELS.encoding[prep.encoding]}, {PREP_LABELS.scaling[prep.scaling]}, missing numbers filled with the {PREP_LABELS.missing[prep.missing]}<span className="muted">Split {Math.round((1 - prep.test_size) * 100)} / {Math.round(prep.test_size * 100)}, random state {prep.random_state}</span></dd></div>
      </dl>
      <h3 className="h4">Time spent per stage</h3>
      <ul className="timing">
        {Object.entries(r.stage_seconds).map(([name, s]) => (
          <li key={name}>
            <span>{name}</span>
            <span className="bar-track"><span className="bar-fill" style={{ width: `${Math.max(s / total * 100, 1.5)}%` }} /></span>
            <span className="muted">{s < 0.1 ? '<0.1 s' : seconds(s)}</span>
          </li>
        ))}
      </ul>
    </div>
  )
}
