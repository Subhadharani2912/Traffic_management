import { useCallback, useEffect, useState } from 'react'
import { api, sigColor } from '../api'
import LaneCalibration from './LaneCalibration'

export default function LiveMonitoring({ dashboard, status, onNotify }) {
  const [videos, setVideos] = useState([])
  const [selectedVideo, setSelectedVideo] = useState('')
  const [busy, setBusy] = useState(false)
  const [feedOnline, setFeedOnline] = useState(false)
  const [imageUrl, setImageUrl] = useState(null)
  const [calibrating, setCalibrating] = useState(false)

  const refreshVideos = useCallback(() => {
    api.videos().then((res) => {
      setVideos(res.videos || [])
      if (!selectedVideo && res.videos?.length === 1) setSelectedVideo(res.videos[0].name)
    }).catch(() => {})
  }, [selectedVideo])

  useEffect(refreshVideos, [refreshVideos])

  useEffect(() => {
    const url = api.streamUrl() + `?t=${Date.now()}`
    const img = new Image()
    img.onload = () => setFeedOnline(true)
    img.onerror = () => setFeedOnline(false)
    img.src = url
    setImageUrl(url)
    const timer = setInterval(() => {
      const fresh = api.streamUrl() + `?t=${Date.now()}`
      const probe = new Image()
      probe.onload = () => setFeedOnline(true)
      probe.onerror = () => setFeedOnline(false)
      probe.src = fresh
    }, 4000)
    return () => clearInterval(timer)
  }, [status.mode, status.is_running])

  const run = async (action, body = {}) => {
    setBusy(true)
    try {
      if (action === 'mode') {
        await api.mode(body.mode, body.video_name)
      } else if (action.startsWith('video:')) {
        const [, sub] = action.split(':')
        await api.videoControl(sub, body.video_name)
      } else {
        await api.control(action)
      }
    } catch (e) {
      onNotify(`Command failed: ${e.message}`, 'error')
    } finally {
      setBusy(false)
    }
  }

  const handleUpload = async (file) => {
    if (!file) return
    setBusy(true)
    try {
      const res = await api.uploadVideo(file)
      onNotify(`Uploaded ${res.filename}`, 'success')
      refreshVideos()
      setSelectedVideo(res.filename)
    } catch (err) {
      onNotify(`Upload failed: ${err.message}`, 'error')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="live-page">
      <section className="content-grid">
        <div className="intersection-panel">
          <div className="panel-heading">
            <h3>Video Feed</h3>
            <span className={`badge ${feedOnline ? 'success' : 'warning'}`}>
              {feedOnline ? 'LIVE FEED' : 'CONNECTING…'}
            </span>
          </div>
          <div className="feed-wrap">
            {imageUrl ? (
              <img className="live-feed" src={imageUrl} alt="Live traffic feed" />
            ) : (
              <div className="empty-note">Waiting for feed…</div>
            )}
            <div className="feed-statusbar">
              <span>{status.mode.toUpperCase()} MODE</span>
              <span>{status.is_paused ? 'PAUSED' : status.is_running ? 'RUNNING' : 'STOPPED'}</span>
              <span>{Number(dashboard.fps || 0).toFixed(1)} fps</span>
              <span className="feed-status-dot" style={{ background: feedOnline ? '#16a34a' : '#dc2626' }} />
            </div>
          </div>
        </div>

        <div className="side-panel">
          <div className="info-box">
            <h4>Controls</h4>
            <div className="btn-row">
              <button className="btn primary" disabled={busy} onClick={() => run('start')}>Start</button>
              <button className="btn" disabled={busy} onClick={() => run('pause')}>{status.is_paused ? 'Resume' : 'Pause'}</button>
              <button className="btn danger" disabled={busy} onClick={() => run('stop')}>Stop</button>
              <button className="btn" disabled={busy} onClick={() => run('restart')}>Restart</button>
            </div>
            <h4 style={{ marginTop: 16 }}>Mode</h4>
            <div className="btn-row">
              <button className={`btn ${status.mode === 'simulation' ? 'active' : ''}`} disabled={busy} onClick={() => run('mode', { mode: 'simulation' })}>Simulation</button>
              <button className={`btn ${status.mode === 'video' ? 'active' : ''}`} disabled={busy} onClick={() => run('mode', { mode: 'video' })}>Video</button>
            </div>
          </div>

          <div className="info-box">
            <h4>Video source</h4>
            <select className="input select" value={selectedVideo} onChange={(e) => setSelectedVideo(e.target.value)}>
              <option value="">— select video —</option>
              {videos.map((v) => (
                <option key={v.name} value={v.name}>{v.name} ({v.size_mb} MB)</option>
              ))}
            </select>
            <div className="btn-row">
              <button className="btn primary" disabled={busy || !selectedVideo} onClick={() => run('video:start', { video_name: selectedVideo })}>Process this video</button>
            </div>
            <div className="btn-row">
              <button className="btn" onClick={() => setCalibrating(true)}>Calibrate lane markings…</button>
            </div>
            <label className="btn upload-btn">
              Upload video…
              <input type="file" accept=".mp4,.avi,.mov,.mkv" onChange={(e) => handleUpload(e.target.files?.[0])} hidden />
            </label>
            <div className="hint">Supports .mp4, .avi, .mov, .mkv. Vehicles are detected and tracked automatically.</div>
          </div>
        </div>
      </section>

      <section className="analytics-panel">
        <h3>Tracked vehicles ({dashboard.tracked_vehicles?.length || 0})</h3>
        {dashboard.tracked_vehicles?.length ? (
          <div className="table-scroll">
            <table className="data-table">
              <thead>
                <tr><th>ID</th><th>Class</th><th>Direction</th><th>Speed</th><th>Wait</th><th>Status</th></tr>
              </thead>
              <tbody>
                {dashboard.tracked_vehicles.slice(-20).reverse().map((v) => (
                  <tr key={v.id}>
                    <td>#{v.id}</td>
                    <td>{v.class}</td>
                    <td>
                      <span className="dir-chip" style={{ borderColor: sigColor(dashboard.directions?.[v.direction]?.signal_state || 'RED') }}>{v.direction || 'UNKNOWN'}</span>
                    </td>
                    <td>{Number(v.speed || 0).toFixed(1)}</td>
                    <td>{Number(v.waiting_time || 0).toFixed(1)}s</td>
                    <td>{v.status}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="empty-note">No tracked vehicles yet — start the engine.</div>
        )}
      </section>

      {calibrating && (
        <LaneCalibration
          onClose={() => setCalibrating(false)}
          onSaved={(msg, kind) => onNotify(msg || 'Lane markings saved', kind || 'success')}
        />
      )}
    </div>
  )
}