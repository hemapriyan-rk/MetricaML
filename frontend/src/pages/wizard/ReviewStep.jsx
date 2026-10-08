import { useApp } from '../../app-context'
import { PREP_LABELS } from './helpers'

export default function ReviewStep({ dataset, profile, target, problem, features, algo, params, prep }) {
  const { config } = useApp()
  const spec = config.algorithms[problem].find((a) => a.key === algo)
  const host = config.host
  const where = host.instance_type ? `${host.provider} ${host.instance_type}` : host.provider
  const test = Math.round(prep.test_size * 100)

  return (
    <div>
      <h2>Review and run</h2>
      <p className="muted">This is the experiment that will run on {where}. Nothing is executed until you press the button.</p>

      <dl className="sheet">
        <div><dt>Dataset</dt><dd>{dataset.filename}<span className="muted">{profile.rows.toLocaleString('en')} rows, {profile.columns_count} columns</span></dd></div>
        <div><dt>Target</dt><dd>{target}<span className="muted">{problem === 'classification' ? 'Classification' : 'Regression'}</span></dd></div>
        <div><dt>Features</dt><dd>{features.length} columns<span className="muted">{features.slice(0, 8).join(', ')}{features.length > 8 ? `, and ${features.length - 8} more` : ''}</span></dd></div>
        <div><dt>Algorithm</dt><dd>{spec.label}<span className="muted">{spec.params.map((p) => `${p.label.replace(/ \(.*\)/, '').toLowerCase()} ${String(params[p.name]).replace(/_/g, ' ')}`).join(', ')}</span></dd></div>
        <div><dt>Preparation</dt><dd>{PREP_LABELS.encoding[prep.encoding]} and {PREP_LABELS.scaling[prep.scaling]}<span className="muted">Missing numbers filled with the {PREP_LABELS.missing[prep.missing]}</span></dd></div>
        <div><dt>Train / test</dt><dd>{100 - test} / {test}<span className="muted">Random state {prep.random_state}</span></dd></div>
      </dl>

      <p className="note">
        The run stops automatically after {config.limits.max_train_seconds} seconds. {config.limits.concurrent_experiments === 1 && 'One experiment runs at a time on this instance.'}
      </p>
    </div>
  )
}
