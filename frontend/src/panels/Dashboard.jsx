import { DIRECTIONS, sigColor } from '../api'
import { DirectionCard } from '../components'

export default function Dashboard({ dashboard, status, summary, logs, config }) {
  const active = dashboard.directions?.[dashboard.active_direction] || {}
  const cards = DIRECTIONS.map((d) => ({ d, data: dashboard.directions?.[d] }))

  return (
    <>
      <section className="summary-grid">
        <div className="summary-card">
          <span>Active Vehicles</span>
          <strong>{dashboard.total_active_vehicles}</strong>
          <small>In scene right now</small>
        </div>
        <div className="summary-card">
          <span>Passed Vehicles</span>
          <strong>{dashboard.total_passed_vehicles}</strong>
          <small>This session</small>
        </div>
        <div className="summary-card">
          <span>Average Waiting</span>
          <strong>{Number(dashboard.system_avg_waiting_time || 0).toFixed(1)} s</strong>
          <small>Across directions</small>
        </div>
        <div className="summary-card">
          <span>Current Green</span>
          <strong>{dashboard.active_direction}</strong>
          <small>{dashboard.active_signal_state}</small>
        </div>
        <div className="summary-card">
          <span>Green Time</span>
          <strong>{Number(dashboard.current_green_time_assigned || 0).toFixed(0)} s</strong>
          <small>Remaining {Number(dashboard.remaining_green_time || 0).toFixed(1)} s</small>
        </div>
        <div className="summary-card accent">
          <span>Traffic Level</span>
          <strong>{active.density_level || 'LOW'}</strong>
          <small>{Number(active.count || 0)} vehicles · {Number(active.waiting_count || 0)} waiting</small>
        </div>
      </section>

      <section className="content-grid">
        <div className="intersection-panel">
          <div className="panel-heading">
            <h3>Intersection Visualization</h3>
            <span className="badge warning">{dashboard.active_direction} {dashboard.active_signal_state}</span>
          </div>
          <div className="intersection-scene">
            <div className="approach north">
              <span>NORTH</span>
              <div className="signal" style={{ background: sigColor(dashboard.directions?.NORTH?.signal_state || 'RED') }} />
            </div>
            <div className="approach west">
              <span>WEST</span>
              <div className="signal" style={{ background: sigColor(dashboard.directions?.WEST?.signal_state || 'RED') }} />
            </div>
            <div className="center-box">
              <div className="center-text">{dashboard.active_direction}</div>
              <div className="timer">{Number(dashboard.remaining_green_time || 0).toFixed(0)}s</div>
              <div className="mini-stats">
                <span>{dashboard.total_active_vehicles} vehicles</span>
                <span>{dashboard.active_signal_state}</span>
              </div>
            </div>
            <div className="approach east">
              <span>EAST</span>
              <div className="signal" style={{ background: sigColor(dashboard.directions?.EAST?.signal_state || 'RED') }} />
            </div>
            <div className="approach south">
              <span>SOUTH</span>
              <div className="signal" style={{ background: sigColor(dashboard.directions?.SOUTH?.signal_state || 'RED') }} />
            </div>
          </div>
        </div>

        <div className="side-panel">
          <div className="info-box">
            <h4>Current phase</h4>
            <div className="phase-row"><span>Current Green</span><strong>{dashboard.active_direction}</strong></div>
            <div className="phase-row"><span>Remaining time</span><strong>{Number(dashboard.remaining_green_time || 0).toFixed(1)}s</strong></div>
            <div className="phase-row"><span>Next Up</span><strong>{dashboard.next_direction}</strong></div>
            <div className="phase-row"><span>Frame rate</span><strong>{Number(dashboard.fps || 0).toFixed(1)} fps</strong></div>
          </div>
          <div className="info-box">
            <h4>System status</h4>
            <ul className="status-list">
              <li>Engine: <span>{status.is_running ? (status.is_paused ? 'PAUSED' : 'RUNNING') : 'STOPPED'}</span></li>
              <li>Mode: <span>{dashboard.mode}</span></li>
              <li>Model: <span>{status.model?.status || 'Checking…'}</span></li>
            </ul>
          </div>
        </div>
      </section>

      <section className="direction-grid">
        {cards.map(({ d, data }) => <DirectionCard key={d} d={d} data={data} />)}
      </section>

      <section className="analytics-row">
        <div className="analytics-panel">
          <h3>Historical summary</h3>
          <div className="stats-grid">
            <div><span>Total sessions</span><strong>{summary.total_sessions || 0}</strong></div>
            <div><span>Avg wait</span><strong>{Number(summary.avg_waiting_time || 0).toFixed(1)} s</strong></div>
            <div><span>Peak vehicles</span><strong>{summary.peak_vehicles_detected || 0}</strong></div>
            <div><span>Avg vehicles</span><strong>{Number(summary.avg_vehicles_per_frame || 0).toFixed(1)}</strong></div>
          </div>
        </div>
        <div className="analytics-panel log-panel">
          <h3>System log</h3>
          <ul>
            {logs.length > 0 ? logs.slice(0, 12).map((log) => (
              <li key={log.id}>
                <span className="log-time">{log.timestamp?.split(' ')[1] || ''}</span> {log.message}
              </li>
            )) : <li>System started</li>}
          </ul>
        </div>
      </section>
    </>
  )
}

export { DIRECTIONS }