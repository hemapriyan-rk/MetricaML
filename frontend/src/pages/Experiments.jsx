import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api'
import { Spinner } from '../components/bits'
import ExperimentRow from '../components/ExperimentRow'

const FILTERS = [['all', 'All'], ['completed', 'Completed'], ['failed', 'Failed'], ['running', 'Running']]

export default function Experiments() {
  const [exps, setExps] = useState(null)
  const [filter, setFilter] = useState('all')

  useEffect(() => {
    let live = true
    const load = () => api.experiments().then((d) => live && setExps(d)).catch(() => live && setExps([]))
    load()
    return () => { live = false }
  }, [])

  const shown = exps?.filter((e) => filter === 'all' || e.status === filter) ?? []

  return (
    <div className="page">
      <header className="page-head">
        <div>
          <h1>My experiments</h1>
          <p className="lede">Every run is saved with its settings, so you can reopen the results or reproduce it later.</p>
        </div>
        <Link to="/new" className="btn btn-primary">New experiment</Link>
      </header>

      {exps === null ? <Spinner /> : (
        <>
          <div className="segmented" role="group" aria-label="Filter by status">
            {FILTERS.map(([key, label]) => (
              <button key={key} className={filter === key ? 'on' : ''} aria-pressed={filter === key} onClick={() => setFilter(key)}>
                {label}
              </button>
            ))}
          </div>
          {shown.length === 0 ? (
            <div className="empty">
              <h3>{exps.length === 0 ? 'No experiments yet' : `No ${filter} experiments`}</h3>
              <p>{exps.length === 0 ? 'Your finished experiments will be listed here.' : 'Try another filter.'}</p>
              {exps.length === 0 && <Link to="/new" className="btn btn-primary">Start an experiment</Link>}
            </div>
          ) : (
            <ul className="exp-list">{shown.map((e) => <ExperimentRow key={e.id} exp={e} />)}</ul>
          )}
        </>
      )}
    </div>
  )
}
