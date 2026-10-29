import { useCallback, useEffect, useState } from 'react'
import { api } from '../api'

export default function ReportsPanel({ onNotify }) {
  const [reports, setReports] = useState([])
  const [loading, setLoading] = useState(false)
  const [downloading, setDownloading] = useState(null)
  const [format, setFormat] = useState('pdf')
  const [period, setPeriod] = useState('all')

  const refresh = useCallback(() => {
    api.reports().then((res) => setReports(res.reports || [])).catch(() => {})
  }, [])

  useEffect(refresh, [refresh])

  const downloadFile = async (filename) => {
    setDownloading(filename)
    try {
      const url = api.downloadReport(filename)
      const res = await fetch(url)
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const blob = await res.blob()
      const blobUrl = window.URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = blobUrl
      a.download = filename
      document.body.appendChild(a)
      a.click()
      window.URL.revokeObjectURL(blobUrl)
      document.body.removeChild(a)
      onNotify(`Downloaded: ${filename}`, 'success')
    } catch (e) {
      // Direct browser fallback trigger
      try {
        const a = document.createElement('a')
        a.href = api.downloadReport(filename)
        a.download = filename
        a.target = '_blank'
        document.body.appendChild(a)
        a.click()
        document.body.removeChild(a)
        onNotify(`Opening download: ${filename}`, 'info')
      } catch (err2) {
        onNotify(`Download failed: ${e.message}`, 'error')
      }
    } finally {
      setDownloading(null)
    }
  }

  const generate = async () => {
    setLoading(true)
    try {
      const res = await api.generateReport(format, period)
      onNotify(`Report generated: ${res.filename}. Starting download...`, 'success')
      refresh()
      if (res.filename) {
        await downloadFile(res.filename)
      }
    } catch (e) {
      onNotify(`Generation failed: ${e.message}`, 'error')
    } finally {
      setLoading(false)
    }
  }

  const latestReport = reports[0] || null

  return (
    <div className="reports-page">
      <section className="content-grid">
        <div className="intersection-panel">
          <div className="panel-heading">
            <h3>Generate & Download Report</h3>
          </div>
          <div className="inline-form">
            <label>Format
              <select className="input" value={format} onChange={(e) => setFormat(e.target.value)}>
                <option value="pdf">PDF Document (.pdf)</option>
                <option value="csv">CSV Spreadsheet (.csv)</option>
              </select>
            </label>
            <label>Period
              <select className="input" value={period} onChange={(e) => setPeriod(e.target.value)}>
                <option value="today">Today</option>
                <option value="7days">Last 7 days</option>
                <option value="30days">Last 30 days</option>
                <option value="all">All time</option>
              </select>
            </label>
          </div>
          <button className="btn primary" onClick={generate} disabled={loading}>
            {loading ? 'Generating & Downloading…' : `Generate & Download ${format.toUpperCase()}`}
          </button>
          <div className="hint">
            PDF bundles the analytics summary, per-direction tables, signal stats, and charts. CSV exports the raw
            sampling rows for spreadsheet analysis. The file will automatically download to your machine.
          </div>
        </div>

        <div className="side-panel">
          <div className="info-box">
            <h4>Quick Actions</h4>
            {latestReport ? (
              <div style={{ marginTop: '0.5rem' }}>
                <p style={{ fontSize: '0.85rem', color: '#94a3b8', marginBottom: '0.5rem' }}>
                  Latest file: <span className="mono">{latestReport.name}</span>
                </p>
                <button
                  className="btn primary small"
                  style={{ width: '100%' }}
                  onClick={() => downloadFile(latestReport.name)}
                  disabled={downloading === latestReport.name}
                >
                  {downloading === latestReport.name ? 'Downloading…' : `Download Latest (${latestReport.type.toUpperCase()})`}
                </button>
              </div>
            ) : (
              <p className="hint">Generate your first report to enable quick download.</p>
            )}
            <div className="btn-row" style={{ marginTop: '0.8rem' }}>
              {['pdf', 'csv'].map((f) => (
                <button key={f} className={`btn small ${format === f ? 'active' : ''}`} onClick={() => setFormat(f)}>
                  Select {f.toUpperCase()}
                </button>
              ))}
            </div>
          </div>
        </div>
      </section>

      <section className="analytics-panel">
        <h3>Generated Reports Archive ({reports.length})</h3>
        {reports.length ? (
          <div className="table-scroll">
            <table className="data-table">
              <thead>
                <tr><th>File</th><th>Type</th><th>Size</th><th>Created</th><th>Action</th></tr>
              </thead>
              <tbody>
                {reports.map((r) => (
                  <tr key={r.name}>
                    <td className="mono">{r.name}</td>
                    <td>{(r.type || (r.name.split('.').pop() || '')).toUpperCase()}</td>
                    <td>{(r.size_kb ?? 0) < 1024 ? `${Number(r.size_kb || 0).toFixed(1)} KB` : `${(Number(r.size_kb || 0) / 1024).toFixed(1)} MB`}</td>
                    <td>{r.created || '—'}</td>
                    <td>
                      <button
                        className="btn small primary"
                        onClick={() => downloadFile(r.name)}
                        disabled={downloading === r.name}
                      >
                        {downloading === r.name ? 'Saving…' : 'Download'}
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="empty-note">No reports generated yet — click 'Generate & Download' above.</div>
        )}
      </section>
    </div>
  )
}