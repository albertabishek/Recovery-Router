import { useState } from 'react'
import { simulateEvent } from '../lib/api'
import { StatusBadge, TypeBadge, timeAgo } from './OverviewPage'

const fmt = (n) => new Intl.NumberFormat('en-IN', { maximumFractionDigits: 0 }).format(n)

const SCENARIOS = [
  { id: 'upi_timeout', label: 'UPI Timeout', group: 'Payment Failure', desc: 'Retryable — high recovery odds', amount: '₹499–4,999' },
  { id: 'card_expired', label: 'Card Expired', group: 'Payment Failure', desc: 'Needs new card details', amount: '₹1,999–8,999' },
  { id: 'insufficient_funds', label: 'Insufficient Funds', group: 'Payment Failure', desc: 'Delayed retry works best', amount: '₹2,499–12,999' },
  { id: 'bank_downtime', label: 'Bank Downtime', group: 'Payment Failure', desc: 'Retry after outage clears', amount: '₹999–4,999' },
  { id: 'gateway_error', label: 'Gateway Error', group: 'Payment Failure', desc: 'Immediate retry likely to succeed', amount: '₹799–3,999' },
  { id: 'fraud_decline', label: 'Fraud Decline', group: 'Payment Failure', desc: 'Unrecoverable — system skips action', amount: '₹9,999–24,999' },
  { id: 'high_value_cart', label: 'High-Value Cart', group: 'Cart Abandonment', desc: 'Worth chasing — email + link', amount: '₹2,999–14,999' },
  { id: 'low_value_cart', label: 'Low-Value Cart', group: 'Cart Abandonment', desc: 'Below action threshold — no spend', amount: '₹99–199' },
  { id: 'recent_invoice', label: 'Recent Invoice', group: 'Invoice Overdue', desc: 'Friendly nudge, high recovery', amount: '₹5,000–50,000' },
  { id: 'old_invoice', label: 'Old Invoice', group: 'Invoice Overdue', desc: 'Escalated tone, lower odds', amount: '₹15,000–75,000' },
]

const GROUPS = ['Payment Failure', 'Cart Abandonment', 'Invoice Overdue']
const TYPE_MAP = { 'Payment Failure': 'payment_failure', 'Cart Abandonment': 'cart_abandonment', 'Invoice Overdue': 'invoice_overdue' }

const inputStyle = {
  width: '100%',
  padding: '9px 12px',
  border: '1px solid #E8EAED',
  borderRadius: 6,
  fontSize: 14,
  color: '#1A1A1A',
  background: '#fff',
  outline: 'none',
  transition: 'border-color 0.15s',
  fontFamily: 'inherit',
}

export default function SimulatorPage({ events, onSimulated }) {
  const [busy, setBusy] = useState(null)
  const [results, setResults] = useState([])
  const [customer, setCustomer] = useState({ name: '', email: '', phone: '' })
  const [showCustomer, setShowCustomer] = useState(false)

  const fire = async (scenario) => {
    setBusy(scenario.id)
    const ts = Date.now()
    try {
      const res = await simulateEvent(TYPE_MAP[scenario.group], scenario.id, customer)
      setResults(prev => [{ id: ts, scenario: scenario.label, group: scenario.group, status: 'queued', message: res.message, time: new Date() }, ...prev].slice(0, 20))
      onSimulated?.()
    } catch (err) {
      setResults(prev => [{ id: ts, scenario: scenario.label, group: scenario.group, status: 'error', message: err.message, time: new Date() }, ...prev].slice(0, 20))
    } finally {
      setBusy(null)
    }
  }

  return (
    <div style={{ padding: '28px 32px' }}>
      <div style={{ marginBottom: 28 }}>
        <h1 style={{ fontSize: 18, fontWeight: 600, color: '#1A1A1A', margin: '0 0 6px' }}>Simulator</h1>
        <p style={{ fontSize: 14, color: '#6B7280', margin: 0 }}>
          Fire real events through the live pipeline. Each event goes through: AI Classify → Route → Payment Link → Send Message → Track.
        </p>
      </div>

      <div style={{
        background: '#fff', border: '1px solid #E8EAED', borderRadius: 8,
        marginBottom: 24, overflow: 'hidden',
      }}>
        <button
          onClick={() => setShowCustomer(v => !v)}
          style={{
            width: '100%', display: 'flex', alignItems: 'center', justifyContent: 'space-between',
            padding: '14px 20px', background: 'none', border: 'none', cursor: 'pointer',
            fontFamily: 'inherit', fontSize: 14, fontWeight: 600, color: '#1A1A1A',
          }}
        >
          <span style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <svg width="16" height="16" viewBox="0 0 16 16" fill="none" style={{ flexShrink: 0 }}>
              <path d="M8 8a3 3 0 100-6 3 3 0 000 6zm0 1.5c-3.315 0-6 1.343-6 3v.5a1 1 0 001 1h10a1 1 0 001-1v-.5c0-1.657-2.685-3-6-3z" fill="#6B7280"/>
            </svg>
            Customer Details
            {(customer.name || customer.email || customer.phone) && (
              <span style={{
                fontSize: 11, fontWeight: 500, color: '#528FF0', background: '#F0F4FF',
                padding: '2px 8px', borderRadius: 10,
              }}>
                Custom
              </span>
            )}
          </span>
          <svg width="12" height="12" viewBox="0 0 12 12" fill="none"
            style={{ transform: showCustomer ? 'rotate(180deg)' : 'rotate(0)', transition: 'transform 0.2s' }}>
            <path d="M2.5 4.5L6 8l3.5-3.5" stroke="#6B7280" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
          </svg>
        </button>

        {showCustomer && (
          <div style={{ padding: '0 20px 20px', borderTop: '1px solid #E8EAED' }}>
            <p style={{ fontSize: 13, color: '#6B7280', margin: '14px 0 16px' }}>
              Override the default test recipient. Leave blank to use the system defaults.
            </p>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(220px, 1fr))', gap: 12 }}>
              <div>
                <label style={{ display: 'block', fontSize: 12, fontWeight: 600, color: '#6B7280', marginBottom: 6, textTransform: 'uppercase', letterSpacing: '0.04em' }}>
                  Name
                </label>
                <input
                  type="text"
                  placeholder="e.g. Rahul Sharma"
                  value={customer.name}
                  onChange={e => setCustomer(c => ({ ...c, name: e.target.value }))}
                  style={inputStyle}
                  onFocus={e => e.target.style.borderColor = '#528FF0'}
                  onBlur={e => e.target.style.borderColor = '#E8EAED'}
                />
              </div>
              <div>
                <label style={{ display: 'block', fontSize: 12, fontWeight: 600, color: '#6B7280', marginBottom: 6, textTransform: 'uppercase', letterSpacing: '0.04em' }}>
                  Email
                </label>
                <input
                  type="email"
                  placeholder="e.g. rahul@example.com"
                  value={customer.email}
                  onChange={e => setCustomer(c => ({ ...c, email: e.target.value }))}
                  style={inputStyle}
                  onFocus={e => e.target.style.borderColor = '#528FF0'}
                  onBlur={e => e.target.style.borderColor = '#E8EAED'}
                />
              </div>
              <div>
                <label style={{ display: 'block', fontSize: 12, fontWeight: 600, color: '#6B7280', marginBottom: 6, textTransform: 'uppercase', letterSpacing: '0.04em' }}>
                  Phone
                </label>
                <input
                  type="tel"
                  placeholder="e.g. +919876543210"
                  value={customer.phone}
                  onChange={e => setCustomer(c => ({ ...c, phone: e.target.value }))}
                  style={inputStyle}
                  onFocus={e => e.target.style.borderColor = '#528FF0'}
                  onBlur={e => e.target.style.borderColor = '#E8EAED'}
                />
              </div>
            </div>
            {(customer.name || customer.email || customer.phone) && (
              <button
                onClick={() => setCustomer({ name: '', email: '', phone: '' })}
                style={{
                  marginTop: 12, padding: '6px 14px', fontSize: 13, color: '#6B7280',
                  background: 'none', border: '1px solid #E8EAED', borderRadius: 6,
                  cursor: 'pointer', fontFamily: 'inherit',
                }}
              >
                Reset to defaults
              </button>
            )}
          </div>
        )}
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 24, marginBottom: 32 }}>
        {GROUPS.map(group => (
          <div key={group}>
            <div style={{ fontSize: 11, fontWeight: 600, color: '#6B7280', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: 12 }}>
              {group}
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: 12 }}>
              {SCENARIOS.filter(s => s.group === group).map(s => (
                <button
                  key={s.id}
                  onClick={() => fire(s)}
                  disabled={busy !== null}
                  style={{
                    display: 'flex', flexDirection: 'column', gap: 6,
                    padding: '16px 20px',
                    background: busy === s.id ? '#F0F4FF' : '#fff',
                    border: busy === s.id ? '1px solid #528FF0' : '1px solid #E8EAED',
                    borderRadius: 8,
                    cursor: busy ? 'not-allowed' : 'pointer',
                    textAlign: 'left',
                    transition: 'border-color 0.15s, box-shadow 0.15s',
                    opacity: busy && busy !== s.id ? 0.5 : 1,
                    fontFamily: 'inherit',
                  }}
                  onMouseEnter={e => { if (!busy) e.currentTarget.style.borderColor = '#528FF0' }}
                  onMouseLeave={e => { if (busy !== s.id) e.currentTarget.style.borderColor = '#E8EAED' }}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', width: '100%' }}>
                    <span style={{ fontSize: 14, fontWeight: 600, color: '#1A1A1A' }}>
                      {busy === s.id ? 'Sending…' : s.label}
                    </span>
                    <span style={{ fontSize: 12, color: '#6B7280' }}>{s.amount}</span>
                  </div>
                  <span style={{ fontSize: 13, color: '#6B7280' }}>{s.desc}</span>
                </button>
              ))}
            </div>
          </div>
        ))}
      </div>

      {results.length > 0 && (
        <div style={{ background: '#fff', border: '1px solid #E8EAED', borderRadius: 8, overflow: 'hidden' }}>
          <div style={{ padding: '16px 24px', borderBottom: '1px solid #E8EAED', fontSize: 14, fontWeight: 600, color: '#1A1A1A' }}>
            Simulation Log
          </div>
          <div style={{ maxHeight: 300, overflow: 'auto' }}>
            {results.map(r => (
              <div key={r.id} style={{
                display: 'flex', alignItems: 'center', gap: 12,
                padding: '12px 24px', borderBottom: '1px solid #E8EAED', fontSize: 14,
              }}>
                <span style={{
                  width: 7, height: 7, borderRadius: '50%', flexShrink: 0,
                  background: r.status === 'queued' ? '#12B76A' : '#F04438',
                }} />
                <span style={{ fontWeight: 500, color: '#1A1A1A', minWidth: 130 }}>{r.scenario}</span>
                <span style={{ color: '#6B7280', flex: 1 }}>{r.message}</span>
                <span style={{ color: '#6B7280', fontSize: 13, flexShrink: 0 }}>{r.time.toLocaleTimeString()}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {(events || []).length > 0 && (
        <div style={{ background: '#fff', border: '1px solid #E8EAED', borderRadius: 8, overflow: 'hidden', marginTop: 16 }}>
          <div style={{
            padding: '16px 24px', borderBottom: '1px solid #E8EAED', fontSize: 14, fontWeight: 600, color: '#1A1A1A',
            display: 'flex', alignItems: 'center', gap: 8,
          }}>
            Pipeline Results
            <span style={{ width: 7, height: 7, borderRadius: '50%', background: '#12B76A', animation: 'pulse 2s infinite' }} />
            <span style={{ fontSize: 12, color: '#6B7280', fontWeight: 400 }}>Live from Supabase</span>
          </div>
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', minWidth: 780 }}>
              <thead>
                <tr>
                  {['ID', 'Type', 'Amount', 'AI Category', 'Routed To', 'Probability', 'Status', 'Time'].map(h => (
                    <th key={h} style={{
                      padding: '10px 16px', fontSize: 12, fontWeight: 600,
                      color: '#6B7280', textAlign: 'left',
                      textTransform: 'uppercase', letterSpacing: '0.04em',
                      borderBottom: '1px solid #E8EAED',
                      whiteSpace: 'nowrap',
                    }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {(events || []).slice(0, 20).map(e => (
                  <tr key={e.id} style={{ borderBottom: '1px solid #E8EAED' }}>
                    <td style={{ padding: '10px 16px', fontSize: 13, fontFamily: 'monospace', color: '#6B7280', whiteSpace: 'nowrap' }}>#{e.id}</td>
                    <td style={{ padding: '10px 16px', whiteSpace: 'nowrap' }}><TypeBadge type={e.event_type} /></td>
                    <td style={{ padding: '10px 16px', fontSize: 14, fontWeight: 500, whiteSpace: 'nowrap' }}>₹{fmt(e.amount)}</td>
                    <td style={{ padding: '10px 16px', fontSize: 14, color: '#5F6B7A', textTransform: 'capitalize', whiteSpace: 'nowrap' }}>{(e.failure_category || '—').replace(/_/g, ' ')}</td>
                    <td style={{ padding: '10px 16px', fontSize: 14, color: '#5F6B7A', textTransform: 'capitalize', whiteSpace: 'nowrap' }}>{e.recommended_channel || '—'}</td>
                    <td style={{ padding: '10px 16px', fontSize: 14, color: '#528FF0', fontWeight: 600, whiteSpace: 'nowrap' }}>{Math.round((e.recovery_probability || 0) * 100)}%</td>
                    <td style={{ padding: '10px 16px', whiteSpace: 'nowrap' }}><StatusBadge status={e.status} /></td>
                    <td style={{ padding: '10px 16px', fontSize: 13, color: '#6B7280', whiteSpace: 'nowrap' }}>{timeAgo(e.created_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  )
}
