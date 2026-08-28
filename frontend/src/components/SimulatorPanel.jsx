import { useState } from 'react'
import { simulateEvent } from '../lib/api'

const SCENARIOS = [
  { id: 'upi_timeout', label: 'UPI Timeout', group: 'Payment Failure', hint: 'Retryable · high recovery odds' },
  { id: 'card_expired', label: 'Card Expired', group: 'Payment Failure', hint: 'Needs new card details' },
  { id: 'insufficient_funds', label: 'Insufficient Funds', group: 'Payment Failure', hint: 'Delayed retry works best' },
  { id: 'bank_downtime', label: 'Bank Downtime', group: 'Payment Failure', hint: 'Retry after outage' },
  { id: 'gateway_error', label: 'Gateway Error', group: 'Payment Failure', hint: 'Immediate retry' },
  { id: 'fraud_decline', label: 'Fraud Decline', group: 'Payment Failure', hint: 'Unrecoverable · no spend' },
  { id: 'high_value_cart', label: 'High-Value Cart', group: 'Cart Abandonment', hint: 'Worth chasing' },
  { id: 'low_value_cart', label: 'Low-Value Cart', group: 'Cart Abandonment', hint: 'Below action threshold' },
  { id: 'recent_invoice', label: 'Recent Invoice', group: 'Invoice Overdue', hint: 'Friendly nudge' },
  { id: 'old_invoice', label: 'Old Invoice', group: 'Invoice Overdue', hint: 'Escalated tone' },
]

const GROUPS = ['Payment Failure', 'Cart Abandonment', 'Invoice Overdue']

const EVENT_TYPE_BY_GROUP = {
  'Payment Failure': 'payment_failure',
  'Cart Abandonment': 'cart_abandonment',
  'Invoice Overdue': 'invoice_overdue',
}

export default function SimulatorPanel({ onSimulated }) {
  const [busy, setBusy] = useState(null)
  const [toast, setToast] = useState(null)

  const fire = async (scenario) => {
    setBusy(scenario.id)
    setToast(null)
    try {
      const res = await simulateEvent(EVENT_TYPE_BY_GROUP[scenario.group], scenario.id)
      setToast({ ok: true, msg: res.message || `${scenario.label} queued` })
      onSimulated?.()
    } catch (err) {
      setToast({ ok: false, msg: err.message })
    } finally {
      setBusy(null)
      setTimeout(() => setToast(null), 4000)
    }
  }

  return (
    <div className="rounded-xl p-6 border" style={{ background: 'var(--bg-card)', borderColor: 'var(--border)' }}>
      <div className="flex items-start justify-between mb-4">
        <div>
          <h3 className="text-lg font-semibold" style={{ color: 'var(--text-primary)' }}>
            Simulator
          </h3>
          <p className="text-xs mt-0.5" style={{ color: 'var(--text-secondary)' }}>
            Fire a real event through the live pipeline — classify → route → act
          </p>
        </div>
        {toast && (
          <span
            className="text-xs px-2.5 py-1 rounded-md"
            style={{
              background: 'var(--border)',
              color: toast.ok ? 'var(--success)' : 'var(--danger)',
            }}
          >
            {toast.msg}
          </span>
        )}
      </div>

      <div className="space-y-4">
        {GROUPS.map((group) => (
          <div key={group}>
            <p className="text-xs uppercase tracking-wide mb-2" style={{ color: 'var(--text-secondary)' }}>
              {group}
            </p>
            <div className="flex flex-wrap gap-2">
              {SCENARIOS.filter((s) => s.group === group).map((s) => (
                <button
                  key={s.id}
                  onClick={() => fire(s)}
                  disabled={busy !== null}
                  title={s.hint}
                  className="px-3 py-2 rounded-lg text-sm border transition-opacity disabled:opacity-40"
                  style={{
                    background: busy === s.id ? 'var(--accent)' : 'transparent',
                    borderColor: 'var(--border)',
                    color: busy === s.id ? '#fff' : 'var(--text-primary)',
                    cursor: busy ? 'not-allowed' : 'pointer',
                  }}
                >
                  {busy === s.id ? 'Sending…' : s.label}
                </button>
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
