import { useCallback, useEffect, useState } from 'react'
import { api } from '../api'

export default function ReportsPanel({ onNotify }) {
  const [reports, setReports] = useState([])
  const [loading, setLoading] = useState(false)
  const [format, setFormat] = useState('pdf')
  const [period, setPeriod] = useState('all')

  const refresh = useCallback(() => {
    api.reports().then((res) => setReports(res.reports || [])).catch(() => {})
  }, [])

  useEffect(refresh, [refresh])

  const generate = async () => {
    setLoading(true)
    try {
      const res = await api.generateReport(format, period)
      onNotify(`Report generated: ${res.filename}`, 'success')
      refresh()
    } catch (e) {
      onNotify(`Generation failed: ${e.message}`, 'error')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="reports-page">
      <section className="content-grid">
        <div className="intersection-panel">
          <div className="panel-heading">
            <h3>Generate report</h3>
          </div>
          <div className="inline-form">
            <label>Format
              <select className="input" value={format} onChange={(e) => setFormat(e.target.value)}>
                <option value="pdf">PDF</option>
                <option value="csv">CSV</option>
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
            {loading ? 'Generating…' : 'Generate report'}
          </button>
          <div className="hint">
            PDF bundles the analytics summary, per-direction tables, signal stats and charts. CSV exports the raw
            sampling rows for spreadsheet analysis.
          </div>
        </div>

        <div className="side-panel">
          <div className="info-box">
            <h4>Download</h4>
            <div className="btn-row">
              {['pdf', 'csv'].map((f) => (
                <a key={f} className={`btn ${format === f ? 'active' : ''}`} onClick={() => setFormat(f)}>{f.toUpperCase()}</a>
              ))}
            </div>
            <p className="hint">Pick a format above, then generate. Files open in a new tab.</p>
          </div>
        </div>
      </section>

      <section className="analytics-panel">
        <h3>Generated reports ({reports.length})</h3>
        {reports.length ? (
          <div className="table-scroll">
            <table className="data-table">
              <thead>
                <tr><th>File</th><th>Type</th><th>Size</th><th>Created</th><th></th></tr>
              </thead>
              <tbody>
                {reports.map((r) => (
                  <tr key={r.name}>
                    <td className="mono">{r.name}</td>
                    <td>{(r.type || (r.name.split('.').pop() || '')).toUpperCase()}</td>
                    <td>{(r.size_kb ?? 0) < 1024 ? `${Number(r.size_kb || 0).toFixed(1)} KB` : `${(Number(r.size_kb || 0) / 1024).toFixed(1)} MB`}</td>
                    <td>{r.created || '—'}</td>
                    <td><a className="btn small" href={api.downloadReport(r.name)} target="_blank" rel="noreferrer">Download</a></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="empty-note">No reports yet — generate one above.</div>
        )}
      </section>
    </div>
  )
}