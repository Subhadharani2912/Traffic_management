import { DIRECTIONS, sigColor, densityColor } from './api'

export function HBarChart({ data, valueKey, labelKey = 'direction', colorFn = () => '#38bdf8', height = 64 }) {
  const max = Math.max(1, ...data.map((d) => Number(d[valueKey]) || 0))
  return (
    <div className="hbar-chart">
      {data.map((d) => {
        const v = Number(d[valueKey]) || 0
        const pct = (v / max) * 100
        return (
          <div className="hbar-row" key={d[labelKey]}>
            <span className="hbar-label">{d[labelKey]}</span>
            <div className="hbar-track">
              <div className="hbar-fill" style={{ width: `${pct}%`, background: colorFn(d[labelKey]) }} />
            </div>
            <span className="hbar-value">{v}</span>
          </div>
        )
      })}
    </div>
  )
}

export function DensityChart({ data }) {
  const total = Math.max(1, data.reduce((s, d) => s + (d.count || 0), 0))
  const tones = { LOW: '#16a34a', MEDIUM: '#f59e0b', HIGH: '#dc2626' }
  const order = { LOW: 0, MEDIUM: 1, HIGH: 2 }
  const sorted = [...data].sort((a, b) => order[a.level] - order[b.level])
  return (
    <div className="density-chart">
      {sorted.length === 0 && <div className="empty-note">No samples yet — run the simulation to collect data.</div>}
      {sorted.map((d) => (
        <div className="density-row" key={d.level}>
          <span className="hbar-label" style={{ color: tones[d.level] }}>{d.level}</span>
          <div className="hbar-track">
            <div className="hbar-fill" style={{ width: `${(d.count / total) * 100}%`, background: tones[d.level] }} />
          </div>
          <span className="hbar-value">{d.count}</span>
        </div>
      ))}
    </div>
  )
}

export function TimeSeries({ history }) {
  const points = history.map((h) => Number(h.north_count || 0) + Number(h.south_count || 0) + Number(h.east_count || 0) + Number(h.west_count || 0))
  const max = Math.max(1, ...points)
  const w = 700
  const h = 160
  const stepX = (w - 10) / Math.max(1, points.length - 1)
  const path = points
    .map((p, i) => `${i === 0 ? 'M' : 'L'}${10 + i * stepX},${h - 20 - (p / max) * (h - 40)}`)
    .join(' ')
  const area = `${path} L${10 + (points.length - 1) * stepX},${h - 10} L10,${h - 10} Z`

  return (
    <div className="time-series">
      {points.length < 2 ? (
        <div className="empty-note">Collecting samples…</div>
      ) : (
        <svg viewBox={`0 0 ${w} ${h}`} className="ts-svg">
          <defs>
            <linearGradient id="tsFill" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#38bdf8" stopOpacity="0.5" />
              <stop offset="100%" stopColor="#38bdf8" stopOpacity="0.05" />
            </linearGradient>
          </defs>
          <path d={area} fill="url(#tsFill)" />
          <path d={path} fill="none" stroke="#38bdf8" strokeWidth="2" />
          <line x1="10" y1={h - 10} x2={w - 10} y2={h - 10} stroke="rgba(148,163,184,0.3)" strokeWidth="1" />
          <text x={w - 80} y={h - 16} fill="#94a3b8" fontSize="10">{points[points.length - 1]} active</text>
        </svg>
      )}
    </div>
  )
}

export function SignalLight({ state, size = 22 }) {
  return <span className="signal-light" style={{ width: size, height: size, background: sigColor(state), boxShadow: `0 0 14px ${sigColor(state)}` }} />
}

export function DirectionCard({ d, data }) {
  const item = data || {}
  return (
    <div className="direction-card">
      <div className="direction-header">
        <h4>{d}</h4>
        <span className="signal-pill" style={{ background: sigColor(item.signal_state || 'RED') }}>{item.signal_state || 'RED'}</span>
      </div>
      <div className="metric-row">
        <span>Vehicle count</span>
        <strong>{Number(item.count || 0)}</strong>
      </div>
      <div className="metric-row">
        <span>Waiting now</span>
        <strong>{Number(item.waiting_count || 0)}</strong>
      </div>
      <div className="metric-row">
        <span>Density</span>
        <strong style={{ color: densityColor(item.density_level || 'LOW') }}>{item.density_level || 'LOW'}</strong>
      </div>
      <div className="metric-row">
        <span>Waiting time</span>
        <strong>{Number(item.avg_waiting_time || 0).toFixed(1)} s</strong>
      </div>
    </div>
  )
}

export function Spinner({ label = 'Loading…' }) {
  return (
    <div className="spinner-box">
      <div className="spinner" />
      <span>{label}</span>
    </div>
  )
}

export { DIRECTIONS }