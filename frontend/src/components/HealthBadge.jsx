import { useEffect, useState } from 'react'
import { fetchHealth } from '../lib/api'

export default function HealthBadge() {
  const [health, setHealth] = useState(null)

  useEffect(() => {
    let alive = true
    const load = async () => {
      try {
        const h = await fetchHealth()
        if (alive) setHealth(h)
      } catch (err) {
        if (alive) setHealth({ status: 'down', services: {}, error: err.message })
      }
    }
    load()
    const t = setInterval(load, 30000)
    return () => { alive = false; clearInterval(t) }
  }, [])

  const services = health?.services || {}
  const entries = Object.entries(services)
  const downCount = entries.filter(([, v]) => v !== 'ok').length
  const ok = health?.status === 'ok' && downCount === 0

  let label = 'checking…'
  if (health) {
    if (health.status === 'down') label = 'backend unreachable'
    else if (ok) label = 'all systems operational'
    else label = `${downCount} service${downCount > 1 ? 's' : ''} degraded`
  }
  const color = health == null ? 'var(--text-secondary)' : ok ? 'var(--success)' : 'var(--danger)'

  return (
    <div
      className="flex items-center gap-2 px-3 py-1.5 rounded-lg border text-xs"
      style={{ borderColor: 'var(--border)', background: 'var(--bg-card)' }}
      title={entries.map(([k, v]) => `${k}: ${v}`).join('\n') || health?.error || ''}
    >
      <span className="w-2 h-2 rounded-full" style={{ background: color }} />
      <span style={{ color: 'var(--text-secondary)' }}>{label}</span>
      {entries.length > 0 && (
        <span className="flex gap-1 ml-1">
          {entries.map(([k, v]) => (
            <span
              key={k}
              className="px-1.5 py-0.5 rounded"
              style={{
                background: 'var(--border)',
                color: v === 'ok' ? 'var(--success)' : 'var(--danger)',
              }}
            >
              {k}
            </span>
          ))}
        </span>
      )}
    </div>
  )
}
