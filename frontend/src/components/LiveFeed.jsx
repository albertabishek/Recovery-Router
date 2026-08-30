import { useEffect, useState } from 'react'

const STATUS_COLORS = {
  pending: 'var(--warning)',
  recovered: 'var(--success)',
  exhausted: 'var(--danger)',
  no_action_needed: 'var(--text-secondary)',
  organic_recovery: 'var(--success)',
}

const TYPE_LABELS = {
  payment_failure: 'Payment',
  cart_abandonment: 'Cart',
  invoice_overdue: 'Invoice',
}

export default function LiveFeed({ events: initialEvents }) {
  const [events, setEvents] = useState(initialEvents || [])

  useEffect(() => {
    setEvents(initialEvents || [])
  }, [initialEvents])

  const fmt = (n) => new Intl.NumberFormat('en-IN', { maximumFractionDigits: 0 }).format(n)
  const timeAgo = (ts) => {
    if (!ts) return ''
    const diff = Date.now() - new Date(ts).getTime()
    const mins = Math.floor(diff / 60000)
    if (mins < 1) return 'just now'
    if (mins < 60) return `${mins}m ago`
    const hrs = Math.floor(mins / 60)
    if (hrs < 24) return `${hrs}h ago`
    return `${Math.floor(hrs / 24)}d ago`
  }

  return (
    <div className="rounded-xl border overflow-hidden" style={{ background: 'var(--bg-card)', borderColor: 'var(--border)' }}>
      <div className="px-6 py-4 flex items-center justify-between" style={{ borderBottom: '1px solid var(--border)' }}>
        <h3 className="text-lg font-semibold" style={{ color: 'var(--text-primary)' }}>Live Event Feed</h3>
        <span className="flex items-center gap-2 text-xs" style={{ color: 'var(--success)' }}>
          <span className="w-2 h-2 rounded-full animate-pulse" style={{ background: 'var(--success)' }} />
          Auto-refresh
        </span>
      </div>
      <div className="max-h-96 overflow-y-auto">
        {events.length === 0 ? (
          <div className="p-8 text-center" style={{ color: 'var(--text-secondary)' }}>
            No events yet. Send a test event using the simulator below.
          </div>
        ) : (
          events.map((e) => (
            <div key={e.id} className="px-6 py-3 flex items-center gap-4 hover:opacity-90 transition-opacity"
              style={{ borderBottom: '1px solid var(--border)' }}>
              <div className="flex-shrink-0">
                <span className="inline-block px-2 py-0.5 rounded text-xs font-medium"
                  style={{ background: 'var(--border)', color: 'var(--text-primary)' }}>
                  {TYPE_LABELS[e.event_type] || e.event_type}
                </span>
              </div>
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <span className="font-medium text-sm" style={{ color: 'var(--text-primary)' }}>
                    ₹{fmt(e.amount)}
                  </span>
                  {e.failure_category && (
                    <span className="text-xs" style={{ color: 'var(--text-secondary)' }}>
                      {e.failure_category.replace(/_/g, ' ')}
                    </span>
                  )}
                </div>
                <div className="text-xs mt-0.5" style={{ color: 'var(--text-secondary)' }}>
                  {e.recommended_channel && `→ ${e.recommended_channel}`}
                  {e.attempt_count > 0 && ` · ${e.attempt_count} attempts`}
                </div>
              </div>
              <div className="flex-shrink-0 text-right">
                <span className="inline-block px-2 py-0.5 rounded-full text-xs font-medium"
                  style={{ color: STATUS_COLORS[e.status] || 'var(--text-secondary)' }}>
                  {e.status?.replace(/_/g, ' ')}
                </span>
                <div className="text-xs mt-0.5" style={{ color: 'var(--text-secondary)' }}>
                  {timeAgo(e.created_at)}
                </div>
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  )
}
