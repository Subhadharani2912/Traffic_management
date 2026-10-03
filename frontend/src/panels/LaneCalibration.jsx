import { useEffect, useRef, useState } from 'react'
import { api, DIRECTIONS } from '../api'

const COLORS = { NORTH: '#ef4444', SOUTH: '#38bdf8', WEST: '#f59e0b', EAST: '#22d3ee' }

const DEFAULT_ROIS = {
  NORTH: [0.35, 0.0, 0.65, 0.4],
  SOUTH: [0.35, 0.6, 0.65, 1.0],
  WEST: [0.0, 0.35, 0.4, 0.65],
  EAST: [0.6, 0.35, 1.0, 0.65],
}

function toQuad(box) {
  if (Array.isArray(box) && box.length === 4 && Array.isArray(box[0])) {
    return box.map((p) => [Number(p[0]), Number(p[1])])
  }
  const b = box && box.length === 4 ? box.map(Number) : [0.3, 0.3, 0.7, 0.7]
  const [x1, y1, x2, y2] = b
  return [[x1, y1], [x2, y1], [x2, y2], [x1, y2]]
}

function autoIntersection(quads) {
  const inner = []
  for (const q of Object.values(quads)) {
    const cx = q.reduce((s, p) => s + p[0], 0) / q.length
    const cy = q.reduce((s, p) => s + p[1], 0) / q.length
    const ranked = [...q].sort((a, b) => {
      const da = (a[0] - cx) ** 2 + (a[1] - cy) ** 2
      const db = (b[0] - cx) ** 2 + (b[1] - cy) ** 2
      return da - db
    })
    inner.push(ranked[0], ranked[1])
  }
  const xs = inner.map((p) => p[0])
  const ys = inner.map((p) => p[1])
  return [Math.min(...xs), Math.min(...ys), Math.max(...xs), Math.max(...ys)]
}

export default function LaneCalibration({ onClose, onSaved }) {
  const [rois, setRois] = useState(null)
  const [img, setImg] = useState(null)
  const [dragging, setDragging] = useState(null)
  const [saving, setSaving] = useState(false)
  const canvasRef = useRef(null)
  const sizeRef = useRef({ w: 0, h: 0 })

  useEffect(() => {
    api.config()
      .then((cfg) => {
        const r = {}
        for (const d of DIRECTIONS) r[d] = toQuad(cfg.rois?.[d])
        setRois(r)
      })
      .catch(() => {})
    const im = new Image()
    im.onload = () => setImg(im)
    im.src = api.frameStillUrl()
  }, [])

  useEffect(() => {
    if (!img) return
    const maxW = 820
    const maxH = 560
    const scale = Math.min(maxW / img.naturalWidth, maxH / img.naturalHeight)
    const w = Math.round(img.naturalWidth * scale)
    const h = Math.round(img.naturalHeight * scale)
    sizeRef.current = { w, h }
    const canvas = canvasRef.current
    canvas.width = w
    canvas.height = h
    redraw()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [img, rois, dragging])

  const redraw = () => {
    const canvas = canvasRef.current
    if (!canvas || !sizeRef.current.w) return
    const ctx = canvas.getContext('2d')
    const { w, h } = sizeRef.current
    ctx.clearRect(0, 0, w, h)
    if (img) ctx.drawImage(img, 0, 0, w, h)

    if (!rois) return
    for (const d of DIRECTIONS) {
      const pts = rois[d].map((p) => [p[0] * w, p[1] * h])
      ctx.beginPath()
      ctx.moveTo(pts[0][0], pts[0][1])
      for (let i = 1; i < 4; i++) ctx.lineTo(pts[i][0], pts[i][1])
      ctx.closePath()
      ctx.fillStyle = COLORS[d] + '44'
      ctx.fill()
      ctx.strokeStyle = COLORS[d]
      ctx.lineWidth = 2.5
      ctx.stroke()
      const mx = pts.reduce((s, p) => s + p[0], 0) / 4
      const my = pts.reduce((s, p) => s + p[1], 0) / 4
      ctx.font = '600 13px sans-serif'
      ctx.fillStyle = '#ffffff'
      ctx.shadowColor = 'rgba(0,0,0,0.85)'
      ctx.shadowBlur = 4
      ctx.fillText(d, mx - 14, my + 4)
      ctx.shadowBlur = 0
      for (const p of pts) {
        ctx.beginPath()
        ctx.arc(p[0], p[1], 5, 0, Math.PI * 2)
        ctx.fillStyle = '#ffffff'
        ctx.fill()
        ctx.strokeStyle = COLORS[d]
        ctx.lineWidth = 2
        ctx.stroke()
      }
    }

    const ib = autoIntersection(rois)
    ctx.setLineDash([5, 4])
    ctx.strokeStyle = '#fde047'
    ctx.lineWidth = 1.5
    ctx.strokeRect(ib[0] * w, ib[1] * h, (ib[2] - ib[0]) * w, (ib[3] - ib[1]) * h)
    ctx.setLineDash([])
    ctx.fillStyle = '#fde047'
    ctx.font = '600 12px sans-serif'
    ctx.fillText('AUTO INTERSECTION ZONE', ib[0] * w + 5, ib[1] * h + 16)
  }

  const posFromEvent = (e) => {
    const rect = canvasRef.current.getBoundingClientRect()
    return { x: e.clientX - rect.left, y: e.clientY - rect.top }
  }

  const handleAt = ({ x, y }) => {
    const { w, h } = sizeRef.current
    for (const d of DIRECTIONS) {
      for (let i = 0; i < 4; i++) {
        const p = rois[d][i]
        const dx = (p[0] * w - x) ** 2
        const dy = (p[1] * h - y) ** 2
        if (Math.sqrt(dx + dy) < 13) return { dir: d, idx: i }
      }
    }
    return null
  }

  const onPointerDown = (e) => {
    if (!rois) return
    e.preventDefault()
    const hit = handleAt(posFromEvent(e))
    if (hit) {
      setDragging(hit)
      canvasRef.current.setPointerCapture(e.pointerId)
    }
  }

  const onPointerMove = (e) => {
    if (!dragging || !rois) return
    const { x, y } = posFromEvent(e)
    const { w, h } = sizeRef.current
    const nx = Math.min(1, Math.max(0, x / w))
    const ny = Math.min(1, Math.max(0, y / h))
    setRois((prev) => {
      const next = {}
      for (const d of DIRECTIONS) next[d] = prev[d].map((p, i) => (i === dragging.idx ? [nx, ny] : p))
      return next
    })
  }

  const onPointerUp = () => setDragging(null)

  const restoreSaved = () => {
    api.config()
      .then((cfg) => {
        const r = {}
        for (const d of DIRECTIONS) r[d] = toQuad(cfg.rois?.[d])
        setRois(r)
      })
      .catch(() => {})
  }

  const resetDefaults = () => {
    const r = {}
    for (const d of DIRECTIONS) r[d] = toQuad(DEFAULT_ROIS[d])
    setRois(r)
  }

  const save = async () => {
    setSaving(true)
    try {
      const roisOut = {}
      for (const d of DIRECTIONS) roisOut[d] = rois[d].map((p) => [Number(p[0].toFixed(4)), Number(p[1].toFixed(4))])
      const payload = { rois: roisOut, intersection_box: autoIntersection(rois).map((n) => Number(n.toFixed(4))) }
      await api.updateConfig(payload)
      onSaved()
      onClose()
    } catch (err) {
      onSaved(`Save failed: ${err.message}`, 'error')
    } finally {
      setSaving(false)
    }
  }

  if (!img || !rois) {
    return (
      <div className="modal-backdrop">
        <div className="modal-card"><h3>Calibrate Lanes</h3><p className="cal-hint">Loading a still frame…</p></div>
      </div>
    )
  }

  return (
    <div className="modal-backdrop">
      <div className="modal-card">
        <h3>Calibrate Lanes</h3>
        <p className="cal-hint">
          Drag the white corner dots of each coloured lane mark so the mark sits on its real road.
          The yellow rectangle (intersection zone) is computed automatically.
        </p>
        <div className="cal-legend">
          {DIRECTIONS.map((d) => (
            <span key={d}><i className="cal-swatch" style={{ background: COLORS[d] }} />{d}</span>
          ))}
          <span className="cal-note">North = top of the picture, South = bottom, West = left, East = right</span>
        </div>
        <canvas
          ref={canvasRef}
          className="cal-canvas"
          onPointerDown={onPointerDown}
          onPointerMove={onPointerMove}
          onPointerUp={onPointerUp}
          onPointerLeave={onPointerUp}
        />
        <div className="cal-actions">
          <button className="btn" onClick={restoreSaved}>Undo</button>
          <button className="btn" onClick={resetDefaults}>Reset</button>
          <button className="btn primary" disabled={saving} onClick={save}>{saving ? 'Saving…' : 'Save markings'}</button>
        </div>
      </div>
    </div>
  )
}