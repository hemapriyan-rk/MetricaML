import { useRef, useState } from 'react'
import { api } from '../../api'
import { useApp } from '../../app-context'
import { Alert, Icon, Spinner } from '../../components/bits'
import { bytes } from '../../format'
import { RECOMMENDATION } from './helpers'

export default function DatasetStep({ dataset, onDataset, onClear }) {
  const { config } = useApp()
  const [busy, setBusy] = useState('')
  const [progress, setProgress] = useState(0)
  const [error, setError] = useState('')
  const [over, setOver] = useState(false)
  const input = useRef(null)
  const limits = config.limits

  async function send(file) {
    setError('')
    const ext = '.' + file.name.split('.').pop().toLowerCase()
    if (!limits.extensions.includes(ext)) return setError('That file type isn’t supported. Use CSV, TXT, XLS or XLSX.')
    if (file.size > limits.max_file_mb * 1024 * 1024) return setError(`That file is ${bytes(file.size)}. This instance accepts files up to ${limits.max_file_mb} MB.`)
    setBusy(file.name)
    setProgress(0)
    try {
      onDataset(await api.upload(file, setProgress))
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy('')
    }
  }

  async function sample(name) {
    setError('')
    setBusy(name)
    setProgress(1)
    try {
      onDataset(await api.useSample(name))
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy('')
    }
  }

  if (dataset) return <Profile dataset={dataset} onClear={onClear} />

  return (
    <div>
      <h2>Upload your dataset</h2>
      <p className="muted">A table with one row per example and a header row. MetricaML reads it on the server and checks its structure straight away.</p>

      <div
        className={`dropzone ${over ? 'over' : ''} ${busy ? 'busy' : ''}`}
        onDragOver={(e) => { e.preventDefault(); setOver(true) }}
        onDragLeave={() => setOver(false)}
        onDrop={(e) => { e.preventDefault(); setOver(false); const f = e.dataTransfer.files?.[0]; if (f) send(f) }}
      >
        {busy ? (
          <div className="drop-busy">
            <Spinner />
            <strong>{progress >= 1 ? 'Profiling' : 'Uploading'} {busy}</strong>
            <div className="meter" aria-hidden="true"><i style={{ width: `${Math.round(progress * 100)}%` }} /></div>
            <span className="muted">{progress >= 1 ? 'Reading columns and checking quality on the EC2 instance' : `${Math.round(progress * 100)}%`}</span>
          </div>
        ) : (
          <>
            {Icon.upload}
            <strong>Drop your dataset here</strong>
            <span className="muted">CSV, TXT, XLS or XLSX, up to {limits.max_file_mb} MB and {limits.max_rows.toLocaleString('en')} rows</span>
            <button className="btn" onClick={() => input.current.click()}>Browse files</button>
            <input ref={input} type="file" hidden accept={limits.extensions.join(',')}
                   onChange={(e) => { const f = e.target.files?.[0]; if (f) send(f); e.target.value = '' }} />
          </>
        )}
      </div>
      <Alert>{error}</Alert>

      <div className="samples">
        <h3 className="h4">Or try a sample dataset</h3>
        <ul>
          {config.samples.map((s) => (
            <li key={s.name}>
              <button className="sample" onClick={() => sample(s.name)} disabled={!!busy}>
                <strong>{s.name}</strong>
                <span>{s.description}</span>
              </button>
            </li>
          ))}
        </ul>
      </div>
    </div>
  )
}

function Profile({ dataset, onClear }) {
  const p = dataset.profile
  const stats = [
    ['Rows', p.rows.toLocaleString('en')],
    ['Columns', p.columns_count],
    ['Numeric', p.numeric],
    ['Categorical', p.categorical],
    ['Missing values', p.missing_values.toLocaleString('en')],
    ['Duplicate rows', p.duplicate_rows.toLocaleString('en')],
  ]
  return (
    <div>
      <div className="step-head">
        <div>
          <h2>{dataset.filename}</h2>
          <p className="muted">{bytes(dataset.size_bytes)}. Here’s what MetricaML found.</p>
        </div>
        <button className="btn btn-sm" onClick={onClear}>Use a different file</button>
      </div>

      <dl className="tally tally-6">
        {stats.map(([k, v]) => <div key={k}><dt>{k}</dt><dd>{v}</dd></div>)}
      </dl>
      {p.duplicate_rows > 0 && <p className="note">Duplicate rows are kept as they are. Remove them from the file first if they shouldn’t count twice.</p>}

      <h3 className="h4">Columns</h3>
      <div className="table-scroll">
        <table className="data">
          <thead><tr><th>Column</th><th>Type</th><th className="r">Unique</th><th className="r">Missing</th><th>Recommendation</th></tr></thead>
          <tbody>
            {p.columns.map((c) => {
              const r = RECOMMENDATION[c.recommendation]
              return (
                <tr key={c.name}>
                  <td className="strong">{c.name}</td>
                  <td>{c.type}</td>
                  <td className="r">{c.unique.toLocaleString('en')}</td>
                  <td className="r">{c.missing ? `${c.missing} (${c.missing_pct}%)` : '0'}</td>
                  <td><span className={`chip chip-${r.tone}`}>{r.text}</span></td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>

      <details className="preview">
        <summary>Preview the first {p.preview.length} rows</summary>
        <div className="table-scroll">
          <table className="data compact">
            <thead><tr>{p.columns.map((c) => <th key={c.name}>{c.name}</th>)}</tr></thead>
            <tbody>
              {p.preview.map((row, i) => (
                <tr key={i}>{p.columns.map((c) => <td key={c.name}>{row[c.name] == null ? <span className="muted">empty</span> : String(row[c.name])}</td>)}</tr>
              ))}
            </tbody>
          </table>
        </div>
      </details>
    </div>
  )
}
