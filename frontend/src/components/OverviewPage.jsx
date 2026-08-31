const fmt = (n) => new Intl.NumberFormat('en-IN', { maximumFractionDigits: 0 }).format(n)

const CARD = {
  background: '#fff',
  border: '1px solid #E8EAED',
  borderRadius: 8,
}

export default function OverviewPage({ analytics, events, onNavigate, dateRange }) {
  const s = analytics?.summary || {}
  const ai = analytics?.ai_lift || {}
  const ranking = analytics?.channel_ranking || []
  const byType = analytics?.by_event_type || {}

  return (
    <div style={{ padding: '28px 32px' }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'baseline', gap: 10, marginBottom: 28 }}>
        <h1 style={{ fontSize: 18, fontWeight: 600, color: '#1A1A1A', margin: 0 }}>Overview</h1>
      </div>

      {/* Hero stat card */}
      <div style={{ ...CARD, padding: '28px 32px', marginBottom: 20 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 8 }}>
          <span style={{ fontSize: 14, fontWeight: 600, color: '#3C4257' }}>Revenue Recovered</span>
          <InfoIcon />
        </div>
        <div style={{ fontSize: 40, fontWeight: 700, color: '#1A1A1A', letterSpacing: '-0.5px', lineHeight: 1.15 }}>
          ₹{fmt(s.recovered_amount || 0)}
        </div>
        <div style={{ fontSize: 14, color: '#6B7280', marginTop: 6 }}>
          from {s.recovered_count || 0} recovered payments
        </div>
      </div>

      {/* 3-card summary row */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 16, marginBottom: 28 }}>
        <SummaryCard
          icon={<DangerCircle />}
          label="At Risk"
          value={`₹${fmt(s.total_amount || 0)}`}
          sub={`${s.total_events || 0} events`}
          onClick={() => onNavigate('events')}
        />
        <SummaryCard
          icon={<ClockCircle />}
          label="Pending"
          value={`₹${fmt(s.pending_amount || 0)}`}
          sub={`${s.pending_count || 0} in pipeline`}
          onClick={() => onNavigate('events')}
        />
        <SummaryCard
          icon={<CrossCircle />}
          label="Stopped"
          value={s.exhausted_count || 0}
          sub={`${s.no_action_count || 0} skipped`}
          onClick={() => onNavigate('events')}
        />
      </div>

      {/* Assisted Recovery + Channel Performance */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16, marginBottom: 28 }}>
        <div style={{ ...CARD, padding: '24px 28px' }}>
          <div style={{ fontSize: 14, fontWeight: 600, color: '#1A1A1A', marginBottom: 20 }}>
            Observed Recovery vs Industry Baseline
          </div>
          <div style={{ display: 'flex', gap: 36, marginBottom: 20 }}>
            <div>
              <div style={{ fontSize: 11, color: '#6B7280', marginBottom: 6, textTransform: 'uppercase', letterSpacing: '0.04em' }}>Industry Baseline</div>
              <div style={{ fontSize: 28, fontWeight: 700, color: '#6B7280' }}>{ai.baseline_rate_percent || 15.0}%</div>
            </div>
            <div>
              <div style={{ fontSize: 11, color: '#528FF0', marginBottom: 6, textTransform: 'uppercase', letterSpacing: '0.04em' }}>Recovery Router</div>
              <div style={{ fontSize: 28, fontWeight: 700, color: '#528FF0' }}>{ai.ai_recovery_rate_percent || 0}%</div>
            </div>
          </div>
          <div style={{ display: 'flex', gap: 8, marginBottom: 12 }}>
            <Bar value={ai.baseline_rate_percent || 15.0} color="#D1D5DB" />
            <Bar value={ai.ai_recovery_rate_percent || 0} color="#528FF0" />
          </div>
          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 13, color: '#6B7280' }}>
            <span>Improvement: <strong style={{ color: (ai.improvement_points || 0) >= 0 ? '#12B76A' : '#F04438' }}>
              {(ai.improvement_points || 0) >= 0 ? '+' : ''}{ai.improvement_points || 0} pts
            </strong></span>
            <span>Observed: <strong style={{ color: '#12B76A' }}>₹{fmt(ai.additional_revenue_recovered || 0)}</strong></span>
          </div>
        </div>

        <div style={{ ...CARD, padding: '24px 28px' }}>
          <div style={{ fontSize: 14, fontWeight: 600, color: '#1A1A1A', marginBottom: 20 }}>
            Channel Performance
          </div>
          {ranking.length === 0 ? (
            <div style={{ fontSize: 14, color: '#6B7280', padding: '24px 0', textAlign: 'center' }}>No channel data yet</div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
              {ranking.slice(0, 4).map((ch, i) => (
                <div key={ch.channel} style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                  <span style={{ fontSize: 13, color: '#6B7280', width: 20 }}>#{i + 1}</span>
                  <span style={{ fontSize: 14, color: '#1A1A1A', width: 80, textTransform: 'capitalize' }}>{ch.channel}</span>
                  <div style={{ flex: 1, height: 6, background: '#E8EAED', borderRadius: 3 }}>
                    <div style={{
                      height: 6, borderRadius: 3,
                      width: `${Math.min(ch.recovery_rate, 100)}%`,
                      background: i === 0 ? '#12B76A' : '#528FF0',
                    }} />
                  </div>
                  <span style={{ fontSize: 13, fontWeight: 600, color: '#1A1A1A', width: 44, textAlign: 'right' }}>
                    {ch.recovery_rate}%
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Recovery by Type */}
      <div style={{ ...CARD, padding: '24px 28px', marginBottom: 28 }}>
        <div style={{ fontSize: 14, fontWeight: 600, color: '#1A1A1A', marginBottom: 20 }}>
          Recovery by Type
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 16 }}>
          {[
            { key: 'payment_failure', label: 'Payment Failures', icon: '💳' },
            { key: 'cart_abandonment', label: 'Cart Abandonment', icon: '🛒' },
            { key: 'invoice_overdue', label: 'Invoice Overdue', icon: '📄' },
          ].map(({ key, label, icon }) => {
            const d = byType[key] || { total: 0, recovered: 0, amount: 0, recovery_rate: 0 }
            return (
              <div key={key} style={{ padding: '18px 20px', borderRadius: 8, border: '1px solid #E8EAED' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 14 }}>
                  <span style={{ fontSize: 16 }}>{icon}</span>
                  <span style={{ fontSize: 14, fontWeight: 500, color: '#1A1A1A' }}>{label}</span>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 13, color: '#6B7280', marginBottom: 6 }}>
                  <span>{d.total} events</span>
                  <span>₹{fmt(d.amount)}</span>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 13 }}>
                  <span style={{ color: '#6B7280' }}>{d.recovered} recovered</span>
                  <span style={{ fontWeight: 600, color: '#528FF0' }}>{d.recovery_rate}%</span>
                </div>
              </div>
            )
          })}
        </div>
      </div>

      {/* Recent Events table */}
      <div style={{ ...CARD, overflow: 'hidden' }}>
        <div style={{
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          padding: '16px 28px', borderBottom: '1px solid #E8EAED',
        }}>
          <span style={{ fontSize: 14, fontWeight: 600, color: '#528FF0', borderBottom: '2px solid #528FF0', paddingBottom: 14, marginBottom: -17 }}>
            Recent Events
          </span>
          <button onClick={() => onNavigate('events')} style={{
            fontSize: 13, color: '#528FF0', background: 'none', border: 'none', cursor: 'pointer', fontWeight: 500,
          }}>View all →</button>
        </div>
        <div style={{ overflowX: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', minWidth: 640 }}>
            <thead>
              <tr style={{ borderBottom: '1px solid #E8EAED' }}>
                {['Type', 'Amount', 'Category', 'Channel', 'Status', 'Time'].map(h => (
                  <th key={h} style={{
                    padding: '12px 20px', fontSize: 12, fontWeight: 600,
                    color: '#6B7280', textAlign: 'left',
                    textTransform: 'uppercase', letterSpacing: '0.04em',
                    whiteSpace: 'nowrap',
                  }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {(events || []).slice(0, 8).map(e => (
                <tr key={e.id}
                  style={{ borderBottom: '1px solid #E8EAED', cursor: 'pointer' }}
                  onMouseEnter={ev => ev.currentTarget.style.background = '#F7F8F9'}
                  onMouseLeave={ev => ev.currentTarget.style.background = 'transparent'}
                  onClick={() => onNavigate('events', e.id)}
                >
                  <td style={{ padding: '12px 20px', whiteSpace: 'nowrap' }}><TypeBadge type={e.event_type} /></td>
                  <td style={{ padding: '12px 20px', fontSize: 14, fontWeight: 500, whiteSpace: 'nowrap' }}>₹{fmt(e.amount)}</td>
                  <td style={{ padding: '12px 20px', fontSize: 14, color: '#5F6B7A', whiteSpace: 'nowrap' }}>{formatCategory(e.failure_category)}</td>
                  <td style={{ padding: '12px 20px', fontSize: 14, color: '#5F6B7A', textTransform: 'capitalize', whiteSpace: 'nowrap' }}>{e.recommended_channel || '—'}</td>
                  <td style={{ padding: '12px 20px', whiteSpace: 'nowrap' }}><StatusBadge status={e.status} /></td>
                  <td style={{ padding: '12px 20px', fontSize: 13, color: '#6B7280', whiteSpace: 'nowrap' }}>{timeAgo(e.created_at)}</td>
                </tr>
              ))}
              {(!events || events.length === 0) && (
                <tr>
                  <td colSpan={6} style={{ padding: '48px 20px', textAlign: 'center', fontSize: 14, color: '#6B7280' }}>
                    No events yet. Use the Simulator to fire test events.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}

/* ─── Shared exports ─── */

export function TypeBadge({ type }) {
  const map = {
    payment_failure: { label: 'Payment', bg: '#FEF3F2', color: '#B42318' },
    cart_abandonment: { label: 'Cart', bg: '#FFFAEB', color: '#B54708' },
    invoice_overdue: { label: 'Invoice', bg: '#EFF8FF', color: '#175CD3' },
  }
  const m = map[type] || { label: type, bg: '#F2F4F7', color: '#5F6B7A' }
  return <span style={{
    display: 'inline-block', padding: '3px 10px', borderRadius: 4,
    fontSize: 12, fontWeight: 500, background: m.bg, color: m.color,
  }}>{m.label}</span>
}

export function StatusBadge({ status }) {
  const map = {
    pending: { label: 'In Progress', bg: '#FFFAEB', color: '#B54708' },
    paused: { label: 'On Hold', bg: '#F0F4FF', color: '#3538CD' },
    recovered: { label: 'Paid', bg: '#ECFDF3', color: '#027A48' },
    exhausted: { label: 'Gave Up', bg: '#FEF3F2', color: '#B42318' },
    no_action_needed: { label: 'Skipped', bg: '#F2F4F7', color: '#5F6B7A' },
    organic_recovery: { label: 'Paid (Self)', bg: '#ECFDF3', color: '#027A48' },
    cancelled: { label: 'Cancelled', bg: '#FEF3F2', color: '#B42318' },
  }
  const m = map[status] || { label: status || '—', bg: '#F2F4F7', color: '#5F6B7A' }
  return <span style={{
    display: 'inline-block', padding: '3px 10px', borderRadius: 4,
    fontSize: 12, fontWeight: 500, background: m.bg, color: m.color,
  }}>{m.label}</span>
}

const CATEGORY_LABELS = {
  upi_timeout: 'Payment Timed Out',
  bank_downtime: 'Bank Offline',
  card_expired: 'Card Expired',
  insufficient_funds: 'Low Balance',
  gateway_error: 'System Error',
  user_cancelled: 'Customer Cancelled',
  unrecoverable_decline: 'Permanently Declined',
  high_intent_abandonment: 'Cart Left Behind',
  browse_only_abandonment: 'Just Browsing',
  recently_overdue: 'Recently Late',
  moderately_overdue: 'Moderately Late',
  long_overdue: 'Very Late',
}

export function formatCategory(cat) {
  if (!cat) return '—'
  return CATEGORY_LABELS[cat] || cat.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())
}

const ESCALATION_LABELS = {
  0: 'Not Started',
  1: 'First Contact',
  2: 'Follow-Up',
  3: 'Escalated',
  4: 'Final Attempt',
  5: 'Max Escalation',
}

export function formatEscalation(level) {
  return ESCALATION_LABELS[level] || `Round ${level}`
}

const STRATEGY_LABELS = {
  initial: 'Scheduled',
  first_contact_sent: 'First Message Sent',
  first_contact_failed: 'First Message Failed',
  follow_up_sent: 'Follow-Up Sent',
  friendly: 'Friendly Follow-Up',
  firm: 'Firm Follow-Up',
  urgent: 'Urgent Follow-Up',
  final: 'Final Attempt',
  exhausted: 'Gave Up',
  window_expired: 'Time Ran Out',
  max_attempts_reached: 'All Attempts Used',
  merchant_paused: 'Paused by You',
  merchant_cancelled: 'Cancelled by You',
  quiet_hours_rescheduled: 'Rescheduled (Quiet Hours)',
  resumed: 'Resumed',
}

export function formatStrategy(strategy) {
  if (!strategy) return '—'
  return STRATEGY_LABELS[strategy] || strategy.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())
}

export function timeAgo(ts) {
  if (!ts) return ''
  const diff = Date.now() - new Date(ts).getTime()
  const mins = Math.floor(diff / 60000)
  if (mins < 1) return 'just now'
  if (mins < 60) return `${mins}m ago`
  const hrs = Math.floor(mins / 60)
  if (hrs < 24) return `${hrs}h ago`
  return `${Math.floor(hrs / 24)}d ago`
}

/* ─── Internal components ─── */

function SummaryCard({ icon, label, value, sub, onClick }) {
  return (
    <div
      onClick={onClick}
      style={{
        ...CARD, padding: '22px 24px',
        cursor: 'pointer', transition: 'box-shadow 0.15s',
      }}
      onMouseEnter={e => e.currentTarget.style.boxShadow = '0 1px 4px rgba(0,0,0,0.06)'}
      onMouseLeave={e => e.currentTarget.style.boxShadow = 'none'}
    >
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 6 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          {icon}
          <span style={{ fontSize: 14, fontWeight: 600, color: '#3C4257' }}>{label}</span>
          <InfoIcon />
        </div>
        <ChevronRight />
      </div>
      <div style={{ fontSize: 32, fontWeight: 700, color: '#1A1A1A', marginTop: 10 }}>{value}</div>
      <div style={{ fontSize: 14, color: '#6B7280', marginTop: 6 }}>{sub}</div>
    </div>
  )
}

function Bar({ value, color }) {
  return (
    <div style={{ flex: 1 }}>
      <div style={{ height: 6, background: '#E8EAED', borderRadius: 3, overflow: 'hidden' }}>
        <div style={{ height: 6, borderRadius: 3, width: `${Math.min(value, 100)}%`, background: color, transition: 'width 0.5s' }} />
      </div>
    </div>
  )
}

function InfoIcon() {
  return <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#C4C9CF" strokeWidth="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/></svg>
}
function DangerCircle() {
  return <div style={{ width: 24, height: 24, borderRadius: '50%', background: '#FEF3F2', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#F04438" strokeWidth="2.5"><circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/></svg>
  </div>
}
function ClockCircle() {
  return <div style={{ width: 24, height: 24, borderRadius: '50%', background: '#FFFAEB', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#F79009" strokeWidth="2.5"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>
  </div>
}
function CrossCircle() {
  return <div style={{ width: 24, height: 24, borderRadius: '50%', background: '#F2F4F7', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#6B7280" strokeWidth="2.5"><circle cx="12" cy="12" r="10"/><line x1="8" y1="12" x2="16" y2="12"/></svg>
  </div>
}
function ChevronRight() {
  return <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#C4C9CF" strokeWidth="2"><polyline points="9 18 15 12 9 6"/></svg>
}
