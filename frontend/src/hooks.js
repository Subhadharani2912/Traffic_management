import { useEffect, useRef, useState, useCallback } from 'react'
import { api } from './api'

export function useTrafficSocket(onState) {
  const onStateRef = useRef(onState)
  onStateRef.current = onState

  useEffect(() => {
    let ws = null
    let retry = 0
    let closed = false

    const connect = () => {
      if (closed) return
      try {
        ws = new WebSocket(api.wsUrl())
      } catch {
        setTimeout(connect, 3000)
        return
      }

      ws.onopen = () => {
        retry = 0
      }

      ws.onmessage = (ev) => {
        try {
          const msg = JSON.parse(ev.data)
          if (msg.type === 'state' && msg.data) {
            onStateRef.current(msg.data)
          }
        } catch {
          /* ignore malformed frames */
        }
      }

      ws.onclose = () => {
        if (!closed) {
          const delay = Math.min(5000, 1000 * 2 ** retry)
          retry += 1
          setTimeout(connect, delay)
        }
      }

      ws.onerror = () => {
        try {
          ws.close()
        } catch {
          /* noop */
        }
      }
    }

    connect()

    return () => {
      closed = true
      try {
        ws && ws.close()
      } catch {
        /* noop */
      }
    }
  }, [])
}

export function usePolling(fn, interval = 3000, deps = []) {
  const fnRef = useRef(fn)
  fnRef.current = fn

  useEffect(() => {
    fnRef.current()
    const timer = setInterval(() => fnRef.current(), interval)
    return () => clearInterval(timer)
  }, deps) // eslint-disable-line react-hooks/exhaustive-deps
}

export function useConfig() {
  const [config, setConfig] = useState(null)
  usePolling(() => {
    api.config()
      .then(setConfig)
      .catch(() => {})
  }, 5000)
  return [config, setConfig]
}

export function useEngineStatus() {
  const [status, setStatus] = useState({ is_running: true, is_paused: false, mode: 'simulation' })
  usePolling(() => {
    api
      .engineStatus()
      .then(setStatus)
      .catch(() => {})
  }, 3000)
  return status
}