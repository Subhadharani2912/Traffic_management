const API = 'http://localhost:8000'

async function getJSON(path, timeout = 8000) {
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), timeout)
  try {
    const res = await fetch(`${API}${path}`, { signal: controller.signal })
    if (!res.ok) throw new Error(`${path} -> ${res.status}`)
    return res.json()
  } finally {
    clearTimeout(timer)
  }
}

async function postJSON(path, body, timeout = 20000) {
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), timeout)
  try {
    const res = await fetch(`${API}${path}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body || {}),
      signal: controller.signal,
    })
    if (!res.ok) {
      const data = await res.json().catch(() => ({}))
      throw new Error((data.detail ? JSON.stringify(data.detail) : `${path} -> ${res.status}`))
    }
    return res.json()
  } finally {
    clearTimeout(timer)
  }
}

export const api = {
  base: API,
  config: () => getJSON('/api/traffic/config'),
  updateConfig: (body) => postJSON('/api/traffic/config', body),
  state: () => getJSON('/api/traffic/state'),
  engineStatus: () => getJSON('/api/traffic/status'),
  streamUrl: () => `${API}/api/traffic/stream`,
  frameStillUrl: () => `${API}/api/traffic/frame_still`,
  wsUrl: () => `${API.replace('http', 'ws')}/ws`,
  control: (action) => postJSON('/api/traffic/control', { action }),
  mode: (mode, video_name) => postJSON('/api/traffic/mode', { mode, video_name }),
  manualSignal: (direction, duration) => postJSON('/api/traffic/signal/manual', { direction, duration }),
  setAdaptive: (adaptive) => postJSON('/api/traffic/signal/adaptive', { adaptive }),
  logs: (limit = 30) => getJSON(`/api/traffic/logs?limit=${limit}`),
  analyticsSummary: (period = 'all') => getJSON(`/api/analytics/summary?filter_period=${period}`),
  analyticsCharts: (period = 'all') => getJSON(`/api/analytics/charts?filter_period=${period}`),
  modelStatus: () => getJSON('/api/model/status'),
  videos: () => getJSON('/api/video/list'),
  uploadVideo: (file) => {
    const fd = new FormData()
    fd.append('file', file)
    return fetch(`${API}/api/video/upload`, { method: 'POST', body: fd }).then((r) => r.json())
  },
  videoControl: (action, video_name) => postJSON('/api/video/control', { action, video_name }),
  reports: () => getJSON('/api/reports/list'),
  generateReport: (format = 'pdf', period = 'all') =>
    postJSON('/api/reports/generate', { format, filter_period: period }, 60000),
  downloadReport: (name) => `${API}/api/reports/download/${encodeURIComponent(name)}`,
}

export const DIRECTIONS = ['NORTH', 'SOUTH', 'EAST', 'WEST']

export const sigColor = (state) => {
  if (state === 'GREEN') return '#22c55e'
  if (state === 'YELLOW') return '#fbbf24'
  return '#ef4444'
}

export const densityColor = (level) => {
  if (level === 'HIGH') return '#ef4444'
  if (level === 'MEDIUM') return '#f59e0b'
  return '#22c55e'
}

export const fmt = (v, d = 1) => (v === null || v === undefined || Number.isNaN(Number(v)) ? '0' : Number(v).toFixed(d))

export const defaultDashboard = {
  mode: 'simulation',
  active_direction: 'NORTH',
  active_signal_state: 'GREEN',
  current_green_time_assigned: 20,
  remaining_green_time: 15,
  next_direction: 'SOUTH',
  next_priority_score: 0,
  total_active_vehicles: 0,
  total_waiting_vehicles: 0,
  total_passed_vehicles: 0,
  system_avg_waiting_time: 0,
  system_max_waiting_time: 0,
  fps: 0,
  adaptive_mode: true,
  directions: {
    NORTH: { direction: 'NORTH', count: 0, waiting_count: 0, density_level: 'LOW', density_percent: 0, priority_score: 0, signal_state: 'RED', avg_waiting_time: 0, max_waiting_time: 0, starvation_timer: 0 },
    SOUTH: { direction: 'SOUTH', count: 0, waiting_count: 0, density_level: 'LOW', density_percent: 0, priority_score: 0, signal_state: 'RED', avg_waiting_time: 0, max_waiting_time: 0, starvation_timer: 0 },
    EAST: { direction: 'EAST', count: 0, waiting_count: 0, density_level: 'LOW', density_percent: 0, priority_score: 0, signal_state: 'RED', avg_waiting_time: 0, max_waiting_time: 0, starvation_timer: 0 },
    WEST: { direction: 'WEST', count: 0, waiting_count: 0, density_level: 'LOW', density_percent: 0, priority_score: 0, signal_state: 'RED', avg_waiting_time: 0, max_waiting_time: 0, starvation_timer: 0 },
  },
  tracked_vehicles: [],
}