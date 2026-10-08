import { useEffect, useRef, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { api } from '../api'
import { useApp } from '../app-context'
import { Alert, Icon, Spinner } from '../components/bits'
import HostPanel from '../components/HostPanel'
import Ruler from '../components/Ruler'
import { seconds } from '../format'
import Results from './Results'

export default function ExperimentPage() {
  const { id } = useParams()
  const [exp, setExp] = useState(null)
  const [error, setError] = useState('')
  const [shown, setShown] = useState(0) // stage rows revealed as done while the run plays out
  const [replayDone, setReplayDone] = useState(false)
  const firstStatus = useRef(null)

  // Poll while the experiment is running.
  useEffect(() => {
    let live = true
    let timer
    setExp(null); setError(''); setShown(0); setReplayDone(false); firstStatus.current = null
    const load = async () => {
      try {
        const data = await api.experiment(id)
        if (!live) return
        if (firstStatus.current === null) firstStatus.current = data.status
        setExp(data)
        if (data.status === 'running') timer = setTimeout(load, 700)
      } catch (err) {
        if (live) setError(err.message)
      }
    }
    load()
    return () => { live = false; clearTimeout(timer) }
  }, [id])

  const total = exp?.stages.length || 7
  const target = exp ? (exp.status === 'completed' ? total : exp.stages.filter((s) => s.ended).length) : 0

  // Reveal completed stages one at a time so even a fast run is readable.
  useEffect(() => {
    if (!exp || firstStatus.current !== 'running') return
    if (shown >= target) { if (exp.status === 'completed' && shown >= total) setReplayDone(true); return }
    const t = setTimeout(() => setShown((s) => s + 1), 380)
    return () => clearTimeout(t)
  }, [exp, shown, target, total])

  if (error) return <div className="page"><Alert>{error}</Alert><Link to="/experiments">Back to my experiments</Link></div>
  if (!exp) return <div className="page"><Spinner label="Loading experiment" /></div>

  const playing = firstStatus.current === 'running' && exp.status !== 'failed' && !replayDone
  if (exp.status === 'completed' && !playing) return <Results exp={exp} />
  return <Progress exp={exp} shown={shown} />
}

function Progress({ exp, shown }) {
  const { config } = useApp()
  const failed = exp.status === 'failed'
  const limit = config.limits.max_train_seconds
  const created = useRef(Date.now())
  const [elapsed, setElapsed] = useState(0)
  const navigate = useNavigate()

  useEffect(() => {
    if (failed) return
    const t = setInterval(() => setElapsed((Date.now() - created.current) / 1000), 250)
    return () => clearInterval(t)
  }, [failed])

  const stages = exp.stages.length ? exp.stages : config.stages.map((name) => ({ name }))
  const failedIndex = failed ? Math.max(0, stages.map((s) => !!s.started).lastIndexOf(true)) : -1

  const stateOf = (i) => {
    if (failed) return i < failedIndex ? 'done' : i === failedIndex ? 'failed' : 'pending'
    return i < shown ? 'done' : i === shown ? 'active' : 'pending'
  }
  const duration = (s) => (s.started && s.ended ? seconds(s.ended - s.started) : '')

  return (
    <div className="page wide">
      <header className="page-head">
        <div>
          <p className="crumb"><Link to="/experiments">My experiments</Link></p>
          <h1>Experiment #{exp.id}</h1>
          <p className="lede">{exp.algorithm_label} on {exp.dataset_name}, predicting {exp.target}</p>
        </div>
      </header>

      <div className="split">
        <div className="split-main">
          <ol className="stages" aria-live="polite">
            {stages.map((s, i) => {
              const st = stateOf(i)
              return (
                <li key={s.name} className={`stage stage-${st}`}>
                  <span className="stage-mark" aria-hidden="true">
                    {st === 'done' ? Icon.check : st === 'failed' ? Icon.cross : st === 'active' ? <Spinner /> : null}
                  </span>
                  <span className="stage-name">{s.name}</span>
                  <span className="stage-time muted">{st === 'done' ? duration(s) : st === 'active' ? 'in progress' : st === 'failed' ? 'stopped here' : ''}</span>
                  <span className="sr">{st}</span>
                </li>
              )
            })}
          </ol>

          {failed ? (
            <div className="failure">
              <h2>This experiment didn’t finish</h2>
              <p>{exp.error}</p>
              <div className="btn-row">
                <button className="btn btn-primary" onClick={() => navigate('/new')}>Set up another experiment</button>
                <button className="btn" onClick={async () => { await api.deleteExperiment(exp.id); navigate('/experiments') }}>Delete this run</button>
              </div>
            </div>
          ) : (
            <div className="clock">
              <div className="clock-head">
                <span>Time on the instance</span>
                <b>{seconds(elapsed)}</b><span className="muted"> of {limit} s allowed</span>
              </div>
              <Ruler value={Math.min(elapsed / limit, 1)} size="md" animate={false} ticks={false} label={`${Math.round(elapsed)} seconds of ${limit} used`} />
            </div>
          )}
        </div>
        <aside className="split-side">
          <HostPanel host={exp.host} title={failed ? 'It ran on' : 'Running on'} />
        </aside>
      </div>
    </div>
  )
}
