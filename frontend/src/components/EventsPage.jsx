import { useState, useEffect, useCallback, useRef } from 'react'
import { fetchEvents, fetchEventTrace, fetchEventCounts, controlEvent } from '../lib/api'
import { TypeBadge, StatusBadge, timeAgo, formatCategory, formatEscalation, formatStrategy } from './OverviewPage'
import { getDateParams } from './DateRangePicker'

const fmt = (n) => new Intl.NumberFormat('en-IN', { maximumFractionDigits: 0 }).format(n)
const PAGE_SIZE = 25

const TABS = [
  { id: null, label: 'All Events' },
  { id: 'pending', label: 'In Progress' },
  { id: 'paused', label: 'On Hold' },
  { id: 'recovered', label: 'Paid' },
  { id: 'exhausted', label: 'Gave Up' },
  { id: 'cancelled', label: 'Cancelled' },
  { id: 'no_action_needed', label: 'Skipped' },
]

function timeUntil(dateStr) {
  if (!dateStr) return null
  const diff = new Date(dateStr) - Date.now()
  if (diff <= 0) return 'due now'
  const mins = Math.floor(diff / 60000)
  if (mins < 60) return `in ${mins}m`
  const hrs = Math.floor(mins / 60)
  const remainMins = mins % 60
  return remainMins > 0 ? `in ${hrs}h ${remainMins}m` : `in ${hrs}h`
}

export default function EventsPage({ selectedEventId, dateRange }) {
  const [activeTab, setActiveTab] = useState(null)
  const [detailId, setDetailId] = useState(selectedEventId || null)
  const [events, setEvents] = useState([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(0)
  const [initialLoading, setInitialLoading] = useState(true)
  const [tabCounts, setTabCounts] = useState({})
  const hasLoaded = useRef(false)

  const load = useCallback(async (silent = false) => {
    if (!silent && !hasLoaded.current) setInitialLoading(true)
    try {
      const dp = getDateParams(dateRange || {})
      const params = { limit: PAGE_SIZE, offset: page * PAGE_SIZE, ...dp }
      if (activeTab) params.status = activeTab
      const data = await fetchEvents(params)
      setEvents(data.events || [])
      setTotal(data.total || 0)
      hasLoaded.current = true
    } catch (e) {
      console.error('Failed to load events:', e)
    } finally {
      setInitialLoading(false)
    }
  }, [activeTab, page, dateRange])

  const loadCounts = useCallback(async () => {
    try {
      const dp = getDateParams(dateRange || {})
      const counts = await fetchEventCounts(dp)
      setTabCounts({
        all: counts.all || 0,
        pending: counts.pending || 0,
        paused: counts.paused || 0,
        recovered: counts.recovered || 0,
        exhausted: counts.exhausted || 0,
        cancelled: counts.cancelled || 0,
        no_action_needed: counts.no_action_needed || 0,
      })
    } catch (e) {
      console.error('Failed to load counts:', e)
    }
  }, [dateRange])

  useEffect(() => { setPage(0) }, [dateRange])
  useEffect(() => { load() }, [load])
  useEffect(() => { loadCounts() }, [loadCounts])

  useEffect(() => {
    const interval = setInterval(() => { load(true); loadCounts() }, 30000)
    return () => clearInterval(interval)
  }, [load, loadCounts])

  const totalPages = Math.ceil(total / PAGE_SIZE)

  const switchTab = (tabId) => {
    setActiveTab(tabId)
    setPage(0)
    hasLoaded.current = false
  }

  const detail = detailId ? events.find(e => e.id === detailId) : null

  return (
    <div style={{ display: 'flex', height: 'calc(100vh - 56px)' }}>
      <div style={{ flex: 1, minWidth: 0, overflow: 'auto' }}>
        <div style={{ padding: '28px 32px 0' }}>
          <h1 style={{ fontSize: 18, fontWeight: 600, color: '#1A1A1A', margin: '0 0 20px' }}>
            Recovery Events
          </h1>
        </div>

        <div style={{
          display: 'flex', gap: 0, padding: '0 32px',
          borderBottom: '1px solid #E8EAED',
          overflowX: 'auto',
        }}>
          {TABS.map(tab => {
            const count = tab.id ? (tabCounts[tab.id] ?? '—') : (tabCounts.all ?? '—')
            return (
              <button
                key={tab.id || 'all'}
                onClick={() => switchTab(tab.id)}
                style={{
                  padding: '12px 18px',
                  fontSize: 14,
                  fontWeight: activeTab === tab.id ? 600 : 400,
                  color: activeTab === tab.id ? '#528FF0' : '#6B7280',
                  background: 'none',
                  border: 'none',
                  borderBottom: activeTab === tab.id ? '2px solid #528FF0' : '2px solid transparent',
                  cursor: 'pointer',
                  marginBottom: -1,
                  fontFamily: 'inherit',
                  whiteSpace: 'nowrap',
                  flexShrink: 0,
                }}
              >
                {tab.label}
                <span style={{
                  marginLeft: 8, fontSize: 12, padding: '2px 8px',
                  borderRadius: 8, background: '#F2F4F7',
                  color: '#6B7280', fontWeight: 500,
                }}>
                  {count}
                </span>
              </button>
            )
          })}
        </div>

        <div style={{ background: '#fff', margin: '16px 32px', border: '1px solid #E8EAED', borderRadius: 8, overflow: 'hidden' }}>
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', minWidth: 780 }}>
              <thead>
                <tr style={{ borderBottom: '1px solid #E8EAED' }}>
                  {['ID', 'Type', 'Amount', 'Category', 'Channel', 'Messages', 'Status', 'Next / Created'].map(h => (
                    <th key={h} style={{
                      padding: '12px 16px', fontSize: 12, fontWeight: 600,
                      color: '#6B7280', textAlign: 'left',
                      textTransform: 'uppercase', letterSpacing: '0.04em',
                      whiteSpace: 'nowrap',
                    }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {initialLoading ? (
                  <tr>
                    <td colSpan={8} style={{ padding: '48px 20px', textAlign: 'center', fontSize: 14, color: '#6B7280' }}>
                      Loading...
                    </td>
                  </tr>
                ) : events.length === 0 ? (
                  <tr>
                    <td colSpan={8} style={{ padding: '48px 20px', textAlign: 'center', fontSize: 14, color: '#6B7280' }}>
                      No events match this filter.
                    </td>
                  </tr>
                ) : (
                  events.map(e => (
                    <tr
                      key={e.id}
                      onClick={() => setDetailId(e.id)}
                      style={{
                        borderBottom: '1px solid #E8EAED',
                        cursor: 'pointer',
                        background: detailId === e.id ? '#F0F4FF' : 'transparent',
                      }}
                      onMouseEnter={ev => { if (detailId !== e.id) ev.currentTarget.style.background = '#F7F8F9' }}
                      onMouseLeave={ev => { if (detailId !== e.id) ev.currentTarget.style.background = 'transparent' }}
                    >
                      <td style={{ padding: '12px 16px', fontSize: 13, color: '#6B7280', fontFamily: 'monospace', whiteSpace: 'nowrap' }}>#{e.id}</td>
                      <td style={{ padding: '12px 16px', whiteSpace: 'nowrap' }}><TypeBadge type={e.event_type} /></td>
                      <td style={{ padding: '12px 16px', fontSize: 14, fontWeight: 500, whiteSpace: 'nowrap' }}>₹{fmt(e.amount)}</td>
                      <td style={{ padding: '12px 16px', fontSize: 14, color: '#5F6B7A', whiteSpace: 'nowrap' }}>{formatCategory(e.failure_category)}</td>
                      <td style={{ padding: '12px 16px', fontSize: 14, color: '#5F6B7A', textTransform: 'capitalize', whiteSpace: 'nowrap' }}>{e.recommended_channel || '—'}</td>
                      <td style={{ padding: '12px 16px', fontSize: 14, color: '#5F6B7A', whiteSpace: 'nowrap' }}>{e.attempt_count || 0}/{e.max_attempts ?? 5}</td>
                      <td style={{ padding: '12px 16px', whiteSpace: 'nowrap' }}><StatusBadge status={e.status} /></td>
                      <td style={{ padding: '12px 16px', whiteSpace: 'nowrap' }}>
                        {e.status === 'pending' && e.next_action_at ? (
                          <span style={{ fontSize: 13, color: '#528FF0', fontWeight: 500 }}>
                            {timeUntil(e.next_action_at)}
                          </span>
                        ) : (
                          <span style={{ fontSize: 13, color: '#6B7280' }}>{timeAgo(e.created_at)}</span>
                        )}
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>

          {totalPages > 1 && (
            <div style={{
              display: 'flex', alignItems: 'center', justifyContent: 'space-between',
              padding: '12px 16px', borderTop: '1px solid #E8EAED', fontSize: 13,
            }}>
              <span style={{ color: '#6B7280' }}>
                Showing {page * PAGE_SIZE + 1}–{Math.min((page + 1) * PAGE_SIZE, total)} of {total}
              </span>
              <div style={{ display: 'flex', gap: 4 }}>
                <PaginationBtn onClick={() => setPage(0)} disabled={page === 0}>First</PaginationBtn>
                <PaginationBtn onClick={() => setPage(p => p - 1)} disabled={page === 0}>Prev</PaginationBtn>
                {Array.from({ length: Math.min(5, totalPages) }, (_, i) => {
                  let p
                  if (totalPages <= 5) p = i
                  else if (page < 3) p = i
                  else if (page > totalPages - 4) p = totalPages - 5 + i
                  else p = page - 2 + i
                  return (
                    <PaginationBtn key={p} onClick={() => setPage(p)} active={page === p}>
                      {p + 1}
                    </PaginationBtn>
                  )
                })}
                <PaginationBtn onClick={() => setPage(p => p + 1)} disabled={page >= totalPages - 1}>Next</PaginationBtn>
                <PaginationBtn onClick={() => setPage(totalPages - 1)} disabled={page >= totalPages - 1}>Last</PaginationBtn>
              </div>
            </div>
          )}
        </div>
      </div>

      {detail && <EventDetailPanel event={detail} onClose={() => setDetailId(null)} onUpdate={() => { load(); loadCounts() }} />}
    </div>
  )
}

function PaginationBtn({ onClick, disabled, active, children }) {
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      style={{
        padding: '6px 12px', fontSize: 13, fontWeight: active ? 600 : 400,
        color: disabled ? '#D0D5DD' : active ? '#fff' : '#344054',
        background: active ? '#528FF0' : 'transparent',
        border: '1px solid ' + (active ? '#528FF0' : '#E8EAED'),
        borderRadius: 6, cursor: disabled ? 'default' : 'pointer',
        fontFamily: 'inherit',
      }}
    >
      {children}
    </button>
  )
}

function EventDetailPanel({ event, onClose, onUpdate }) {
  const e = event
  const [attempts, setAttempts] = useState([])
  const [loadingTrace, setLoadingTrace] = useState(false)
  const [controlling, setControlling] = useState(false)

  useEffect(() => {
    let cancelled = false
    setLoadingTrace(true)
    fetchEventTrace(e.id).then(data => {
      if (!cancelled) setAttempts(data.attempts || [])
    }).catch(() => {}).finally(() => {
      if (!cancelled) setLoadingTrace(false)
    })
    return () => { cancelled = true }
  }, [e.id])

  const nextAction = e.status === 'pending' ? timeUntil(e.next_action_at) : null

  const handleControl = async (action) => {
    setControlling(true)
    try {
      await controlEvent(e.id, action)
      onUpdate?.()
    } catch (err) {
      console.error('Control failed:', err)
    } finally {
      setControlling(false)
    }
  }

  return (
    <div style={{
      width: 420, borderLeft: '1px solid #E8EAED',
      background: '#fff', overflow: 'auto',
      height: 'calc(100vh - 56px)',
    }}>
      <div style={{
        padding: '18px 24px', borderBottom: '1px solid #E8EAED',
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <span style={{ fontSize: 16, fontWeight: 600, color: '#1A1A1A' }}>Event #{e.id}</span>
          <StatusBadge status={e.status} />
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          {e.status === 'pending' && (
            <button
              onClick={() => handleControl('pause')}
              disabled={controlling}
              style={{
                padding: '5px 12px', fontSize: 12, fontWeight: 500,
                color: '#B54708', background: '#FFFAEB', border: '1px solid #FEC84B',
                borderRadius: 6, cursor: controlling ? 'not-allowed' : 'pointer',
                fontFamily: 'inherit',
              }}
            >
              {controlling ? '...' : 'Pause'}
            </button>
          )}
          {e.status === 'paused' && (
            <button
              onClick={() => handleControl('resume')}
              disabled={controlling}
              style={{
                padding: '5px 12px', fontSize: 12, fontWeight: 500,
                color: '#027A48', background: '#ECFDF3', border: '1px solid #6CE9A6',
                borderRadius: 6, cursor: controlling ? 'not-allowed' : 'pointer',
                fontFamily: 'inherit',
              }}
            >
              {controlling ? '...' : 'Resume'}
            </button>
          )}
          {(e.status === 'pending' || e.status === 'paused' || e.status === 'exhausted') && (
            <button
              onClick={() => { if (window.confirm('Cancel recovery for this event? This cannot be undone.')) handleControl('cancel') }}
              disabled={controlling}
              style={{
                padding: '5px 12px', fontSize: 12, fontWeight: 500,
                color: '#B42318', background: '#FEF3F2', border: '1px solid #FECDCA',
                borderRadius: 6, cursor: controlling ? 'not-allowed' : 'pointer',
                fontFamily: 'inherit',
              }}
            >
              {controlling ? '...' : 'Cancel'}
            </button>
          )}
          <button onClick={onClose} style={{ background: 'none', border: 'none', cursor: 'pointer', padding: 4, color: '#6B7280' }}>
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
          </button>
        </div>
      </div>

      <div style={{ padding: '20px 24px' }}>
        <div style={{ fontSize: 32, fontWeight: 700, color: '#1A1A1A', marginBottom: 4 }}>
          ₹{fmt(e.amount)} <span style={{ fontSize: 14, fontWeight: 400, color: '#6B7280' }}>{e.currency}</span>
        </div>

        {nextAction && (
          <div style={{
            display: 'inline-flex', alignItems: 'center', gap: 6,
            padding: '4px 10px', background: '#EFF6FF', borderRadius: 6,
            fontSize: 13, color: '#1D4ED8', fontWeight: 500, marginBottom: 16,
          }}>
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/>
            </svg>
            Next attempt {nextAction}
          </div>
        )}

        {e.status === 'paused' && (
          <div style={{
            padding: '10px 14px', background: '#F0F4FF', borderRadius: 8,
            fontSize: 13, color: '#3538CD', lineHeight: 1.5, marginBottom: 16,
          }}>
            <strong>On Hold:</strong> Recovery is paused. Click Resume to continue.
          </div>
        )}

        {e.status === 'exhausted' && (
          <div style={{
            padding: '10px 14px', background: '#FEF3F2', borderRadius: 8,
            fontSize: 13, color: '#B42318', lineHeight: 1.5, marginBottom: 16,
          }}>
            <strong>Recovery Stopped:</strong> {e.skip_reason || 'All recovery attempts completed without successful payment'}
          </div>
        )}

        {e.status === 'cancelled' && (
          <div style={{
            padding: '10px 14px', background: '#F9FAFB', borderRadius: 8,
            fontSize: 13, color: '#344054', lineHeight: 1.5, marginBottom: 16,
          }}>
            <strong>Cancelled:</strong> {e.skip_reason || 'Recovery was cancelled'}
          </div>
        )}

        {e.fallback_classification && (
          <div style={{
            display: 'inline-flex', alignItems: 'center', gap: 6,
            padding: '4px 10px', background: '#FFFAEB', borderRadius: 6,
            fontSize: 12, color: '#B54708', fontWeight: 500, marginBottom: 12,
          }}>
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z"/>
              <line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/>
            </svg>
            Auto-classified (rules)
          </div>
        )}

        <div style={{ marginBottom: 20, marginTop: nextAction || e.status === 'exhausted' ? 0 : 16 }}>
          <SectionLabel>Recovery Pipeline</SectionLabel>
          <PipelineStage number={1} label="Classified" done detail={`${formatCategory(e.failure_category)} · ${Math.round((e.recovery_probability || 0) * 100)}% chance`} />
          <PipelineStage number={2} label="Routed" done={!!e.recommended_channel} detail={
            e.status === 'no_action_needed' ? 'no recovery needed — skipped' :
            e.recommended_channel === 'none' ? 'no channel — skipped' :
            e.recommended_channel ? `${e.recommended_channel} · ${e.recommended_timing === 'immediate' ? 'send now' : (e.recommended_timing || 'immediate').replace(/_/g, ' ')}` :
            'waiting'
          } />
          <PipelineStage number={3} label="Message Sent" done={e.attempt_count > 0 || e.status === 'no_action_needed' || e.status === 'cancelled'} detail={
            e.status === 'no_action_needed' ? 'skipped — not worth pursuing' :
            e.status === 'cancelled' ? 'cancelled before completion' :
            e.attempt_count > 0 ? `${e.attempt_count}/${e.max_attempts ?? 5} messages sent` :
            e.next_action_at && new Date(e.next_action_at) > new Date() ? `scheduled ${timeUntil(e.next_action_at)}` :
            'waiting'
          } />
          <PipelineStage number={4} label="Result" done={e.status === 'recovered' || e.status === 'exhausted' || e.status === 'no_action_needed' || e.status === 'cancelled'} detail={
            e.status === 'recovered' ? `Paid ₹${fmt(e.recovered_amount || e.amount)}` :
            e.status === 'exhausted' ? 'Gave up' :
            e.status === 'no_action_needed' ? 'Skipped' :
            e.status === 'cancelled' ? 'Cancelled' :
            'waiting for payment'
          } last />
        </div>

        {attempts.length > 0 && (
          <>
            <SectionLabel>Attempt History</SectionLabel>
            <div style={{ fontSize: 11, color: '#9CA3AF', marginBottom: 8, marginTop: -4 }}>
              Only successfully sent messages count toward the {e.max_attempts ?? 5}-message limit. Blocked, failed, and customer payment attempts do not.
            </div>
            <div style={{ marginBottom: 16 }}>
              {(() => { let outreachNum = 0; return attempts.map((a, i) => {
                const isCustomerAttempt = a.channel_used === 'payment_link'
                const isBlocked = a.outcome === 'blocked'
                if (!isCustomerAttempt) outreachNum++
                return (
                  <div key={a.id || i} style={{
                    padding: '10px 12px', marginBottom: 6,
                    background: isCustomerAttempt ? '#F0F9FF' : '#F9FAFB',
                    borderRadius: 8,
                    border: `1px solid ${isCustomerAttempt ? '#BAE6FD' : '#E8EAED'}`,
                  }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4 }}>
                      <span style={{ fontSize: 13, fontWeight: 600, color: '#1A1A1A' }}>
                        {isCustomerAttempt ? (
                          <>
                            <span style={{ fontSize: 11, fontWeight: 500, color: '#0369A1', background: '#E0F2FE', padding: '1px 6px', borderRadius: 4, marginRight: 6 }}>Customer</span>
                            {a.metadata?.method || 'payment'}
                          </>
                        ) : (
                          <>#{outreachNum} · {a.channel_used}</>
                        )}
                      </span>
                      <span style={{
                        fontSize: 11, fontWeight: 500, padding: '2px 8px', borderRadius: 10,
                        background: a.outcome === 'sent' ? '#ECFDF3' : isBlocked ? '#FFFAEB' : '#FEF3F2',
                        color: a.outcome === 'sent' ? '#027A48' : isBlocked ? '#B54708' : '#B42318',
                      }}>
                        {isBlocked ? 'cooldown' : a.outcome}
                      </span>
                    </div>
                    <div style={{ fontSize: 12, color: '#6B7280' }}>
                      {a.action_taken}
                    </div>
                    {a.metadata?.degraded_from && (
                      <div style={{ fontSize: 12, color: '#B54708', marginTop: 2 }}>
                        Degraded from {a.metadata.degraded_from}
                      </div>
                    )}
                    {!isCustomerAttempt && a.metadata?.payment_link_url && (
                      <div style={{ fontSize: 12, color: '#528FF0', marginTop: 2, wordBreak: 'break-all' }}>
                        Link: {a.metadata.payment_link_url}
                      </div>
                    )}
                    <div style={{ fontSize: 11, color: '#9CA3AF', marginTop: 4 }}>
                      {a.created_at ? new Date(a.created_at).toLocaleString() : ''}
                    </div>
                  </div>
                )
              }) })()}
            </div>
          </>
        )}
        {loadingTrace && (
          <div style={{ fontSize: 13, color: '#6B7280', marginBottom: 16 }}>Loading attempts...</div>
        )}

        <SectionLabel>Event Details</SectionLabel>
        <DetailRow label="Type"><TypeBadge type={e.event_type} /></DetailRow>
        <DetailRow label="Method">{e.method || '—'}</DetailRow>
        <DetailRow label="Error Code"><span style={{ fontFamily: 'monospace', fontSize: 12 }}>{e.error_code || '—'}</span></DetailRow>
        <DetailRow label="Error">{e.error_description || '—'}</DetailRow>
        <DetailRow label="Payment ID"><span style={{ fontFamily: 'monospace', fontSize: 12 }}>{e.payment_id || '—'}</span></DetailRow>
        <DetailRow label="Order ID"><span style={{ fontFamily: 'monospace', fontSize: 12 }}>{e.order_id || '—'}</span></DetailRow>

        <div style={{ height: 14 }} />
        <SectionLabel>Customer</SectionLabel>
        <DetailRow label="Name">{e.customer_name || '—'}</DetailRow>
        <DetailRow label="Email">{e.customer_email || '—'}</DetailRow>
        <DetailRow label="Phone">{e.customer_phone || '—'}</DetailRow>

        <div style={{ height: 14 }} />
        <SectionLabel>AI Classification</SectionLabel>
        <DetailRow label="Category">{formatCategory(e.failure_category)}</DetailRow>
        <DetailRow label="Recovery Chance">{Math.round((e.recovery_probability || 0) * 100)}%</DetailRow>
        <DetailRow label="Channel">{e.status === 'no_action_needed' ? 'None (skipped)' : e.recommended_channel === 'none' ? 'None (skipped)' : (e.recommended_channel || '—')}</DetailRow>
        <DetailRow label="Messages Sent / Limit">{e.attempt_count || 0} / {e.max_attempts ?? 5}</DetailRow>
        <DetailRow label="Recommended Action">{e.recommended_action || '—'}</DetailRow>
        {e.reasoning && (
          <div style={{ margin: '8px 0', padding: 14, background: '#F7F8FA', borderRadius: 8, fontSize: 13, color: '#5F6B7A', lineHeight: 1.6 }}>
            <strong style={{ color: '#1A1A1A' }}>Why:</strong> {e.reasoning}
          </div>
        )}
        {e.alternative_action && e.status !== 'no_action_needed' && (
          <div style={{ margin: '8px 0', padding: 14, background: '#F0F9FF', borderRadius: 8, fontSize: 13, color: '#0369A1', lineHeight: 1.6 }}>
            <strong style={{ color: '#0C4A6E' }}>Backup Plan:</strong> {e.alternative_action}
          </div>
        )}
        {e.status !== 'exhausted' && e.skip_reason && (
          <div style={{ margin: '8px 0', padding: 14, background: '#FFFAEB', borderRadius: 8, fontSize: 13, color: '#B54708' }}>
            <strong>Reason skipped:</strong> {e.skip_reason}
          </div>
        )}

        <div style={{ height: 14 }} />
        <SectionLabel>Timeline</SectionLabel>
        <DetailRow label="Created">{e.created_at ? new Date(e.created_at).toLocaleString() : '—'}</DetailRow>
        <DetailRow label="Last Message">{e.last_attempt_at ? new Date(e.last_attempt_at).toLocaleString() : '—'}</DetailRow>
        {e.status === 'pending' && e.next_action_at && (
          <DetailRow label="Next Message">
            <span style={{ color: '#1D4ED8', fontWeight: 500 }}>
              {new Date(e.next_action_at).toLocaleString()} ({timeUntil(e.next_action_at)})
            </span>
          </DetailRow>
        )}
        <DetailRow label="Stop Trying After">{e.status === 'no_action_needed' ? '—' : e.recovery_window_ends ? new Date(e.recovery_window_ends).toLocaleString() : '—'}</DetailRow>
        {e.recovered_at && <DetailRow label="Paid At">{new Date(e.recovered_at).toLocaleString()}</DetailRow>}
        <DetailRow label="Source">{e.source === 'simulator' ? 'Simulator' : e.source === 'api' ? 'API' : e.source === 'razorpay_webhook' ? 'Razorpay Webhook' : e.source || '—'}</DetailRow>
        <DetailRow label="Follow-Up Round">{
          e.status === 'no_action_needed' || e.status === 'cancelled' ? '—' :
          formatEscalation(e.escalation_level || 0)
        }</DetailRow>
        <DetailRow label="Current Approach">{
          e.status === 'no_action_needed' ? 'No action taken' :
          formatStrategy(e.current_strategy)
        }</DetailRow>
      </div>
    </div>
  )
}

function PipelineStage({ number, label, done, detail, last }) {
  return (
    <div style={{ display: 'flex', gap: 12 }}>
      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
        <div style={{
          width: 26, height: 26, borderRadius: '50%',
          background: done ? '#12B76A' : '#E8EAED',
          color: done ? '#fff' : '#6B7280',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          fontSize: 12, fontWeight: 600,
        }}>
          {done ? '✓' : number}
        </div>
        {!last && <div style={{ width: 2, height: 24, background: done ? '#12B76A' : '#E8EAED' }} />}
      </div>
      <div style={{ paddingBottom: last ? 0 : 12 }}>
        <div style={{ fontSize: 14, fontWeight: 500, color: '#1A1A1A' }}>{label}</div>
        <div style={{ fontSize: 13, color: '#6B7280', marginTop: 2 }}>{detail}</div>
      </div>
    </div>
  )
}

function SectionLabel({ children }) {
  return (
    <div style={{ fontSize: 11, fontWeight: 600, color: '#6B7280', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: 10 }}>
      {children}
    </div>
  )
}

function DetailRow({ label, children }) {
  return (
    <div style={{
      display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start',
      padding: '8px 0', fontSize: 14, borderBottom: '1px solid #E8EAED',
    }}>
      <span style={{ color: '#6B7280', flexShrink: 0, marginRight: 12 }}>{label}</span>
      <span style={{ color: '#1A1A1A', textAlign: 'right', wordBreak: 'break-all' }}>{children}</span>
    </div>
  )
}
