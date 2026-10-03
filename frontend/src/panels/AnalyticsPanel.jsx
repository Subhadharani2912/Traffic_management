import { useCallback, useEffect, useState } from 'react'
import { api, densityColor } from '../api'
import { HBarChart, DensityChart, TimeSeries, Spinner } from '../components'

const PERIODS = [
  { key: 'today', label: 'Today' },
  { key: '7days', label: 'Last 7 days' },
  { key: '30days', label: 'Last 30 days' },
  { key: 'all', label: 'All time' },
]

export default function AnalyticsPanel({ onNotify }) {
  const [period, setPeriod] = useState('all')
  const [summary, setSummary] = useState(null)
  const [charts, setCharts] = useState(null)
  const [loading, setLoading] = useState(false)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const [s, c] = await Promise.all([
        api.analyticsSummary(period),
        api.analyticsCharts(period),
      ])
      setSummary(s)
      setCharts(c)
    } catch (e) {
      onNotify(`Analytics unavailable: ${e.message}`, 'error')
    } finally {
      setLoading(false)
    }
  }, [period, onNotify])

  useEffect(() => { load() }, [load])

  const dirColor = {
    NORTH: '#38bdf8',
    SOUTH: '#34d399',
    EAST: '#fbbf24',
    WEST: '#f472b6',
  }

  if (loading && !summary) return <Spinner label="Loading analytics…" />

  return (
    <div className="analytics-page">
      <div className="toolbar">
        <div className="seg">
          {PERIODS.map((p) => (
            <button key={p.key} className={`seg-btn ${period === p.key ? 'active' : ''}`} onClick={() => setPeriod(p.key)}>{p.label}</button>
          ))}
        </div>
        <button className="btn" onClick={load}>Refresh</button>
      </div>

      <section className="summary-grid">
        <div className="summary-card"><span>Total sessions</span><strong>{summary?.total_sessions ?? 0}</strong><small>recorded</small></div>
        <div className="summary-card"><span>Vehicles</span><strong>{summary?.total_vehicles_recorded ?? 0}</strong><small>cumulative</small></div>
        <div className="summary-card"><span>Signal changes</span><strong>{summary?.total_signal_cycles ?? 0}</strong><small>counted</small></div>
        <div className="summary-card"><span>Avg vehicles</span><strong>{Number(summary?.avg_vehicles_per_frame ?? 0).toFixed(1)}</strong><small>per sample</small></div>
        <div className="summary-card"><span>Peak vehicles</span><strong>{summary?.peak_vehicles_detected ?? 0}</strong><small>detected</small></div>
        <div className="summary-card"><span>Avg waiting</span><strong>{Number(summary?.avg_waiting_time ?? 0).toFixed(1)} s</strong><small>overall</small></div>
        <div className="summary-card"><span>Max waiting</span><strong>{Number(summary?.max_waiting_time ?? 0).toFixed(1)} s</strong><small>overall</small></div>
        <div className="summary-card accent"><span>Avg green</span><strong>{Number(summary?.avg_green_duration ?? 0).toFixed(1)} s</strong><small>{summary?.records_count ?? 0} samples</small></div>
      </section>

      <section className="chart-grid">
        <div className="analytics-panel">
          <h3>Volume by direction</h3>
          <HBarChart data={charts?.volume_by_direction || []} valueKey="count" colorFn={(d) => dirColor[d]} />
        </div>
        <div className="analytics-panel">
          <h3>Average waiting time by direction</h3>
          <HBarChart data={charts?.waiting_by_direction || []} valueKey="avg_wait" colorFn={(d) => dirColor[d]} />
        </div>
        <div className="analytics-panel">
          <h3>Signal phase usage</h3>
          {charts?.signal_usage?.length ? (
            <HBarChart data={charts.signal_usage} valueKey="count" labelKey="direction" colorFn={(d) => dirColor[d]} />
          ) : <div className="empty-note">No signal samples recorded yet.</div>}
        </div>
        <div className="analytics-panel">
          <h3>Density breakdown</h3>
          <DensityChart data={charts?.density_breakdown || []} />
        </div>
        <div className="analytics-panel chart-wide">
          <h3>Active vehicles over time</h3>
          <TimeSeries history={charts?.history || []} />
        </div>
      </section>
    </div>
  )
}