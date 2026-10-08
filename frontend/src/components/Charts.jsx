import { compact, num } from '../format'

const short = (s, n = 14) => (s.length > n ? s.slice(0, n - 1) + '…' : s)

export function ConfusionMatrix({ labels, matrix }) {
  const rowTotals = matrix.map((r) => r.reduce((a, b) => a + b, 0))
  return (
    <div className="cm-wrap">
      <div className="cm-axis-y" aria-hidden="true">Actual</div>
      <div className="cm-scroll">
        <div className="cm" style={{ gridTemplateColumns: `minmax(64px, auto) repeat(${labels.length}, minmax(52px, 1fr))` }}>
          <div />
          {labels.map((l) => <div key={l} className="cm-head" title={l}>{short(l, 12)}</div>)}
          {matrix.map((row, i) => (
            <Row key={i} label={labels[i]} row={row} total={rowTotals[i]} index={i} labels={labels} />
          ))}
        </div>
        <div className="cm-axis-x" aria-hidden="true">Predicted</div>
      </div>
    </div>
  )
}

function Row({ label, row, total, index, labels }) {
  return (
    <>
      <div className="cm-rowhead" title={label}>{short(label, 14)}</div>
      {row.map((count, j) => {
        const share = total ? count / total : 0
        const diagonal = index === j
        const alpha = count === 0 ? 0 : 0.1 + share * 0.85
        return (
          <div key={j} className={`cm-cell ${count === 0 ? 'empty' : diagonal ? 'diag' : 'off'}`}
               style={{ '--a': alpha, color: diagonal && alpha > 0.5 ? '#fff' : undefined }}
               title={`${count} rows were '${label}' and predicted as '${labels[j]}' (${(share * 100).toFixed(0)}% of '${label}')`}>
            {count}
          </div>
        )
      })}
    </>
  )
}

export function ImportanceBars({ items }) {
  const max = Math.max(...items.map((i) => i.importance), 1e-9)
  return (
    <ol className="bars">
      {items.map((it) => (
        <li key={it.feature}>
          <span className="bar-name" title={it.feature}>{it.feature}</span>
          <span className="bar-track"><span className="bar-fill" style={{ width: `${Math.max(it.importance, 0) / max * 100}%` }} /></span>
          <span className="bar-val">{it.importance.toFixed(3)}</span>
        </li>
      ))}
    </ol>
  )
}

export function ClassBars({ labels, actual, predicted }) {
  const max = Math.max(...actual, ...predicted, 1)
  return (
    <div>
      <div className="legend">
        <span><i className="swatch actual" /> Actual</span>
        <span><i className="swatch predicted" /> Predicted</span>
      </div>
      <ul className="class-bars">
        {labels.map((l, i) => (
          <li key={l}>
            <span className="bar-name" title={l}>{l}</span>
            <span className="pair">
              <span className="bar-track"><span className="bar-fill actual" style={{ width: `${actual[i] / max * 100}%` }} /></span>
              <span className="bar-track"><span className="bar-fill predicted" style={{ width: `${predicted[i] / max * 100}%` }} /></span>
            </span>
            <span className="bar-val two"><b>{actual[i]}</b><b>{predicted[i]}</b></span>
          </li>
        ))}
      </ul>
    </div>
  )
}

function niceTicks(min, max, count = 5) {
  if (min === max) { min -= 1; max += 1 }
  const step0 = (max - min) / count
  const mag = Math.pow(10, Math.floor(Math.log10(step0)))
  const norm = step0 / mag
  const step = (norm < 1.5 ? 1 : norm < 3 ? 2 : norm < 7 ? 5 : 10) * mag
  const start = Math.ceil(min / step) * step
  const out = []
  for (let v = start; v <= max + step * 1e-6; v += step) out.push(Number(v.toPrecision(12)))
  return out
}

export function Scatter({ points, xLabel, yLabel }) {
  const W = 560, H = 380, L = 58, R = 16, T = 14, B = 46
  const all = points.flat()
  const lo = Math.min(...all), hi = Math.max(...all)
  const pad = (hi - lo) * 0.04 || 1
  const min = lo - pad, max = hi + pad
  const x = (v) => L + ((v - min) / (max - min)) * (W - L - R)
  const y = (v) => H - B - ((v - min) / (max - min)) * (H - T - B)
  const ticks = niceTicks(min, max)
  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="chart-svg" role="img"
         aria-label={`Scatter plot of actual against predicted ${yLabel}. Points close to the diagonal are accurate predictions.`}>
      {ticks.map((t) => (
        <g key={t}>
          <line x1={L} x2={W - R} y1={y(t)} y2={y(t)} className="grid" />
          <line x1={x(t)} x2={x(t)} y1={T} y2={H - B} className="grid" />
          <text x={L - 8} y={y(t) + 4} textAnchor="end" className="tick">{compact(t)}</text>
          <text x={x(t)} y={H - B + 18} textAnchor="middle" className="tick">{compact(t)}</text>
        </g>
      ))}
      <line x1={x(min)} y1={y(min)} x2={x(max)} y2={y(max)} className="ideal" />
      {points.map(([a, p], i) => <circle key={i} cx={x(a)} cy={y(p)} r="3.4" className="dot" />)}
      <text x={(L + W - R) / 2} y={H - 8} textAnchor="middle" className="axis-label">Actual {xLabel}</text>
      <text transform={`translate(14 ${(T + H - B) / 2}) rotate(-90)`} textAnchor="middle" className="axis-label">Predicted {yLabel}</text>
    </svg>
  )
}

export function Histogram({ edges, counts, xLabel }) {
  const W = 560, H = 300, L = 44, R = 16, T = 14, B = 46
  const min = edges[0], max = edges[edges.length - 1]
  const maxC = Math.max(...counts, 1)
  const x = (v) => L + ((v - min) / (max - min || 1)) * (W - L - R)
  const y = (c) => H - B - (c / maxC) * (H - T - B)
  const ticks = niceTicks(min, max, 5)
  const zero = min <= 0 && max >= 0
  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="chart-svg" role="img"
         aria-label={`Histogram of prediction errors for ${xLabel}. Bars centred on zero mean unbiased predictions.`}>
      {[0, 0.5, 1].map((f) => (
        <g key={f}>
          <line x1={L} x2={W - R} y1={y(maxC * f)} y2={y(maxC * f)} className="grid" />
          <text x={L - 8} y={y(maxC * f) + 4} textAnchor="end" className="tick">{Math.round(maxC * f)}</text>
        </g>
      ))}
      {counts.map((c, i) => (
        <rect key={i} x={x(edges[i]) + 1} y={y(c)} width={Math.max(x(edges[i + 1]) - x(edges[i]) - 2, 1)} height={H - B - y(c)} className="hist-bar" />
      ))}
      {zero && <line x1={x(0)} x2={x(0)} y1={T} y2={H - B} className="zero" />}
      {ticks.map((t) => <text key={t} x={x(t)} y={H - B + 18} textAnchor="middle" className="tick">{compact(t)}</text>)}
      <text x={(L + W - R) / 2} y={H - 8} textAnchor="middle" className="axis-label">Error (actual − predicted) in {xLabel} units</text>
    </svg>
  )
}

export function PerClassTable({ rows }) {
  return (
    <div className="table-scroll">
      <table className="data">
        <thead><tr><th>Class</th><th className="r">Precision</th><th className="r">Recall</th><th className="r">F1</th><th className="r">Rows</th></tr></thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.class}>
              <td>{r.class}</td>
              <td className="r">{num(r.precision * 100, 3)}%</td>
              <td className="r">{num(r.recall * 100, 3)}%</td>
              <td className="r">{num(r.f1 * 100, 3)}%</td>
              <td className="r">{r.support}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
