import { Link } from 'react-router-dom'
import { primaryLabel, primaryText, seconds, when } from '../format'
import { Spinner, Status } from './bits'
import Ruler from './Ruler'

export default function ExperimentRow({ exp }) {
  const done = exp.status === 'completed'
  return (
    <li className="exp-row">
      <Link to={`/experiments/${exp.id}`} className="exp-link">
        <span className="exp-id">#{exp.id}</span>
        <span className="exp-main">
          <strong>{exp.algorithm_label}</strong>
          <span className="muted">{exp.dataset_name}, predicting {exp.target}</span>
        </span>
        <span className="exp-score">
          {done ? (
            <>
              <span className="exp-value"><b>{primaryText(exp)}</b> <small>{primaryLabel(exp)}</small></span>
              <Ruler value={exp.primary_value} size="xs" animate={false} />
            </>
          ) : exp.status === 'running' ? <span className="exp-running"><Spinner /> Running</span>
            : <span className="exp-fail" title={exp.error}>{exp.error ? 'Did not finish' : 'Failed'}</span>}
        </span>
        <span className="exp-meta">
          <Status status={exp.status} />
          <span className="muted">{when(exp.created_at)}{done && exp.duration_s ? `, took ${seconds(exp.duration_s)}` : ''}</span>
        </span>
      </Link>
    </li>
  )
}
