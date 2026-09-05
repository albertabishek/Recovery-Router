import { useState, useEffect, useRef, useCallback } from 'react'

const BLUE = '#0D94FB'
const NAVY = '#012652'
const TEXT = '#172b4d'
const MUTED = '#5e6c84'
const BORDER = '#ebecf0'
const BG = '#f4f5f7'

const FAILURE_TYPES = [
  {
    id: 'expired-mandate',
    title: 'Expired Mandate',
    desc: 'Spending authorization expired before the agent could execute',
    agent: 'ChatGPT Operator',
    protocol: 'Visa TAP',
    amount: '₹4,999',
    outcome: 'Re-authorize',
    steps: [
      { phase: 'detect', label: 'Payment Attempt', detail: 'Shopping agent requests ₹4,999 via expired TAP mandate (issued 24h ago, validity: 12h)', delay: 1200 },
      { phase: 'diagnose', label: 'Failure Diagnosis', detail: 'MANDATE_EXPIRED | Visa TAP | Mandate: tap_m_8f3k | Expired 3h ago', delay: 1400 },
      { phase: 'verify', label: 'Settlement Verification', detail: 'No funds captured. Gateway confirms zero settlement. Safe to proceed.', delay: 1200 },
      { phase: 'decide', label: 'Policy Decision', detail: 'Expired < 24h → eligible for re-authorization. Agent verified. Amount in scope.', delay: 1400 },
      { phase: 'recover', label: 'Recovery Action', detail: 'Request fresh mandate from user wallet. Queue retry on confirmation. Block stale credential retry.', delay: 1500 },
    ],
  },
  {
    id: 'delegated-limit',
    title: 'Delegation Exceeded',
    desc: 'Cart total grew beyond the agent\'s authorized spending limit',
    agent: 'Amazon Rufus',
    protocol: 'Delegation Grant',
    amount: '₹7,200 / ₹5,000',
    outcome: 'Escalate to User',
    steps: [
      { phase: 'detect', label: 'Payment Attempt', detail: 'Rufus submits ₹7,200 order. Delegation grant: max ₹5,000 per transaction.', delay: 1200 },
      { phase: 'diagnose', label: 'Failure Diagnosis', detail: 'DELEGATION_LIMIT_EXCEEDED | Requested: ₹7,200 | Authorized: ₹5,000 | Over by ₹2,200', delay: 1400 },
      { phase: 'verify', label: 'Settlement Verification', detail: 'Pre-auth declined. No settlement initiated. Grant still active for amounts ≤₹5,000.', delay: 1200 },
      { phase: 'decide', label: 'Policy Decision', detail: '44% overage → too large for silent retry. Must escalate for explicit approval or cart reduction.', delay: 1400 },
      { phase: 'recover', label: 'Recovery Action', detail: 'Push notification: "Order ₹7,200 exceeds your ₹5,000 limit. Approve or let agent adjust cart?"', delay: 1500 },
    ],
  },
  {
    id: 'consumed-credential',
    title: 'Credential Consumed',
    desc: 'One-time payment token already used — duplicate retry detected',
    agent: 'x402 Agent',
    protocol: 'x402 / EIP-3009',
    amount: '₹1,299',
    outcome: 'Stop (Duplicate)',
    steps: [
      { phase: 'detect', label: 'Retry Attempt', detail: 'Agent retries ₹1,299 with same x402 nonce: 0x8f3a...b2c1 (already consumed).', delay: 1200 },
      { phase: 'diagnose', label: 'Failure Diagnosis', detail: 'CREDENTIAL_CONSUMED | Nonce collision at T-45s | Idempotency conflict detected', delay: 1400 },
      { phase: 'verify', label: 'Settlement Verification', detail: 'First attempt: SETTLED (₹1,299 captured). Original payment succeeded. This is a duplicate.', delay: 1400 },
      { phase: 'decide', label: 'Policy Decision', detail: 'Original confirmed captured → duplicate attempt, not a failure. Mark as already_recovered.', delay: 1400 },
      { phase: 'recover', label: 'Recovery Action', detail: 'Suppress retry. Confirm payment_id pay_x402_8f3a. Prevent double-charge. Audit logged.', delay: 1400 },
    ],
  },
  {
    id: 'untrusted-agent',
    title: 'Identity Rejected',
    desc: 'PSP cannot verify agent identity or authorization chain',
    agent: 'Merchant Agent',
    protocol: 'Agent Studio',
    amount: '₹15,000',
    outcome: 'Block + Alert',
    steps: [
      { phase: 'detect', label: 'Payment Attempt', detail: 'Merchant agent submits ₹15,000 B2B payment. Agent ID: agent_studio_m7k2. PSP rejects.', delay: 1200 },
      { phase: 'diagnose', label: 'Failure Diagnosis', detail: 'AGENT_IDENTITY_REJECTED | Token signature invalid or not in trusted registry', delay: 1400 },
      { phase: 'verify', label: 'Settlement Verification', detail: 'Rejected pre-authorization. No funds at risk. Identity issue is upstream of money movement.', delay: 1200 },
      { phase: 'decide', label: 'Policy Decision', detail: 'Identity failure NOT retryable. Could be: expired signing key, revoked agent, or replay attack.', delay: 1500 },
      { phase: 'recover', label: 'Recovery Action', detail: 'Block all retries. Alert: "Agent m7k2 rejected — verify signing keys in Agent Studio."', delay: 1500 },
    ],
  },
  {
    id: 'psp-timeout',
    title: 'Unknown Settlement',
    desc: 'Payment timed out at PSP — unclear if money was captured',
    agent: 'Delivery Agent',
    protocol: 'Razorpay Gateway',
    amount: '₹849',
    outcome: 'Safe Retry',
    steps: [
      { phase: 'detect', label: 'Payment Attempt', detail: 'Agent submits ₹849 payment. PSP response: HTTP 504 Gateway Timeout after 30s.', delay: 1200 },
      { phase: 'diagnose', label: 'Failure Diagnosis', detail: 'PSP_TIMEOUT | Order: order_M8k2p | Settlement status: UNKNOWN — could be captured or failed', delay: 1500 },
      { phase: 'verify', label: 'Settlement Verification', detail: 'PSP API: status "created" (not captured). Bank: no debit on instrument. Confirmed SAFE to retry.', delay: 1600 },
      { phase: 'decide', label: 'Policy Decision', detail: 'No capture confirmed → safe retry with fresh idempotency key. Wait 60s for gateway recovery.', delay: 1400 },
      { phase: 'recover', label: 'Recovery Action', detail: 'Retry with idem_key: order_M8k2p:retry:1. Second timeout → escalate to user.', delay: 1500 },
    ],
  },
  {
    id: 'delivery-mismatch',
    title: 'Paid but Undelivered',
    desc: 'Payment succeeded but the service or product was never delivered',
    agent: 'API Agent',
    protocol: 'x402',
    amount: '₹2,499',
    outcome: 'Retry / Refund',
    steps: [
      { phase: 'detect', label: 'Payment + Service', detail: 'Agent pays ₹2,499 for API access. Payment: SETTLED. Service response: HTTP 500.', delay: 1200 },
      { phase: 'diagnose', label: 'Failure Diagnosis', detail: 'Payment layer: SUCCESS (₹2,499). Service layer: FAILED (500). Money moved but value not delivered.', delay: 1500 },
      { phase: 'verify', label: 'Settlement Verification', detail: 'Confirmed ₹2,499 settled at PSP. Service endpoint returned 500 — no API key issued.', delay: 1400 },
      { phase: 'decide', label: 'Policy Decision', detail: 'Payment OK but delivery failed → refund or re-delivery case, not a payment retry.', delay: 1400 },
      { phase: 'recover', label: 'Recovery Action', detail: 'Retry service call 3x over 5 minutes. Still failing → auto-refund ₹2,499. Log for disputes.', delay: 1500 },
    ],
  },
]

const PHASE_STEPS = [
  { key: 'detect', label: 'Detect', number: '1' },
  { key: 'diagnose', label: 'Diagnose', number: '2' },
  { key: 'verify', label: 'Verify', number: '3' },
  { key: 'decide', label: 'Decide', number: '4' },
  { key: 'recover', label: 'Recover', number: '5' },
]

const PHASE_STYLE = {
  detect: { bg: '#f0f4ff', border: '#d0d9f0' },
  diagnose: { bg: '#fef3f2', border: '#fecdca' },
  verify: { bg: '#fffaeb', border: '#fde68a' },
  decide: { bg: '#eff8ff', border: '#b2ddff' },
  recover: { bg: '#ecfdf3', border: '#a6f4c5' },
}

function PipelineStep({ step, visible, stepNumber }) {
  if (!visible) return null
  const style = PHASE_STYLE[step.phase]
  return (
    <div style={{
      display: 'flex', gap: 14, padding: '14px 16px', margin: '8px 0',
      background: style.bg, border: `1px solid ${style.border}`, borderRadius: 4,
      animation: 'fadeSlideIn 0.4s ease-out',
    }}>
      <span style={{
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        width: 28, height: 28, borderRadius: '50%', flexShrink: 0,
        background: NAVY, color: '#fff', fontSize: 12, fontWeight: 700,
      }}>
        {stepNumber}
      </span>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ fontSize: 14, fontWeight: 600, color: TEXT, marginBottom: 4 }}>{step.label}</div>
        <div style={{ fontSize: 13, color: MUTED, lineHeight: 1.6, fontFamily: "'SF Mono', 'Cascadia Code', 'Consolas', monospace" }}>
          {step.detail}
        </div>
      </div>
    </div>
  )
}

function ScenarioCard({ failure, isSelected, onSelect, index }) {
  return (
    <button
      onClick={onSelect}
      style={{
        display: 'flex', alignItems: 'center', gap: 12,
        padding: '12px 14px', width: '100%', textAlign: 'left',
        background: isSelected ? '#eff8ff' : '#fff',
        border: isSelected ? `2px solid ${BLUE}` : `1px solid ${BORDER}`,
        borderRadius: 4, cursor: 'pointer', fontFamily: 'inherit',
        transition: 'all 0.15s',
      }}
    >
      <span style={{
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        width: 32, height: 32, borderRadius: '50%', flexShrink: 0,
        background: isSelected ? BLUE : BORDER,
        color: isSelected ? '#fff' : MUTED,
        fontSize: 13, fontWeight: 700,
      }}>
        {index + 1}
      </span>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ fontSize: 14, fontWeight: 600, color: TEXT }}>{failure.title}</div>
        <div style={{ fontSize: 12, color: MUTED, lineHeight: 1.4, marginTop: 2 }}>{failure.desc}</div>
      </div>
      {isSelected && (
        <svg width="14" height="14" viewBox="0 0 14 14" fill="none" style={{ flexShrink: 0 }}>
          <path d="M5 3l4 4-4 4" stroke={BLUE} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
        </svg>
      )}
    </button>
  )
}

function ScenarioPlayer({ failure }) {
  const [visibleSteps, setVisibleSteps] = useState(0)
  const [playing, setPlaying] = useState(false)
  const [done, setDone] = useState(false)
  const [activePhase, setActivePhase] = useState(null)
  const logRef = useRef(null)
  const timeoutsRef = useRef([])

  const reset = useCallback(() => {
    timeoutsRef.current.forEach(clearTimeout)
    timeoutsRef.current = []
    setVisibleSteps(0)
    setPlaying(false)
    setDone(false)
    setActivePhase(null)
  }, [])

  const play = useCallback(() => {
    reset()
    setPlaying(true)
    let cumulative = 0
    failure.steps.forEach((step, i) => {
      cumulative += step.delay
      const t = setTimeout(() => {
        setVisibleSteps(i + 1)
        setActivePhase(step.phase)
        if (i === failure.steps.length - 1) {
          setPlaying(false)
          setDone(true)
        }
      }, cumulative)
      timeoutsRef.current.push(t)
    })
  }, [failure, reset])

  useEffect(() => {
    return () => timeoutsRef.current.forEach(clearTimeout)
  }, [])

  useEffect(() => { reset() }, [failure, reset])

  useEffect(() => {
    if (logRef.current) logRef.current.scrollTop = logRef.current.scrollHeight
  }, [visibleSteps])

  return (
    <div style={{ background: '#fff', border: `1px solid ${BORDER}`, borderRadius: 4, overflow: 'hidden' }}>
      <div style={{
        padding: '16px 20px', borderBottom: `1px solid ${BORDER}`,
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
      }}>
        <div>
          <div style={{ fontSize: 16, fontWeight: 700, color: TEXT }}>{failure.title}</div>
          <div style={{ fontSize: 13, color: MUTED, marginTop: 2 }}>
            {failure.agent} &middot; {failure.protocol} &middot; {failure.amount}
          </div>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          {done && (
            <button onClick={reset} style={{
              padding: '7px 14px', fontSize: 13, fontWeight: 500,
              border: `1px solid ${BORDER}`, borderRadius: 4,
              background: '#fff', color: TEXT, cursor: 'pointer', fontFamily: 'inherit',
            }}>
              Reset
            </button>
          )}
          <button
            onClick={play}
            disabled={playing}
            style={{
              padding: '7px 18px', fontSize: 13, fontWeight: 600,
              border: 'none', borderRadius: 4,
              background: playing ? '#94A3B8' : BLUE,
              color: '#fff', cursor: playing ? 'not-allowed' : 'pointer',
              fontFamily: 'inherit', display: 'flex', alignItems: 'center', gap: 6,
            }}
          >
            {playing ? (
              <>
                <span style={{ display: 'inline-block', width: 6, height: 6, borderRadius: '50%', background: '#fff', animation: 'pulse 1s infinite' }} />
                Processing...
              </>
            ) : done ? 'Run Again' : 'Run Scenario'}
          </button>
        </div>
      </div>

      <div style={{
        display: 'flex', padding: '10px 20px', gap: 0,
        borderBottom: `1px solid ${BORDER}`, background: BG,
      }}>
        {PHASE_STEPS.map((p, i) => {
          const isActive = activePhase === p.key
          const stepIdx = failure.steps.findIndex(s => s.phase === p.key)
          const isPast = stepIdx < visibleSteps && stepIdx >= 0 && visibleSteps > 0
          return (
            <div key={p.key} style={{ display: 'flex', alignItems: 'center', flex: 1 }}>
              <div style={{
                display: 'flex', alignItems: 'center', gap: 6,
                padding: '5px 8px', borderRadius: 4,
                background: isActive ? '#e6f7ff' : 'transparent',
                transition: 'all 0.3s',
              }}>
                <span style={{
                  width: 22, height: 22, borderRadius: '50%', display: 'flex',
                  alignItems: 'center', justifyContent: 'center',
                  fontSize: 11, fontWeight: 700,
                  background: isPast || isActive ? NAVY : BORDER,
                  color: isPast || isActive ? '#fff' : MUTED,
                  transition: 'all 0.3s',
                }}>
                  {isPast && !isActive ? '✓' : p.number}
                </span>
                <span style={{
                  fontSize: 13, fontWeight: isActive ? 700 : 500,
                  color: isActive ? NAVY : isPast ? TEXT : MUTED,
                  transition: 'all 0.3s',
                }}>
                  {p.label}
                </span>
              </div>
              {i < PHASE_STEPS.length - 1 && (
                <div style={{
                  flex: 1, height: 2, margin: '0 4px',
                  background: isPast ? NAVY : BORDER,
                  transition: 'background 0.3s',
                }} />
              )}
            </div>
          )
        })}
      </div>

      <div ref={logRef} style={{ padding: '12px 20px', minHeight: 280, maxHeight: 420, overflowY: 'auto' }}>
        {visibleSteps === 0 && !playing && (
          <div style={{
            height: 260, display: 'flex', flexDirection: 'column',
            alignItems: 'center', justifyContent: 'center', color: MUTED,
          }}>
            <div style={{
              width: 48, height: 48, borderRadius: '50%', display: 'flex',
              alignItems: 'center', justifyContent: 'center',
              background: BG, marginBottom: 14,
            }}>
              <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
                <path d="M8 5l5 5-5 5" stroke={MUTED} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
              </svg>
            </div>
            <span style={{ fontSize: 15, fontWeight: 600, color: TEXT }}>Ready to trace</span>
            <span style={{ fontSize: 13, color: MUTED, marginTop: 4 }}>
              Click "Run Scenario" to watch the 5-step recovery pipeline
            </span>
          </div>
        )}
        {failure.steps.map((step, i) => (
          <PipelineStep key={i} step={step} visible={i < visibleSteps} stepNumber={i + 1} />
        ))}
        {done && (
          <div style={{
            margin: '14px 0 4px', padding: '12px 16px', borderRadius: 4,
            background: '#f0fdf4', border: '1px solid #bbf7d0',
            fontSize: 14, color: '#166534', fontWeight: 500,
          }}>
            Pipeline complete — Outcome: <strong>{failure.outcome}</strong>
          </div>
        )}
      </div>
    </div>
  )
}

export default function AgenticDemoPage() {
  const [selectedId, setSelectedId] = useState(FAILURE_TYPES[0].id)
  const selected = FAILURE_TYPES.find(f => f.id === selectedId)

  return (
    <div style={{ padding: '28px 32px' }}>
      <style>{`
        @keyframes fadeSlideIn {
          from { opacity: 0; transform: translateY(6px); }
          to { opacity: 1; transform: translateY(0); }
        }
        @keyframes pulse {
          0%, 100% { opacity: 1; }
          50% { opacity: 0.4; }
        }
      `}</style>

      <div style={{ marginBottom: 24 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 6 }}>
          <h1 style={{ fontSize: 18, fontWeight: 700, color: TEXT, margin: 0 }}>
            Agentic Payment Recovery
          </h1>
          <span style={{
            padding: '3px 10px', fontSize: 11, fontWeight: 600,
            background: '#EFF8FF', color: BLUE, borderRadius: 4,
          }}>
            VISION
          </span>
        </div>
        <p style={{ fontSize: 14, color: MUTED, margin: 0, lineHeight: 1.6, maxWidth: 680 }}>
          AI agents (ChatGPT Operator, Amazon Rufus, Razorpay Agent Studio) are starting to make payments on behalf of users.
          When those payments fail, Recovery Router diagnoses and resolves them through a deterministic 5-step pipeline.
        </p>
      </div>

      <div style={{
        background: `linear-gradient(135deg, ${NAVY} 0%, #01305e 100%)`,
        borderRadius: 4, padding: '18px 24px', marginBottom: 24,
        display: 'flex', alignItems: 'center', gap: 24,
      }}>
        <div style={{ flex: 1 }}>
          <div style={{ fontSize: 15, fontWeight: 700, color: '#fff', marginBottom: 6 }}>
            How It Works
          </div>
          <div style={{ fontSize: 13, color: '#94A3B8', lineHeight: 1.6 }}>
            Every failed agent payment flows through 5 deterministic steps — no human in the loop.
            Select a scenario below and run it to see each step in action.
          </div>
        </div>
        <div style={{ display: 'flex', gap: 8, flexShrink: 0 }}>
          {PHASE_STEPS.map((p, i) => (
            <div key={p.key} style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              <div style={{
                padding: '8px 14px', borderRadius: 4, textAlign: 'center',
                background: 'rgba(255,255,255,0.08)', border: '1px solid rgba(255,255,255,0.12)',
              }}>
                <div style={{ fontSize: 16, fontWeight: 700, color: '#fff', marginBottom: 2 }}>{p.number}</div>
                <div style={{ fontSize: 11, fontWeight: 600, color: '#94A3B8' }}>{p.label}</div>
              </div>
              {i < PHASE_STEPS.length - 1 && (
                <span style={{ color: 'rgba(255,255,255,0.25)', fontSize: 14 }}>→</span>
              )}
            </div>
          ))}
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '300px 1fr', gap: 20, marginBottom: 28 }}>
        <div>
          <div style={{
            fontSize: 11, fontWeight: 600, color: MUTED, textTransform: 'uppercase',
            letterSpacing: '0.05em', marginBottom: 10, padding: '0 2px',
          }}>
            Failure Scenarios
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            {FAILURE_TYPES.map((f, i) => (
              <ScenarioCard
                key={f.id}
                failure={f}
                index={i}
                isSelected={selectedId === f.id}
                onSelect={() => setSelectedId(f.id)}
              />
            ))}
          </div>
        </div>

        <div>
          <div style={{
            fontSize: 11, fontWeight: 600, color: MUTED, textTransform: 'uppercase',
            letterSpacing: '0.05em', marginBottom: 10, padding: '0 2px',
          }}>
            Pipeline Trace
          </div>
          <ScenarioPlayer failure={selected} />
        </div>
      </div>

      <div style={{
        background: '#fff', border: `1px solid ${BORDER}`, borderRadius: 4,
        padding: '18px 24px',
        display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 16,
      }}>
        <div style={{ gridColumn: '1 / -1', marginBottom: 4 }}>
          <div style={{ fontSize: 14, fontWeight: 700, color: TEXT }}>Razorpay Ecosystem Fit</div>
          <div style={{ fontSize: 13, color: MUTED, marginTop: 2 }}>How Recovery Router integrates with Razorpay's agentic infrastructure</div>
        </div>
        {[
          { title: 'Vulcan AI', desc: 'Scores payment routes for success probability. Recovery Router handles what Vulcan can\'t prevent — diagnosing and recovering failed agent payments.' },
          { title: 'Agent Studio', desc: 'Agents built in Agent Studio execute payments. Recovery Router catches their failures — expired mandates, limit overages, identity rejections — and routes to the right action.' },
          { title: 'MCP Server', desc: 'Recovery analytics exposed via MCP Server, letting AI assistants query failure patterns, settlement status, and recovery outcomes conversationally.' },
        ].map((item, i) => (
          <div key={i} style={{
            padding: '16px 18px', borderRadius: 4,
            background: BG, border: `1px solid ${BORDER}`,
          }}>
            <div style={{ fontSize: 14, fontWeight: 600, color: TEXT, marginBottom: 6 }}>{item.title}</div>
            <div style={{ fontSize: 13, color: MUTED, lineHeight: 1.6 }}>{item.desc}</div>
          </div>
        ))}
      </div>
    </div>
  )
}
