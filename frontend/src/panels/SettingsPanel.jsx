import { useState } from 'react'
import { api } from '../api'

export default function SettingsPanel({ config, status, onNotify, onConfigChange }) {
  const [form, setForm] = useState(() => ({
    max_vehicles: config?.max_vehicles ?? 50,
    processing_fps: config?.processing_fps ?? 15,
    confidence_threshold: config?.confidence_threshold ?? 0.3,
    iou_threshold: config?.iou_threshold ?? 0.45,
    min_green_time: config?.min_green_time ?? 5,
    max_green_time: config?.max_green_time ?? 40,
    yellow_time: config?.yellow_time ?? 3,
    all_red_time: config?.all_red_time ?? 1,
    headway_seconds: config?.headway_seconds ?? 2.2,
    start_window_seconds: config?.start_window_seconds ?? 2.5,
    simulation: config?.simulation ?? {},
    report: config?.report ?? 'pdf',
  }))
  const [busy, setBusy] = useState(false)

  const setField = (key) => (e) => setForm((f) => ({ ...f, [key]: e.target.value }))

  const save = async () => {
    setBusy(true)
    try {
      const body = {
        max_vehicles: Number(form.max_vehicles),
        processing_fps: Number(form.processing_fps),
        confidence_threshold: Number(form.confidence_threshold),
        iou_threshold: Number(form.iou_threshold),
        min_green_time: Number(form.min_green_time),
        max_green_time: Number(form.max_green_time),
        yellow_time: Number(form.yellow_time),
        all_red_time: Number(form.all_red_time),
        headway_seconds: Number(form.headway_seconds),
        start_window_seconds: Number(form.start_window_seconds),
      }
      await api.updateConfig(body)
      onNotify('Configuration saved', 'success')
      onConfigChange && onConfigChange()
    } catch (e) {
      onNotify(`Save failed: ${e.message}`, 'error')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="settings-page">
      <section className="content-grid">
        <div className="intersection-panel">
          <div className="panel-heading">
            <h3>System configuration</h3>
          </div>
          <div className="settings-grid">
            <div className="info-box">
              <h4>Engine</h4>
              <label className="form-row"><span>Max vehicles in scene</span><input type="number" className="input" value={form.max_vehicles} onChange={setField('max_vehicles')} /></label>
              <label className="form-row"><span>Processing FPS</span><input type="number" className="input" value={form.processing_fps} onChange={setField('processing_fps')} /></label>
              <label className="form-row"><span>Default report format</span>
                <select className="input" value={form.report} onChange={setField('report')}>
                  <option value="pdf">PDF</option>
                  <option value="csv">CSV</option>
                </select>
              </label>
            </div>
            <div className="info-box">
              <h4>Detection</h4>
              <label className="form-row"><span>Confidence threshold</span><input type="number" step="0.05" className="input" value={form.confidence_threshold} onChange={setField('confidence_threshold')} /></label>
              <label className="form-row"><span>Overlap (IoU)</span><input type="number" step="0.05" className="input" value={form.iou_threshold} onChange={setField('iou_threshold')} /></label>
            </div>
            <div className="info-box">
              <h4>Signal timing</h4>
              <label className="form-row"><span>Min green (s)</span><input type="number" className="input" value={form.min_green_time} onChange={setField('min_green_time')} /></label>
              <label className="form-row"><span>Max green (s)</span><input type="number" className="input" value={form.max_green_time} onChange={setField('max_green_time')} /></label>
              <label className="form-row"><span>Yellow (s)</span><input type="number" className="input" value={form.yellow_time} onChange={setField('yellow_time')} /></label>
              <label className="form-row"><span>All-red (s)</span><input type="number" className="input" value={form.all_red_time} onChange={setField('all_red_time')} /></label>
              <label className="form-row"><span>Per vehicle (s)</span><input type="number" step="0.1" className="input" value={form.headway_seconds} onChange={setField('headway_seconds')} /></label>
              <label className="form-row"><span>Startup window (s)</span><input type="number" step="0.1" className="input" value={form.start_window_seconds} onChange={setField('start_window_seconds')} /></label>
            </div>
            <div className="info-box">
              <h4>Backend</h4>
              <ul className="status-list">
                <li>Mode: <span>{status.mode}</span></li>
                <li>Running: <span>{status.is_running ? 'yes' : 'no'}</span></li>
                <li>Paused: <span>{status.is_paused ? 'yes' : 'no'}</span></li>
              </ul>
            </div>
          </div>
          <div className="btn-row" style={{ marginTop: 12 }}>
            <button className="btn primary" onClick={save} disabled={busy}>Save configuration</button>
          </div>
          <div className="hint">Changes apply immediately to the running engine without a restart.</div>
        </div>
      </section>
    </div>
  )
}