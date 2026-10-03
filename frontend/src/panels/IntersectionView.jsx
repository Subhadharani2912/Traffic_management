import { DIRECTIONS, sigColor, densityColor } from '../api'
import { SignalLight } from '../components'

const layout = {
  NORTH: { label: 'NORTH', cls: 'north', pos: { top: 0, left: '50%' } },
  SOUTH: { label: 'SOUTH', cls: 'south', pos: { bottom: 0, left: '50%' } },
  WEST: { label: 'WEST', cls: 'west', pos: { left: 0, top: '50%' } },
  EAST: { label: 'EAST', cls: 'east', pos: { right: 0, top: '50%' } },
}

export default function IntersectionView({ dashboard }) {
  return (
    <div className="intersection-page">
      <section className="content-grid">
        <div className="intersection-panel">
          <div className="panel-heading">
            <h3>4-Way Intersection — Signal Board</h3>
            <span className="badge warning">ACTIVE: {dashboard.active_direction} ({dashboard.active_signal_state})</span>
          </div>

          <div className="big-intersection">
            {DIRECTIONS.map((d) => {
              const data = dashboard.directions?.[d] || {}
              const p = layout[d]
              return (
                <div className={`big-approach ${p.cls}`} key={d} style={p.pos}>
                  <div className="approach-card">
                    <div className="approach-top">
                      <strong>{d}</strong>
                      <SignalLight state={data.signal_state || 'RED'} />
                    </div>
                    <div className="approach-metrics">
                      <span>Count <b>{data.count ?? 0}</b></span>
                      <span>Density <b style={{ color: densityColor(data.density_level || 'LOW') }}>{data.density_level || 'LOW'}</b></span>
                      <span>Wait <b>{Number(data.avg_waiting_time || 0).toFixed(1)}s</b></span>
                    </div>
                  </div>
                </div>
              )
            })}

            <div className="big-center">
              <div className="big-center-top">
                <span>NEXT</span>
                <strong>{dashboard.next_direction}</strong>
              </div>
              <div className="big-timer">{Number(dashboard.remaining_green_time || 0).toFixed(0)}<small>s left</small></div>
              <div className="big-center-state">{dashboard.active_signal_state}</div>
              <div className="big-center-bottom">
                <span>Green {Number(dashboard.current_green_time_assigned || 0).toFixed(0)}s</span>
                <span>{dashboard.total_active_vehicles} active</span>
              </div>
            </div>
          </div>

          <div className="phase-timeline">
            {DIRECTIONS.map((d, i) => (
              <div key={d} className={`phase-step ${d === dashboard.active_direction ? 'active' : ''}`}>
                <span className="step-index">{i + 1}</span>
                <strong>{d}</strong>
                <SignalLight state={dashboard.directions?.[d]?.signal_state || 'RED'} size={16} />
              </div>
            ))}
          </div>
        </div>

        <div className="side-panel">
          <div className="info-box">
            <h4>Signal states</h4>
            {DIRECTIONS.map((d) => (
              <div className="phase-row" key={d}>
                <span style={{ display: 'inline-flex', alignItems: 'center', gap: 8 }}>
                  <SignalLight state={dashboard.directions?.[d]?.signal_state || 'RED'} size={14} /> {d}
                </span>
                <strong style={{ color: sigColor(dashboard.directions?.[d]?.signal_state || 'RED') }}>{dashboard.directions?.[d]?.signal_state || 'RED'}</strong>
              </div>
            ))}
          </div>
          <div className="info-box">
            <h4>Approach status</h4>
            {DIRECTIONS.map((d) => {
              const data = dashboard.directions?.[d] || {}
              return (
                <div className="phase-row" key={d}>
                  <span>{d}</span>
                  <strong style={{ color: densityColor(data.density_level || 'LOW') }}>{data.density_level || 'LOW'} · {Number(data.count || 0)} veh</strong>
                </div>
              )
            })}
          </div>
        </div>
      </section>
    </div>
  )
}