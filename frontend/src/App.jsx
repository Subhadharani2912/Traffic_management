import { useCallback, useMemo, useState } from 'react'
import './App.css'
import { api, defaultDashboard } from './api'
import { useTrafficSocket, usePolling, useEngineStatus } from './hooks'
import Dashboard from './panels/Dashboard'
import LiveMonitoring from './panels/LiveMonitoring'
import IntersectionView from './panels/IntersectionView'
import AnalyticsPanel from './panels/AnalyticsPanel'
import SignalControl from './panels/SignalControl'
import DetectionPanel from './panels/DetectionPanel'
import DatasetModel from './panels/DatasetModel'
import ReportsPanel from './panels/ReportsPanel'
import SettingsPanel from './panels/SettingsPanel'

const PANELS = [
  'Dashboard',
  'Live Monitoring',
  'Intersection',
  'Traffic Analytics',
  'Signal Control',
  'Vehicle Detection',
  'Dataset & Model',
  'Reports',
  'Settings',
]

function App() {
  const [panel, setPanel] = useState('Dashboard')
  const [dashboard, setDashboard] = useState(defaultDashboard)
  const [config, setConfig] = useState(null)
  const [summary, setSummary] = useState({ total_sessions: 0, avg_waiting_time: 0, peak_vehicles_detected: 0 })
  const [logs, setLogs] = useState([])
  const [toasts, setToasts] = useState([])
  const status = useEngineStatus()

  useTrafficSocket((state) => setDashboard((prev) => ({ ...prev, ...state })))

  const refreshStatic = useCallback(() => {
    api.config().then(setConfig).catch(() => {})
    api.analyticsSummary().then(setSummary).catch(() => {})
    api.logs(30).then((res) => setLogs(res || [])).catch(() => {})
  }, [])

  usePolling(refreshStatic, 5000)

  const notify = useCallback((message, kind = 'info') => {
    const id = Date.now() + Math.random()
    setToasts((t) => [...t, { id, message, kind }])
    setTimeout(() => setToasts((t) => t.filter((x) => x.id !== id)), 4200)
  }, [])

  const refreshConfig = useCallback(() => {
    api.config().then(setConfig).catch(() => {})
    refreshStatic()
  }, [refreshStatic])

  const renderPanel = useMemo(() => {
    switch (panel) {
      case 'Dashboard': return <Dashboard dashboard={dashboard} status={status} summary={summary} logs={logs} config={config} />
      case 'Live Monitoring': return <LiveMonitoring dashboard={dashboard} status={status} onNotify={notify} />
      case 'Intersection': return <IntersectionView dashboard={dashboard} />
      case 'Traffic Analytics': return <AnalyticsPanel onNotify={notify} />
      case 'Signal Control': return <SignalControl dashboard={dashboard} config={config} onNotify={notify} onConfigChange={refreshConfig} />
      case 'Vehicle Detection': return <DetectionPanel dashboard={dashboard} config={config} status={status} onNotify={notify} onConfigChange={refreshConfig} />
      case 'Dataset & Model': return <DatasetModel status={status} onNotify={notify} />
      case 'Reports': return <ReportsPanel onNotify={notify} />
      case 'Settings': return <SettingsPanel config={config} status={status} onNotify={notify} onConfigChange={refreshConfig} />
      default: return <Dashboard dashboard={dashboard} status={status} summary={summary} logs={logs} config={config} />
    }
  }, [panel, dashboard, status, summary, logs, config, notify, refreshConfig])

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand-block">
          <div className="traffic-light" aria-hidden="true"><i className="tl-red" /><i className="tl-yellow" /><i className="tl-green" /></div>
          <div className="brand-mark">AI</div>
          <div>
            <h2>Adaptive Traffic</h2>
            <small>Control Center</small>
          </div>
        </div>

        <nav className="nav">
          {PANELS.map((p) => (
            <button key={p} className={p === panel ? 'active' : ''} onClick={() => setPanel(p)}>{p}</button>
          ))}
        </nav>

        <div className="status-panel">
          <span className="label">System status</span>
          <strong>{status.is_running ? (status.is_paused ? 'PAUSED' : 'ONLINE') : 'STOPPED'}</strong>
          <span className="label">Source</span>
          <strong>{status.mode === 'video' ? 'VIDEO' : 'SIMULATION'}</strong>
          <span className="label">Model status</span>
          <strong>{status.model?.status || 'Pretrained YOLOv8n'}</strong>
        </div>
      </aside>

      <main className="main-content">
        <header className="topbar">
          <div>
            <p className="eyebrow">Operations Overview</p>
            <h1>{panel}</h1>
          </div>
          <div className="topbar-right">
            <span className={`badge ${dashboard.adaptive_mode !== false ? 'success' : 'warning'}`}>
              {dashboard.adaptive_mode !== false ? 'Adaptive Mode ON' : 'Manual Mode'}
            </span>
            <span className="clock">{new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</span>
          </div>
        </header>

        {dashboard.emergency?.active && (
          <div className="emergency-alert-banner" role="alert">
            <div className="emergency-alert-pulse">
              <span className="emergency-siren-icon">🚨</span>
            </div>
            <div className="emergency-alert-body">
              <div className="emergency-alert-title">
                <strong>EMERGENCY SIGNAL PREEMPTION ACTIVE</strong>
                <span className="emergency-badge">{dashboard.emergency.type ? dashboard.emergency.type.toUpperCase() : 'EMERGENCY'}</span>
                <span className="emergency-badge direction">APPROACH: {dashboard.emergency.direction}</span>
                {dashboard.emergency.vehicle_id != null && (
                  <span className="emergency-badge vid">TRACK #{dashboard.emergency.vehicle_id}</span>
                )}
              </div>
              <div className="emergency-alert-details">
                Status: <strong>{dashboard.emergency.status || 'ACTIVE'}</strong> · Timer: <strong>{Number(dashboard.emergency.timer_remaining || 0).toFixed(1)}s remaining</strong> (Window: {dashboard.emergency.duration || 15}s) · Multi-frame Confirmed
              </div>
            </div>
            <div className="emergency-alert-action">
              <button
                className="btn emergency-clear-btn"
                onClick={async () => {
                  try {
                    await api.emergencyClear()
                    notify('Emergency preemption cleared manually', 'success')
                  } catch (e) {
                    notify(`Failed to clear: ${e.message}`, 'error')
                  }
                }}
              >
                Clear Preemption
              </button>
            </div>
          </div>
        )}

        {renderPanel}
      </main>

      <div className="toasts">
        {toasts.map((t) => (
          <div key={t.id} className={`toast ${t.kind}`}>{t.message}</div>
        ))}
      </div>
    </div>
  )
}

export default App