import { useApp } from '../app-context'

/** Describes the machine the work runs on. `host` may come from a finished experiment. */
export default function HostPanel({ host, title = 'Where experiments run', showLimits = false }) {
  const { config } = useApp()
  const h = host || config.host
  const l = config.limits
  const machine = h.instance_type ? `${h.provider} ${h.instance_type}` : h.provider
  return (
    <section className="host" aria-label={title}>
      <h2 className="h3">{title}</h2>
      <dl className="facts">
        <div><dt>Machine</dt><dd>{machine}</dd></div>
        <div><dt>Operating system</dt><dd>{h.os}</dd></div>
        <div><dt>Runtime</dt><dd>Python {h.python}, scikit-learn {h.scikit_learn}</dd></div>
        {h.cpu_count && <div><dt>Compute</dt><dd>{h.cpu_count} vCPU{h.memory_mb ? `, ${(h.memory_mb / 1024).toFixed(1)} GB memory` : ''}</dd></div>}
        {h.zone && <div><dt>Zone</dt><dd>{h.zone}</dd></div>}
      </dl>
      {showLimits && (
        <>
          <h3 className="h4">Limits on this instance</h3>
          <dl className="facts">
            <div><dt>File size</dt><dd>{l.max_file_mb} MB</dd></div>
            <div><dt>Rows</dt><dd>{l.max_rows.toLocaleString('en')}</dd></div>
            <div><dt>Training time</dt><dd>{l.max_train_seconds} seconds</dd></div>
            <div><dt>At once</dt><dd>{l.concurrent_experiments} experiment</dd></div>
          </dl>
        </>
      )}
    </section>
  )
}
