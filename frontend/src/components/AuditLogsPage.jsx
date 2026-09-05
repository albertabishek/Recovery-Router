import { useState, useEffect, useCallback } from 'react'
import { fetchAuditLogs, fetchEventTrace } from '../lib/api'
import { getDateParams } from './DateRangePicker'

const fmt = (n) => new Intl.NumberFormat('en-IN', { maximumFractionDigits: 0 }).format(n)

const timeAgo = (iso) => {
  if (!iso) return '—'
  const diff = (Date.now() - new Date(iso).getTime()) / 1000
  if (diff < 60) return 'just now'
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`
  return `${Math.floor(diff / 86400)}d ago`
}

const OutcomeBadge = ({ outcome }) => {
  const colors = {
    sent: { bg: '#ECFDF3', color: '#027A48', border: '#A6F4C5' },
    failed: { bg: '#FEF3F2', color: '#B42318', border: '#FECDCA' },
    delivered: { bg: '#ECFDF3', color: '#027A48', border: '#A6F4C5' },
    give_up: { bg: '#FFF4ED', color: '#B93815', border: '#FDDCAB' },
    blocked: { bg: '#FFFAEB', color: '#B54708', border: '#FEC84B' },
    reserved: { bg: '#F0F4FF', color: '#3538CD', border: '#C7D7FE' },
  }
  const c = colors[outcome] || { bg: '#F2F4F7', color: '#172b4d', border: '#ebecf0' }
  return (
    <span style={{
      display: 'inline-block', padding: '2px 10px', borderRadius: 12,
      fontSize: 12, fontWeight: 600, background: c.bg, color: c.color,
      border: `1px solid ${c.border}`, textTransform: 'capitalize',
    }}>
      {outcome || 'unknown'}
    </span>
  )
}

const ProviderStep = ({ step }) => {
  const isOk = step.status === 'sent'
  const isFail = step.status === 'failed'
  return (
    <div style={{
      display: 'flex', alignItems: 'flex-start', gap: 10, padding: '6px 0',
      borderLeft: `2px solid ${isOk ? '#04db7c' : isFail ? '#F04438' : '#D0D5DD'}`,
      paddingLeft: 12, marginLeft: 6,
    }}>
      <span style={{
        width: 8, height: 8, borderRadius: '50%', flexShrink: 0, marginTop: 5,
        background: isOk ? '#04db7c' : isFail ? '#F04438' : '#F79009',
      }} />
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ fontSize: 13, fontWeight: 500, color: '#172b4d' }}>
          {step.provider}
          <span style={{ fontWeight: 400, color: '#5e6c84', marginLeft: 8 }}>{step.status}</span>
        </div>
        {step.error && (
          <div style={{ fontSize: 12, color: '#B42318', marginTop: 2, wordBreak: 'break-word' }}>{step.error}</div>
        )}
      </div>
    </div>
  )
}

const TracePanel = ({ eventId, onClose }) => {
  const [trace, setTrace] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    fetchEventTrace(eventId)
      .then(setTrace)
      .catch(() => setTrace(null))
      .finally(() => setLoading(false))
  }, [eventId])

  if (loading) return (
    <div style={{ padding: 24, textAlign: 'center', color: '#5e6c84' }}>Loading trace...</div>
  )
  if (!trace) return (
    <div style={{ padding: 24, color: '#B42318' }}>Failed to load trace for event #{eventId}</div>
  )

  const ev = trace.event
  const attempts = trace.attempts || []

  return (
    <div style={{
      position: 'fixed', top: 0, right: 0, bottom: 0, width: 520,
      background: '#fff', boxShadow: '-4px 0 24px rgba(0,0,0,0.12)',
      zIndex: 100, display: 'flex', flexDirection: 'column', overflow: 'hidden',
    }}>
      <div style={{
        padding: '16px 20px', borderBottom: '1px solid #ebecf0',
        display: 'flex', justifyContent: 'space-between', alignItems: 'center',
      }}>
        <span style={{ fontSize: 15, fontWeight: 700, color: '#172b4d' }}>Event #{ev.id} Trace</span>
        <button onClick={onClose} style={{
          background: 'none', border: 'none', cursor: 'pointer',
          fontSize: 18, color: '#5e6c84', padding: '4px 8px',
        }}>✕</button>
      </div>

      <div style={{ flex: 1, overflow: 'auto', padding: 20 }}>
        <div style={{ marginBottom: 20 }}>
          <div style={{ fontSize: 11, fontWeight: 700, color: '#5e6c84', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: 10 }}>
            Event Details
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px 16px', fontSize: 13 }}>
            <div><span style={{ color: '#5e6c84' }}>Type:</span> <span style={{ fontWeight: 500 }}>{ev.event_type}</span></div>
            <div><span style={{ color: '#5e6c84' }}>Amount:</span> <span style={{ fontWeight: 500 }}>₹{fmt(ev.amount)}</span></div>
            <div><span style={{ color: '#5e6c84' }}>Category:</span> <span style={{ fontWeight: 500 }}>{(ev.failure_category || '—').replace(/_/g, ' ')}</span></div>
            <div><span style={{ color: '#5e6c84' }}>Channel:</span> <span style={{ fontWeight: 500 }}>{ev.recommended_channel || '—'}</span></div>
            <div><span style={{ color: '#5e6c84' }}>Status:</span> <span style={{ fontWeight: 500 }}>{ev.status}</span></div>
            <div><span style={{ color: '#5e6c84' }}>Probability:</span> <span style={{ fontWeight: 500 }}>{Math.round((ev.recovery_probability || 0) * 100)}%</span></div>
            <div style={{ gridColumn: '1 / -1' }}><span style={{ color: '#5e6c84' }}>Customer:</span> <span style={{ fontWeight: 500 }}>{ev.customer_name || '—'}</span></div>
            <div><span style={{ color: '#5e6c84' }}>Email:</span> <span style={{ fontWeight: 500, fontSize: 12 }}>{ev.customer_email || '—'}</span></div>
            <div><span style={{ color: '#5e6c84' }}>Phone:</span> <span style={{ fontWeight: 500, fontSize: 12 }}>{ev.customer_phone || '—'}</span></div>
          </div>
          {ev.reasoning && (
            <div style={{ marginTop: 10, padding: '10px 12px', background: '#f4f5f7', borderRadius: 4, fontSize: 13, color: '#5e6c84', lineHeight: 1.5 }}>
              <span style={{ fontWeight: 500, color: '#172b4d' }}>AI Reasoning: </span>{ev.reasoning}
            </div>
          )}
        </div>

        <div style={{ fontSize: 11, fontWeight: 700, color: '#5e6c84', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: 10 }}>
          Pipeline Steps ({attempts.length} attempt{attempts.length !== 1 ? 's' : ''})
        </div>

        {attempts.length === 0 ? (
          <div style={{ fontSize: 13, color: '#5e6c84', fontStyle: 'italic' }}>No attempts recorded yet</div>
        ) : (
          attempts.map((att) => {
            const meta = att.metadata || {}
            const path = meta.degradation_path || []
            return (
              <div key={att.id} style={{
                background: '#f4f5f7', borderRadius: 4, padding: 16, marginBottom: 12,
                border: '1px solid #ebecf0',
              }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                  <span style={{ fontSize: 13, fontWeight: 600, color: '#172b4d' }}>Attempt #{att.attempt_number}</span>
                  <OutcomeBadge outcome={att.outcome} />
                </div>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '4px 12px', fontSize: 12, color: '#5e6c84', marginBottom: 8 }}>
                  <div>Channel: <span style={{ fontWeight: 500, color: '#172b4d' }}>{att.channel_used}</span></div>
                  <div>Time: <span style={{ fontWeight: 500, color: '#172b4d' }}>{timeAgo(att.created_at)}</span></div>
                  {att.message_id && <div style={{ gridColumn: '1 / -1' }}>Msg ID: <span style={{ fontFamily: 'monospace', fontSize: 11 }}>{att.message_id}</span></div>}
                  {meta.degraded_from && <div style={{ gridColumn: '1 / -1' }}>Degraded from: <span style={{ fontWeight: 500, color: '#F79009' }}>{meta.degraded_from}</span></div>}
                  {meta.send_error && <div style={{ gridColumn: '1 / -1', color: '#B42318' }}>Error: {meta.send_error}</div>}
                  {meta.payment_link_url && <div style={{ gridColumn: '1 / -1' }}>Payment link: <span style={{ fontFamily: 'monospace', fontSize: 11 }}>{meta.payment_link_url}</span></div>}
                </div>
                {path.length > 0 && (
                  <div style={{ marginTop: 8 }}>
                    <div style={{ fontSize: 11, fontWeight: 600, color: '#5e6c84', marginBottom: 4 }}>Provider Chain</div>
                    {path.map((step, j) => <ProviderStep key={j} step={step} />)}
                  </div>
                )}
                {att.notes && <div style={{ marginTop: 8, fontSize: 12, color: '#5e6c84', fontStyle: 'italic' }}>{att.notes}</div>}
              </div>
            )
          })
        )}

        <div style={{ fontSize: 11, fontWeight: 700, color: '#5e6c84', textTransform: 'uppercase', letterSpacing: '0.05em', marginTop: 16, marginBottom: 10 }}>
          Timeline
        </div>
        <div style={{ fontSize: 12, color: '#5e6c84', display: 'flex', flexDirection: 'column', gap: 6 }}>
          <div>Created: <span style={{ color: '#172b4d' }}>{new Date(ev.created_at).toLocaleString()}</span></div>
          {ev.last_attempt_at && <div>Last attempt: <span style={{ color: '#172b4d' }}>{new Date(ev.last_attempt_at).toLocaleString()}</span></div>}
          {ev.next_action_at && <div>Next action: <span style={{ color: '#172b4d' }}>{new Date(ev.next_action_at).toLocaleString()}</span></div>}
          {ev.recovery_window_ends && <div>Window closes: <span style={{ color: '#172b4d' }}>{new Date(ev.recovery_window_ends).toLocaleString()}</span></div>}
          {ev.recovered_at && <div>Recovered: <span style={{ color: '#04db7c', fontWeight: 500 }}>{new Date(ev.recovered_at).toLocaleString()}</span></div>}
        </div>
      </div>
    </div>
  )
}

const AUDIT_PAGE_SIZE = 30

const PgBtn = ({ label, active, disabled, onClick }) => (
  <button onClick={onClick} disabled={disabled} style={{
    padding: '6px 12px', fontSize: 13, fontWeight: active ? 600 : 400,
    background: active ? '#0D94FB' : '#fff', color: active ? '#fff' : disabled ? '#D0D5DD' : '#172b4d',
    border: `1px solid ${active ? '#0D94FB' : '#ebecf0'}`, borderRadius: 4,
    cursor: disabled ? 'default' : 'pointer', fontFamily: 'inherit',
  }}>
    {label}
  </button>
)

export default function AuditLogsPage({ dateRange }) {
  const [logs, setLogs] = useState([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(true)
  const [filterEventId, setFilterEventId] = useState('')
  const [filterChannel, setFilterChannel] = useState('')
  const [filterOutcome, setFilterOutcome] = useState('')
  const [traceEventId, setTraceEventId] = useState(null)
  const [page, setPage] = useState(0)

  const load = useCallback(async () => {
    if (logs.length === 0) setLoading(true)
    try {
      const dp = getDateParams(dateRange || {})
      const params = { limit: AUDIT_PAGE_SIZE, offset: page * AUDIT_PAGE_SIZE, ...dp }
      if (filterEventId) params.event_id = filterEventId
      const data = await fetchAuditLogs(params)
      setLogs(data.logs || [])
      setTotal(data.total || 0)
    } catch (e) {
      console.error('Failed to load audit logs:', e)
    } finally {
      setLoading(false)
    }
  }, [filterEventId, page, dateRange, logs.length])

  useEffect(() => { load() }, [load])
  useEffect(() => {
    const interval = setInterval(load, 15000)
    return () => clearInterval(interval)
  }, [load])
  useEffect(() => { setPage(0) }, [filterEventId, dateRange])

  const filteredLogs = logs.filter(log => {
    if (filterChannel && log.channel_used !== filterChannel) return false
    if (filterOutcome && log.outcome !== filterOutcome) return false
    return true
  })

  const totalPages = Math.max(1, Math.ceil(total / AUDIT_PAGE_SIZE))
  const startItem = page * AUDIT_PAGE_SIZE + 1
  const endItem = Math.min((page + 1) * AUDIT_PAGE_SIZE, total)

  return (
    <div style={{ padding: '28px 32px' }}>
      <div style={{ marginBottom: 20 }}>
        <h1 style={{ fontSize: 18, fontWeight: 700, color: '#172b4d', margin: '0 0 6px' }}>Audit Logs</h1>
        <p style={{ fontSize: 14, color: '#5e6c84', margin: 0 }}>
          Every recovery attempt with full provider chain, degradation paths, and error traces.
        </p>
      </div>

      <div style={{ display: 'flex', gap: 10, marginBottom: 20, alignItems: 'center', flexWrap: 'wrap' }}>
        <input
          type="text"
          placeholder="Filter by Event ID..."
          value={filterEventId}
          onChange={e => setFilterEventId(e.target.value.replace(/\D/g, ''))}
          style={{
            padding: '8px 14px', border: '1px solid #ebecf0', borderRadius: 4,
            fontSize: 14, width: 180, outline: 'none', fontFamily: 'inherit',
          }}
          onFocus={e => e.target.style.borderColor = '#0D94FB'}
          onBlur={e => e.target.style.borderColor = '#ebecf0'}
        />
        <select value={filterChannel} onChange={e => setFilterChannel(e.target.value)} style={{
          padding: '8px 12px', border: '1px solid #ebecf0', borderRadius: 4,
          fontSize: 13, fontFamily: 'inherit', color: '#172b4d', background: '#fff',
        }}>
          <option value="">All Channels</option>
          <option value="whatsapp">WhatsApp</option>
          <option value="sms">SMS</option>
          <option value="email">Email</option>
        </select>
        <select value={filterOutcome} onChange={e => setFilterOutcome(e.target.value)} style={{
          padding: '8px 12px', border: '1px solid #ebecf0', borderRadius: 4,
          fontSize: 13, fontFamily: 'inherit', color: '#172b4d', background: '#fff',
        }}>
          <option value="">All Outcomes</option>
          <option value="sent">Sent</option>
          <option value="delivered">Delivered</option>
          <option value="failed">Failed</option>
          <option value="blocked">Blocked</option>
          <option value="give_up">Give Up</option>
        </select>
        <button onClick={load} style={{
          padding: '8px 16px', background: '#0D94FB', color: '#fff',
          border: 'none', borderRadius: 4, fontSize: 13, fontWeight: 500,
          cursor: 'pointer', fontFamily: 'inherit',
        }}>
          Refresh
        </button>
        <span style={{ fontSize: 13, color: '#5e6c84' }}>
          {total} log{total !== 1 ? 's' : ''} {filterEventId && `for event #${filterEventId}`}
        </span>
        <span style={{
          marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 6,
          fontSize: 12, color: '#5e6c84',
        }}>
          <span style={{ width: 6, height: 6, borderRadius: '50%', background: '#04db7c', animation: 'pulse 2s infinite' }} />
          Auto-refresh 15s
        </span>
      </div>

      <div style={{ background: '#fff', border: '1px solid #ebecf0', borderRadius: 4, overflow: 'hidden' }}>
        <div style={{ overflowX: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', minWidth: 900 }}>
            <thead>
              <tr>
                {['ID', 'Event', 'Attempt', 'Channel', 'Outcome', 'Provider Chain', 'Error', 'Message ID', 'Time'].map(h => (
                  <th key={h} style={{
                    padding: '10px 14px', fontSize: 11, fontWeight: 600,
                    color: '#5e6c84', textAlign: 'left',
                    textTransform: 'uppercase', letterSpacing: '0.04em',
                    borderBottom: '2px solid #ebecf0', whiteSpace: 'nowrap',
                    background: '#f4f5f7',
                  }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr><td colSpan={9} style={{ padding: 40, textAlign: 'center', color: '#5e6c84' }}>Loading...</td></tr>
              ) : filteredLogs.length === 0 ? (
                <tr><td colSpan={9} style={{ padding: 40, textAlign: 'center', color: '#5e6c84' }}>
                  No audit logs found{filterEventId && ` for event #${filterEventId}`}
                </td></tr>
              ) : (
                filteredLogs.map(log => {
                  const meta = log.metadata || {}
                  const path = meta.degradation_path || []
                  const providers = path.map(p => p.provider).join(' → ')
                  const errorMsg = meta.send_error || ''
                  return (
                    <tr key={log.id} onClick={() => setTraceEventId(log.recovery_event_id)}
                      style={{ borderBottom: '1px solid #ebecf0', cursor: 'pointer' }}
                      onMouseEnter={e => e.currentTarget.style.background = '#f4f5f7'}
                      onMouseLeave={e => e.currentTarget.style.background = 'transparent'}
                    >
                      <td style={{ padding: '10px 14px', fontSize: 12, fontFamily: 'monospace', color: '#5e6c84' }}>{log.id}</td>
                      <td style={{ padding: '10px 14px', fontSize: 13, fontWeight: 500 }}>
                        <span style={{ color: '#0D94FB', cursor: 'pointer' }}>#{log.recovery_event_id}</span>
                      </td>
                      <td style={{ padding: '10px 14px', fontSize: 13, textAlign: 'center' }}>{log.attempt_number}</td>
                      <td style={{ padding: '10px 14px', fontSize: 13, textTransform: 'capitalize' }}>
                        {log.channel_used}
                        {meta.degraded_from && <span style={{ fontSize: 11, color: '#F79009', display: 'block' }}>from {meta.degraded_from}</span>}
                      </td>
                      <td style={{ padding: '10px 14px' }}><OutcomeBadge outcome={log.outcome} /></td>
                      <td style={{ padding: '10px 14px', fontSize: 12, color: '#5e6c84', maxWidth: 200, overflow: 'hidden', textOverflow: 'ellipsis' }}>{providers || '—'}</td>
                      <td style={{
                        padding: '10px 14px', fontSize: 12, maxWidth: 220,
                        overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                        color: errorMsg ? '#B42318' : '#5e6c84',
                      }} title={errorMsg}>{errorMsg || '—'}</td>
                      <td style={{ padding: '10px 14px', fontSize: 11, fontFamily: 'monospace', color: '#5e6c84', maxWidth: 120, overflow: 'hidden', textOverflow: 'ellipsis' }}
                        title={log.message_id || ''}>{log.message_id ? log.message_id.substring(0, 16) + '...' : '—'}</td>
                      <td style={{ padding: '10px 14px', fontSize: 12, color: '#5e6c84', whiteSpace: 'nowrap' }}>{timeAgo(log.created_at)}</td>
                    </tr>
                  )
                })
              )}
            </tbody>
          </table>
        </div>
      </div>

      {total > AUDIT_PAGE_SIZE && (
        <div style={{
          display: 'flex', justifyContent: 'space-between', alignItems: 'center',
          padding: '12px 16px', borderTop: '1px solid #ebecf0', background: '#f4f5f7',
          borderRadius: '0 0 4px 4px', marginTop: -1,
        }}>
          <span style={{ fontSize: 13, color: '#5e6c84' }}>Showing {startItem}–{endItem} of {total}</span>
          <div style={{ display: 'flex', gap: 4 }}>
            <PgBtn label="First" disabled={page === 0} onClick={() => setPage(0)} />
            <PgBtn label="Prev" disabled={page === 0} onClick={() => setPage(p => p - 1)} />
            {Array.from({ length: Math.min(5, totalPages) }, (_, i) => {
              let p
              if (totalPages <= 5) p = i
              else if (page < 3) p = i
              else if (page > totalPages - 4) p = totalPages - 5 + i
              else p = page - 2 + i
              return <PgBtn key={p} label={String(p + 1)} active={p === page} onClick={() => setPage(p)} />
            })}
            <PgBtn label="Next" disabled={page >= totalPages - 1} onClick={() => setPage(p => p + 1)} />
            <PgBtn label="Last" disabled={page >= totalPages - 1} onClick={() => setPage(totalPages - 1)} />
          </div>
        </div>
      )}

      {traceEventId && (
        <>
          <div onClick={() => setTraceEventId(null)} style={{
            position: 'fixed', top: 0, left: 0, right: 0, bottom: 0,
            background: 'rgba(0,0,0,0.3)', zIndex: 99,
          }} />
          <TracePanel eventId={traceEventId} onClose={() => setTraceEventId(null)} />
        </>
      )}
    </div>
  )
}
