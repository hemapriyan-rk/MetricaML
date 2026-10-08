import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api'
import { useApp } from '../app-context'
import { Spinner } from '../components/bits'
import ExperimentRow from '../components/ExperimentRow'
import HostPanel from '../components/HostPanel'
import { firstName, primaryLabel, primaryText } from '../format'

export default function Dashboard() {
  const { user } = useApp()
  const [exps, setExps] = useState(null)

  useEffect(() => {
    let live = true
    api.experiments().then((d) => live && setExps(d)).catch(() => live && setExps([]))
    return () => { live = false }
  }, [])

  const completed = exps?.filter((e) => e.status === 'completed') ?? []
  const best = completed.filter((e) => e.problem_type === 'classification').sort((a, b) => b.primary_value - a.primary_value)[0]

  return (
    <div className="page">
      <header className="page-head">
        <div>
          <h1>Welcome back, {firstName(user.name)}</h1>
          <p className="lede">Train a model, check how well it did, and keep the files.</p>
        </div>
        <Link to="/new" className="btn btn-primary">New experiment</Link>
      </header>

      {exps === null ? <Spinner /> : (
        <div className="split">
          <div className="split-main">
            <dl className="tally">
              <div><dt>Experiments run</dt><dd>{exps.length}</dd></div>
              <div><dt>Completed</dt><dd>{completed.length}</dd></div>
              <div>
                <dt>Best accuracy</dt>
                <dd>{best ? primaryText(best) : '–'}{best && <small>{best.algorithm_label}</small>}</dd>
              </div>
            </dl>

            <section aria-labelledby="recent">
              <div className="section-head">
                <h2 id="recent">Latest experiments</h2>
                {exps.length > 5 && <Link to="/experiments">See all {exps.length}</Link>}
              </div>
              {exps.length === 0 ? (
                <div className="empty">
                  <h3>No experiments yet</h3>
                  <p>Start with one of the built-in sample datasets or upload your own CSV, TXT or Excel file.</p>
                  <Link to="/new" className="btn btn-primary">Start your first experiment</Link>
                </div>
              ) : (
                <ul className="exp-list">{exps.slice(0, 5).map((e) => <ExperimentRow key={e.id} exp={e} />)}</ul>
              )}
            </section>
          </div>
          <aside className="split-side"><HostPanel showLimits /></aside>
        </div>
      )}
    </div>
  )
}
