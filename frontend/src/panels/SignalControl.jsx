import { useState } from 'react'
import { api, DIRECTIONS, sigColor } from '../api'
import { SignalLight } from '../components'

export default function SignalControl({ dashboard, config, onNotify, onConfigChange }) {
  const [duration, setDuration] = useState(15)
  const [busy, setBusy] = useState(false)
  const [form, setForm] = useState(() => ({
    min_green_time: config?.min_green_time ?? 5,
    max_green_time: config?.max_green_time ?? 40,
    yellow_time: config?.yellow_time ?? 3,
    all_red_time: config?.all_red_time ?? 1,
    headway_seconds: config?.headway_seconds ?? 2.2,
    start_window_seconds: config?.start_window_seconds ?? 2.5,
    density_weight: config?.density_weight ?? 0.6,
    waiting_weight: config?.waiting_weight ?? 0.4,
    starvation_threshold_seconds: config?.starvation_threshold_seconds ?? 45,
  }))

  const setField = (key) => (e) => setForm((f) => ({ ...f, [key]: e.target.value }))

  const manual = async (d) => {
    setBusy(true)
    try {
      await api.manualSignal(d, Number(duration))
      onNotify(`Signal switch requested: ${d} (${duration}s)`, 'success')
    } catch (e) {
      onNotify(`Manual switch failed: ${e.message}`, 'error')
    } finally {
      setBusy(false)
    }
  }

  const toggleAdaptive = async (next) => {
    try {
      await api.setAdaptive(next)
      onNotify(`Adaptive mode ${next ? 'enabled' : 'disabled'}`, 'success')
      onConfigChange && onConfigChange()
    } catch (e) {
      onNotify(`Failed: ${e.message}`, 'error')
    }
  }

  const save = async () => {
    setBusy(true)
    try {
      const body = { ...form }
      body.min_green_time = Number(body.min_green_time)
      body.max_green_time = Number(body.max_green_time)
      body.yellow_time = Number(body.yellow_time)
      body.all_red_time = Number(body.all_red_time)
      body.headway_seconds = Number(body.headway_seconds)
      body.start_window_seconds = Number(body.start_window_seconds)
      body.density_weight = Number(body.density_weight)
      body.waiting_weight = Number(body.waiting_weight)
      body.starvation_threshold_seconds = Number(body.starvation_threshold_seconds)
      await api.updateConfig(body)
      onNotify('Signal parameters saved', 'success')
      onConfigChange && onConfigChange()
    } catch (e) {
      onNotify(`Save failed: ${e.message}`, 'error')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="signal-page">
      <section className="content-grid">
        <div className="intersection-panel">
          <div className="panel-heading">
            <h3>Signal override panel</h3>
            <span className={`badge ${dashboard.adaptive_mode !== false ? 'success' : 'warning'}`}>
              {dashboard.adaptive_mode !== false ? 'Adaptive ON' : 'Manual'}
            </span>
          </div>

          <div className="signal-matrix">
            {DIRECTIONS.map((d) => {
              const data = dashboard.directions?.[d] || {}
              return (
                <button key={d} className={`signal-btn ${d === dashboard.active_direction ? 'active' : ''}`} onClick={() => manual(d)} disabled={busy}>
                  <SignalLight state={data.signal_state || 'RED'} />
                  <strong>{d}</strong>
                  <span className="signal-state">{data.signal_state || 'RED'}</span>
                  <small>{data.count ?? 0} vehicles</small>
                </button>
              )
            })}
          </div>

          <div className="inline-form">
            <label>Green duration (s)
              <input type="number" className="input" value={duration} min={5} max={120} onChange={(e) => setDuration(e.target.value)} />
            </label>
            <div className="hint">Raises a YELLOW phase for the active direction, then moves GREEN to the chosen direction.</div>
          </div>

          <div className="info-box" style={{ marginTop: 16 }}>
            <h4>Adaptive mode</h4>
            <div className="btn-row">
              <button className={`btn ${dashboard.adaptive_mode !== false ? 'active' : ''}`} onClick={() => toggleAdaptive(true)}>Automatic (AI)</button>
              <button className={`btn ${dashboard.adaptive_mode === false ? 'active' : ''}`} onClick={() => toggleAdaptive(false)}>Manual override</button>
            </div>
            <div className="hint">In AI mode the controller chooses the direction with the most traffic and waiting time.</div>
          </div>
        </div>

        <div className="side-panel">
          <div className="info-box">
            <h4>Signal timing parameters</h4>
            {[
              ['min_green_time', 'Min green (s)'],
              ['max_green_time', 'Max green (s)'],
              ['yellow_time', 'Yellow / amber (s)'],
              ['all_red_time', 'All-red time (s)'],
              ['headway_seconds', 'Per vehicle (s)'],
              ['start_window_seconds', 'Startup window (s)'],
            ].map(([key, label]) => (
              <label key={key} className="form-row">
                <span>{label}</span>
                <input type="number" className="input" value={form[key]} onChange={setField(key)} />
              </label>
            ))}
            {[
              ['density_weight', 'Traffic volume weight'],
              ['waiting_weight', 'Waiting weight'],
              ['starvation_threshold_seconds', 'Fairness limit (s)'],
            ].map(([key, label]) => (
              <label key={key} className="form-row">
                <span>{label}</span>
                <input type="number" step="0.1" className="input" value={form[key]} onChange={setField(key)} />
              </label>
            ))}
            <button className="btn primary full" onClick={save} disabled={busy}>Apply signal parameters</button>
          </div>
        </div>
      </section>
    </div>
  )
}