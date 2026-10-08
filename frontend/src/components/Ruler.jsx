import { useEffect, useState } from 'react'

/**
 * The measurement scale that runs through MetricaML: a ruler with a pointer at the result
 * and, optionally, a hollow mark where a naive baseline would have landed.
 * Values are fractions of the scale (0–1).
 */
export default function Ruler({ value, baseline, size = 'md', label, baselineLabel, ticks = true, animate = true, tone, numbers = [0, 20, 40, 60, 80, 100] }) {
  const clamp = (v) => Math.max(0, Math.min(1, v ?? 0))
  const [pos, setPos] = useState(animate ? 0 : clamp(value))

  useEffect(() => {
    if (!animate) { setPos(clamp(value)); return }
    const id = requestAnimationFrame(() => setPos(clamp(value)))
    return () => cancelAnimationFrame(id)
  }, [value, animate])

  return (
    <div className={`ruler ruler-${size} ${tone ? `ruler-${tone}` : ''}`} role="img"
         aria-label={label || `Scale from 0 to 100 percent, result at ${Math.round(clamp(value) * 100)} percent`}>
      <div className="ruler-scale">
        <div className="ruler-ticks" aria-hidden="true" />
        <div className="ruler-fill" style={{ width: `${pos * 100}%` }} />
        {baseline != null && (
          <div className="ruler-baseline" style={{ left: `${clamp(baseline) * 100}%` }} title={baselineLabel}>
            <span />
          </div>
        )}
        <div className="ruler-pointer" style={{ left: `${pos * 100}%` }}><span /></div>
      </div>
      {size !== 'sm' && size !== 'xs' && ticks && (
        <div className="ruler-numbers" aria-hidden="true">
          {numbers.map((n) => <span key={n}>{n}</span>)}
        </div>
      )}
    </div>
  )
}
