import { useMemo, useState } from 'react'
import { api, DIRECTIONS } from '../api'

const COCO_CLASSES = [
  { id: 2, label: 'car' },
  { id: 3, label: 'motorcycle' },
  { id: 5, label: 'bus' },
  { id: 7, label: 'truck' },
]

const DETRAC_CLASSES = [
  { id: 0, label: 'car' },
  { id: 1, label: 'van' },
  { id: 2, label: 'bus' },
  { id: 3, label: 'others' },
]

export default function DetectionPanel({ dashboard, config, status, onNotify, onConfigChange }) {
  const [busy, setBusy] = useState(false)
  const [form, setForm] = useState(() => ({
    confidence_threshold: config?.confidence_threshold ?? 0.4,
    iou_threshold: config?.iou_threshold ?? 0.45,
    processing_fps: config?.processing_fps ?? 15,
  }))

  const setField = (key) => (e) => setForm((f) => ({ ...f, [key]: e.target.value }))

  const classCatalog = (config?.target_classes ?? [2, 3, 5, 7]).every((c) => c < 4) ? DETRAC_CLASSES : COCO_CLASSES
  const [selected, setSelected] = useState(() => new Set(config?.target_classes ?? [2, 3, 5, 7]))

  const toggleClass = (id) => {
    setSelected((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  const save = async () => {
    setBusy(true)
    try {
      const body = {
        confidence_threshold: Number(form.confidence_threshold),
        iou_threshold: Number(form.iou_threshold),
        processing_fps: Number(form.processing_fps),
        target_classes: Array.from(selected),
      }
      await api.updateConfig(body)
      onNotify('Detection settings saved', 'success')
      onConfigChange && onConfigChange()
    } catch (e) {
      onNotify(`Save failed: ${e.message}`, 'error')
    } finally {
      setBusy(false)
    }
  }

  const classCounts = useMemo(() => {
    const counts = {}
    for (const v of dashboard.tracked_vehicles || []) {
      counts[v.class] = (counts[v.class] || 0) + 1
    }
    return counts
  }, [dashboard.tracked_vehicles])

  const perDirection = useMemo(() => {
    const out = {}
    for (const d of DIRECTIONS) {
      out[d] = dashboard.directions?.[d]?.count ?? 0
    }
    return out
  }, [dashboard])

  return (
    <div className="detection-page">
      <section className="content-grid">
        <div className="intersection-panel">
          <div className="panel-heading">
            <h3>Detection & tracking</h3>
            <span className="badge success">YOLOv8 · ByteTrack</span>
          </div>

          <div className="inline-form">
            <label>Confidence
              <input type="number" step="0.05" min="0.05" max="0.95" className="input" value={form.confidence_threshold} onChange={setField('confidence_threshold')} />
            </label>
            <label>Overlap (IoU)
              <input type="number" step="0.05" min="0.1" max="0.9" className="input" value={form.iou_threshold} onChange={setField('iou_threshold')} />
            </label>
            <label>Process FPS
              <input type="number" min="5" max="60" className="input" value={form.processing_fps} onChange={setField('processing_fps')} />
            </label>
          </div>

          <h4 style={{ margin: '16px 4px 8px' }}>Target vehicle classes</h4>
          <div className="chip-row">
            {classCatalog.map((c) => (
              <button
                key={c.id}
                className={`class-chip ${selected.has(c.id) ? 'active' : ''}`}
                onClick={() => toggleClass(c.id)}
              >
                {c.label}
              </button>
            ))}
          </div>
          <button className="btn primary" onClick={save} disabled={busy}>Apply detection settings</button>

          <div className="info-box" style={{ marginTop: 18 }}>
            <h4>Detection stats</h4>
            <div className="stats-grid four">
              {Object.entries(classCounts).map(([cls, n]) => (
                <div key={cls}><span>{cls}</span><strong>{n}</strong></div>
              ))}
              {Object.keys(classCounts).length === 0 && <div className="hint">No detections yet in this window.</div>}
            </div>
          </div>
        </div>

        <div className="side-panel">
          <div className="info-box">
            <h4>Active model</h4>
            <ul className="status-list">
              <li>Model: <span>{status.model?.active_model || 'Checking…'}</span></li>
              <li>Status: <span>{status.model?.status || '—'}</span></li>
              <li>Custom trained: <span>{status.model?.is_custom_trained ? 'Yes' : 'No'}</span></li>
            </ul>
          </div>
          <div className="info-box">
            <h4>Active count by direction</h4>
            {DIRECTIONS.map((d) => (
              <div className="phase-row" key={d}><span>{d}</span><strong>{perDirection[d]}</strong></div>
            ))}
          </div>
        </div>
      </section>

      <section className="analytics-panel">
        <h3>Current tracked vehicles ({dashboard.tracked_vehicles?.length || 0})</h3>
        {dashboard.tracked_vehicles?.length ? (
          <div className="table-scroll">
            <table className="data-table">
              <thead>
                <tr><th>ID</th><th>Class</th><th>Direction</th><th>Speed</th><th>Wait</th><th>Status</th></tr>
              </thead>
              <tbody>
                {dashboard.tracked_vehicles.slice(-15).reverse().map((v) => (
                  <tr key={v.id}>
                    <td>#{v.id}</td>
                    <td>{v.class}</td>
                    <td>{v.direction || 'UNKNOWN'}</td>
                    <td>{Number(v.speed || 0).toFixed(1)}</td>
                    <td>{Number(v.waiting_time || 0).toFixed(1)}s</td>
                    <td>{v.status}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="empty-note">No detections yet. Detection runs automatically in video mode.</div>
        )}
      </section>
    </div>
  )
}