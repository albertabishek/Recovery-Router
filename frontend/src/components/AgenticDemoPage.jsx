import { useState, useEffect, useRef, useCallback } from 'react'

const CARD = {
  background: '#fff',
  border: '1px solid #E8EAED',
  borderRadius: 8,
}

const FAILURE_TYPES = [
  {
    id: 'expired-mandate',
    title: 'Expired Authorization Mandate',
    desc: 'Agent\'s pre-approved spending mandate expired before the payment executed',
    icon: '⏰',
    color: '#B42318',
    example: 'ChatGPT Operator tries to purchase an item using a Visa Trusted Agent Protocol mandate that expired 3 hours ago',
    steps: [
      { phase: 'trigger', label: 'Agent Payment Attempt', detail: 'Shopping agent requests ₹4,999 purchase via expired TAP mandate (issued 24h ago, validity: 12h)', delay: 500 },
      { phase: 'diagnose', label: 'Failure-Layer Diagnosis', detail: 'Error: MANDATE_EXPIRED | Protocol: Visa TAP | Mandate ID: tap_m_8f3k | Expired at: 2026-09-03T06:00Z', delay: 600 },
      { phase: 'reconcile', label: 'Reconciliation Check', detail: 'No partial settlement detected. Payment gateway confirms: no funds captured. Safe to proceed.', delay: 500 },
      { phase: 'policy', label: 'Policy Decision', detail: 'Mandate expired < 24h ago → eligible for re-authorization. Agent identity verified. Amount within original scope.', delay: 600 },
      { phase: 'action', label: 'Action: Request New Authorization', detail: 'Notify user\'s wallet to issue fresh mandate. Queue retry for when new mandate is confirmed. Do NOT retry on stale credential.', delay: 700 },
    ],
  },
  {
    id: 'delegated-limit',
    title: 'Amount Exceeds Delegated Limit',
    desc: 'Agent was authorized for up to ₹5,000 but the cart total grew beyond that',
    icon: '🚫',
    color: '#DC6803',
    example: 'Amazon Rufus "Buy for Me" agent adds items totaling ₹7,200 but user only delegated ₹5,000 spending authority',
    steps: [
      { phase: 'trigger', label: 'Agent Payment Attempt', detail: 'Rufus agent submits ₹7,200 order. Delegation grant: max ₹5,000 per transaction.', delay: 500 },
      { phase: 'diagnose', label: 'Failure-Layer Diagnosis', detail: 'Error: DELEGATION_LIMIT_EXCEEDED | Requested: ₹7,200 | Authorized: ₹5,000 | Overage: ₹2,200', delay: 600 },
      { phase: 'reconcile', label: 'Reconciliation Check', detail: 'Pre-authorization declined at gateway. No settlement initiated. Delegation grant still active for ≤₹5,000.', delay: 500 },
      { phase: 'policy', label: 'Policy Decision', detail: 'Overage is 44% above limit → too large for silent retry. Must escalate to user for explicit approval or cart reduction.', delay: 600 },
      { phase: 'action', label: 'Action: Escalate to User', detail: 'Push notification: "Your agent\'s order (₹7,200) exceeds your ₹5,000 limit. Approve the higher amount or let the agent adjust the cart?"', delay: 700 },
    ],
  },
  {
    id: 'consumed-credential',
    title: 'Consumed Payment Credential',
    desc: 'One-time payment token was already used or replayed',
    icon: '🔑',
    color: '#7A5AF8',
    example: 'Agent retries a failed x402 payment but the one-time credential (EIP-3009 nonce) was already consumed by the first attempt',
    steps: [
      { phase: 'trigger', label: 'Agent Payment Attempt', detail: 'Agent retries ₹1,299 payment using same x402 credential. Nonce: 0x8f3a...b2c1 (already consumed).', delay: 500 },
      { phase: 'diagnose', label: 'Failure-Layer Diagnosis', detail: 'Error: CREDENTIAL_CONSUMED | Protocol: x402 | Nonce collision: 0x8f3a...b2c1 used at T-45s | Idempotency conflict', delay: 600 },
      { phase: 'reconcile', label: 'Reconciliation Check', detail: 'First attempt status: SETTLED (₹1,299 captured). The original payment actually succeeded. This retry is a duplicate.', delay: 600 },
      { phase: 'policy', label: 'Policy Decision', detail: 'Original payment confirmed captured → this is a duplicate attempt, not a failure. No recovery needed. Mark as already_recovered.', delay: 600 },
      { phase: 'action', label: 'Action: Stop — Already Paid', detail: 'Suppress retry. Update agent\'s state: payment_id pay_x402_8f3a confirmed. Prevent double-charge. Log for audit.', delay: 600 },
    ],
  },
  {
    id: 'untrusted-agent',
    title: 'Untrusted Agent Identity',
    desc: 'Payment gateway rejects the agent because it cannot verify its identity or authorization chain',
    icon: '🛡',
    color: '#528FF0',
    example: 'A merchant\'s custom AI agent attempts payment but its Agent Studio identity token fails verification at the PSP',
    steps: [
      { phase: 'trigger', label: 'Agent Payment Attempt', detail: 'Custom merchant agent submits ₹15,000 B2B payment. Agent ID: agent_studio_m7k2. PSP rejects.', delay: 500 },
      { phase: 'diagnose', label: 'Failure-Layer Diagnosis', detail: 'Error: AGENT_IDENTITY_REJECTED | Agent: agent_studio_m7k2 | Reason: identity token signature invalid / not in trusted registry', delay: 600 },
      { phase: 'reconcile', label: 'Reconciliation Check', detail: 'Payment rejected pre-authorization. No funds at risk. Agent identity issue is upstream of money movement.', delay: 500 },
      { phase: 'policy', label: 'Policy Decision', detail: 'Identity failure is NOT retryable with same credential. Could be: expired signing key, revoked agent, or replay attack. Must not retry.', delay: 700 },
      { phase: 'action', label: 'Action: Stop + Escalate to Merchant', detail: 'Block all retries for this agent. Alert merchant: "Agent m7k2 identity rejected by PSP — verify signing keys in Agent Studio settings."', delay: 700 },
    ],
  },
  {
    id: 'psp-timeout',
    title: 'PSP Timeout — Unknown Settlement',
    desc: 'Payment timed out at the PSP and we don\'t know if money was captured or not',
    icon: '⚠',
    color: '#F79009',
    example: 'Agent payment to a food delivery service times out at the payment gateway — did the money move or not?',
    steps: [
      { phase: 'trigger', label: 'Agent Payment Attempt', detail: 'Agent submits ₹849 food delivery payment. PSP response: HTTP 504 Gateway Timeout after 30s.', delay: 500 },
      { phase: 'diagnose', label: 'Failure-Layer Diagnosis', detail: 'Error: PSP_TIMEOUT | Gateway: Razorpay | Order: order_M8k2p | Settlement status: UNKNOWN — could be captured or failed', delay: 700 },
      { phase: 'reconcile', label: 'Reconciliation Check', detail: 'Querying PSP settlement API... order_M8k2p status: "created" (not captured). Checking bank: no debit on instrument. SAFE to retry.', delay: 800 },
      { phase: 'policy', label: 'Policy Decision', detail: 'Confirmed no capture → safe retry with fresh idempotency key. Wait 60s for gateway recovery. Use same payment method.', delay: 600 },
      { phase: 'action', label: 'Action: Safe Retry (New Idempotency Key)', detail: 'Retry ₹849 with idem_key: order_M8k2p:retry:1. If second timeout → escalate to user. Never retry without settlement verification.', delay: 700 },
    ],
  },
  {
    id: 'delivery-mismatch',
    title: 'Payment Succeeded, Service Delivery Failed',
    desc: 'The x402 payment went through but the service/product was never delivered to the agent',
    icon: '📦',
    color: '#12B76A',
    example: 'Agent pays ₹2,499 for an API service via x402 but receives HTTP 500 — money was taken but service was not delivered',
    steps: [
      { phase: 'trigger', label: 'Payment + Service Call', detail: 'Agent sends x402 payment (₹2,499) for premium API access. Payment: SETTLED. Service response: HTTP 500 Internal Server Error.', delay: 500 },
      { phase: 'diagnose', label: 'Failure-Layer Diagnosis', detail: 'Payment layer: SUCCESS (₹2,499 captured). Service layer: FAILED (500). Mismatch: money moved but value not delivered.', delay: 700 },
      { phase: 'reconcile', label: 'Reconciliation Check', detail: 'Verify: payment_id x402_p9k3 settled at ₹2,499. Service endpoint returned 500 — no API key/token issued. Customer owes nothing more.', delay: 600 },
      { phase: 'policy', label: 'Policy Decision', detail: 'Payment succeeded but delivery failed → this is a refund/re-delivery case, not a payment retry. Wait for service recovery, then retry delivery.', delay: 700 },
      { phase: 'action', label: 'Action: Retry Delivery, Then Refund', detail: 'Retry service call 3x over 5 minutes. If still failing → initiate automated refund of ₹2,499. Log: "paid but undelivered" for dispute evidence.', delay: 700 },
    ],
  },
]

const PHASE_CONFIG = {
  trigger: { label: 'TRIGGER', color: '#6366F1', bg: '#EEF2FF', border: '#C7D2FE' },
  diagnose: { label: 'DIAGNOSE', color: '#B42318', bg: '#FEF3F2', border: '#FECDCA' },
  reconcile: { label: 'RECONCILE', color: '#F79009', bg: '#FFFAEB', border: '#FDE68A' },
  policy: { label: 'POLICY', color: '#528FF0', bg: '#EFF8FF', border: '#B2DDFF' },
  action: { label: 'ACTION', color: '#12B76A', bg: '#ECFDF3', border: '#A6F4C5' },
}

function PipelineStep({ step, visible }) {
  if (!visible) return null
  const phase = PHASE_CONFIG[step.phase]
  return (
    <div style={{
      display: 'flex', gap: 12, padding: '10px 14px', margin: '6px 0',
      background: phase.bg, border: `1px solid ${phase.border}`, borderRadius: 8,
      animation: 'fadeSlideIn 0.3s ease-out',
    }}>
      <div style={{ flexShrink: 0, paddingTop: 1 }}>
        <span style={{
          display: 'inline-block', padding: '2px 8px', borderRadius: 4,
          fontSize: 10, fontWeight: 700, letterSpacing: '0.05em',
          background: phase.color, color: '#fff',
        }}>
          {phase.label}
        </span>
      </div>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ fontSize: 13, fontWeight: 600, color: '#1A1A1A', marginBottom: 2 }}>{step.label}</div>
        <div style={{ fontSize: 12, color: '#4B5563', lineHeight: 1.5, fontFamily: "'SF Mono', 'Cascadia Code', 'Consolas', monospace" }}>
          {step.detail}
        </div>
      </div>
    </div>
  )
}

function FailureScenario({ failure }) {
  const [visibleSteps, setVisibleSteps] = useState(0)
  const [playing, setPlaying] = useState(false)
  const [done, setDone] = useState(false)
  const logRef = useRef(null)
  const timeoutsRef = useRef([])

  const reset = useCallback(() => {
    timeoutsRef.current.forEach(clearTimeout)
    timeoutsRef.current = []
    setVisibleSteps(0)
    setPlaying(false)
    setDone(false)
  }, [])

  const play = useCallback(() => {
    reset()
    setPlaying(true)
    let cumulative = 0
    failure.steps.forEach((step, i) => {
      cumulative += step.delay
      const t = setTimeout(() => {
        setVisibleSteps(i + 1)
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

  useEffect(() => {
    if (logRef.current) logRef.current.scrollTop = logRef.current.scrollHeight
  }, [visibleSteps])

  return (
    <div style={{ ...CARD, overflow: 'hidden' }}>
      <div style={{
        padding: '14px 18px',
        borderBottom: '1px solid #E8EAED',
        display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 12,
      }}>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
            <span style={{
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              width: 32, height: 32, borderRadius: 8,
              background: `${failure.color}12`, fontSize: 16, flexShrink: 0,
            }}>
              {failure.icon}
            </span>
            <div style={{ fontSize: 14, fontWeight: 600, color: '#1A1A1A' }}>{failure.title}</div>
          </div>
          <div style={{ fontSize: 12, color: '#6B7280', marginBottom: 4 }}>{failure.desc}</div>
          <div style={{ fontSize: 11, color: '#9CA3AF', fontStyle: 'italic', lineHeight: 1.4 }}>
            Scenario: {failure.example}
          </div>
        </div>
        <div style={{ display: 'flex', gap: 6, flexShrink: 0, paddingTop: 2 }}>
          {done && (
            <button onClick={reset} style={{
              padding: '5px 10px', fontSize: 11, fontWeight: 500,
              border: '1px solid #E8EAED', borderRadius: 6,
              background: '#fff', color: '#374151', cursor: 'pointer', fontFamily: 'inherit',
            }}>
              Reset
            </button>
          )}
          <button
            onClick={play}
            disabled={playing}
            style={{
              padding: '5px 14px', fontSize: 11, fontWeight: 600,
              border: 'none', borderRadius: 6,
              background: playing ? '#94A3B8' : failure.color,
              color: '#fff', cursor: playing ? 'not-allowed' : 'pointer',
              fontFamily: 'inherit', display: 'flex', alignItems: 'center', gap: 5,
            }}
          >
            {playing ? (
              <>
                <span style={{ display: 'inline-block', width: 5, height: 5, borderRadius: '50%', background: '#fff', animation: 'pulse 1s infinite' }} />
                Running...
              </>
            ) : done ? 'Replay' : 'Run Scenario'}
          </button>
        </div>
      </div>
      <div
        ref={logRef}
        style={{ padding: '10px 14px', minHeight: 200, maxHeight: 340, overflowY: 'auto', background: '#FAFBFC' }}
      >
        {visibleSteps === 0 && !playing && (
          <div style={{
            height: 200, display: 'flex', flexDirection: 'column',
            alignItems: 'center', justifyContent: 'center', color: '#9CA3AF',
          }}>
            <span style={{ fontSize: 24, marginBottom: 8, opacity: 0.4 }}>{failure.icon}</span>
            <span style={{ fontSize: 12 }}>Click "Run Scenario" to trace the recovery pipeline</span>
          </div>
        )}
        {failure.steps.map((step, i) => (
          <PipelineStep key={i} step={step} visible={i < visibleSteps} />
        ))}
      </div>
    </div>
  )
}

function PipelineOverview() {
  const phases = [
    { label: 'Agent Payment', color: '#6366F1', desc: 'AI agent initiates payment on behalf of user' },
    { label: 'Failure Diagnosis', color: '#B42318', desc: 'Identify which layer failed and why' },
    { label: 'Reconciliation', color: '#F79009', desc: 'Verify: did money actually move?' },
    { label: 'Policy Check', color: '#528FF0', desc: 'Deterministic rules decide the action' },
    { label: 'Recovery Action', color: '#12B76A', desc: 'Retry / Re-auth / Refund / Escalate / Stop' },
  ]
  return (
    <div style={{ ...CARD, padding: '16px 18px' }}>
      <div style={{ fontSize: 13, fontWeight: 600, color: '#1A1A1A', marginBottom: 4 }}>Recovery Pipeline for Agent Payments</div>
      <div style={{ fontSize: 11, color: '#6B7280', marginBottom: 14 }}>
        Every failed agent payment flows through this deterministic pipeline — no human in the loop
      </div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 0, overflowX: 'auto', paddingBottom: 4 }}>
        {phases.map((p, i) => (
          <div key={p.label} style={{ display: 'flex', alignItems: 'center', flexShrink: 0 }}>
            <div style={{
              padding: '10px 14px', borderRadius: 8, minWidth: 115, textAlign: 'center',
              background: `${p.color}10`, border: `1px solid ${p.color}30`,
            }}>
              <div style={{ fontSize: 11, fontWeight: 700, color: p.color, marginBottom: 3 }}>{p.label}</div>
              <div style={{ fontSize: 10, color: '#6B7280', lineHeight: 1.3 }}>{p.desc}</div>
            </div>
            {i < phases.length - 1 && (
              <div style={{ padding: '0 5px', color: '#D1D5DB', fontSize: 14, flexShrink: 0 }}>→</div>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}

function AgenticContext() {
  return (
    <div style={{ ...CARD, padding: '18px 20px', background: 'linear-gradient(135deg, #1A1A2E 0%, #16213E 100%)' }}>
      <div style={{ fontSize: 14, fontWeight: 600, color: '#fff', marginBottom: 6 }}>
        Why Agent Payments Fail Differently
      </div>
      <div style={{ fontSize: 12, color: '#94A3B8', lineHeight: 1.6, marginBottom: 16 }}>
        When AI agents make payments — ChatGPT Operator purchasing items, Amazon Rufus buying on behalf of users,
        or Razorpay Agent Studio agents executing B2B transactions — the failure modes are fundamentally different
        from human-initiated payments. Mandates expire, delegated spending limits are exceeded, one-time credentials
        get consumed, agent identities fail verification, and payments can succeed while service delivery fails.
        Traditional retry-and-nudge recovery doesn't work here. You need deterministic diagnosis, settlement
        verification, and policy-driven actions — not a WhatsApp message.
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 12 }}>
        {[
          { label: 'Protocols', items: ['Visa TAP', 'x402', 'AP2 Mandates', 'Agentic Commerce Protocol'] },
          { label: 'Agents Making Payments', items: ['ChatGPT Operator', 'Amazon Rufus', 'Razorpay Agent Studio', 'Custom merchant agents'] },
          { label: 'Recovery Actions', items: ['Safe retry (new idem key)', 'Request re-authorization', 'Automated refund', 'Escalate to user', 'Stop (fraud/identity)'] },
        ].map((col, i) => (
          <div key={i} style={{ padding: '10px 12px', borderRadius: 6, background: 'rgba(255,255,255,0.06)', border: '1px solid rgba(255,255,255,0.1)' }}>
            <div style={{ fontSize: 11, fontWeight: 600, color: '#fff', marginBottom: 6 }}>{col.label}</div>
            {col.items.map((item, j) => (
              <div key={j} style={{ fontSize: 11, color: '#94A3B8', lineHeight: 1.6, paddingLeft: 8, position: 'relative' }}>
                <span style={{ position: 'absolute', left: 0, color: '#528FF0' }}>·</span>
                {item}
              </div>
            ))}
          </div>
        ))}
      </div>
    </div>
  )
}

function RazorpayFit() {
  return (
    <div style={{ ...CARD, padding: '18px 20px', background: 'linear-gradient(135deg, #0F3460 0%, #1A1A2E 100%)' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 10 }}>
        <span style={{ fontSize: 20 }}>🚀</span>
        <div>
          <div style={{ fontSize: 14, fontWeight: 600, color: '#fff' }}>Recovery Router as Razorpay's Agent Payment Safety Layer</div>
          <div style={{ fontSize: 11, color: '#94A3B8', marginTop: 2 }}>
            How this extends into Razorpay's agentic ecosystem
          </div>
        </div>
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 12, marginTop: 12 }}>
        {[
          { title: 'Vulcan AI', desc: 'Vulcan scores payment routes for success probability. When an agent payment still fails, Recovery Router diagnoses and recovers — handling what Vulcan couldn\'t prevent.' },
          { title: 'Agent Studio', desc: 'Agent Studio agents execute payments. Recovery Router catches their failures — expired mandates, limit overages, identity rejections — and routes to the right recovery action.' },
          { title: 'MCP Server', desc: 'Recovery analytics for agent payments exposed via MCP Server — letting AI assistants query failure patterns, settlement status, and recovery outcomes in conversation.' },
        ].map((item, i) => (
          <div key={i} style={{ padding: '12px 14px', borderRadius: 8, background: 'rgba(255,255,255,0.07)', border: '1px solid rgba(255,255,255,0.1)' }}>
            <div style={{ fontSize: 12, fontWeight: 600, color: '#fff', marginBottom: 4 }}>{item.title}</div>
            <div style={{ fontSize: 11, color: '#94A3B8', lineHeight: 1.5 }}>{item.desc}</div>
          </div>
        ))}
      </div>
    </div>
  )
}

export default function AgenticDemoPage() {
  return (
    <div style={{ padding: '24px 28px' }}>
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

      <div style={{ marginBottom: 20 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 6 }}>
          <h1 style={{ fontSize: 18, fontWeight: 600, color: '#1A1A1A', margin: 0 }}>
            Our Next Stop: Agentic Payment Recovery
          </h1>
          <span style={{
            padding: '2px 8px', fontSize: 11, fontWeight: 600,
            background: '#EFF8FF', color: '#528FF0', borderRadius: 4,
          }}>
            CONCEPT
          </span>
        </div>
        <p style={{ fontSize: 13, color: '#6B7280', margin: '0 0 4px', maxWidth: 760, lineHeight: 1.6 }}>
          AI agents are starting to make payments — ChatGPT Operator, Amazon Rufus, Razorpay Agent Studio.
          When those agent-initiated payments fail, the failure modes are different from human payments:
          expired mandates, exceeded delegation limits, consumed credentials, untrusted agent identities,
          and payments that succeed while delivery fails.
          Recovery Router's next evolution is becoming the safety and recovery layer for this new class of failures.
        </p>
        <p style={{ fontSize: 11, color: '#9CA3AF', margin: 0, fontStyle: 'italic' }}>
          Interactive concept with synthetic data — not currently implemented. Demonstrates Recovery Router's future direction.
        </p>
      </div>

      <AgenticContext />

      <div style={{ marginTop: 16 }}>
        <PipelineOverview />
      </div>

      <div style={{ marginTop: 20, marginBottom: 10 }}>
        <h2 style={{ fontSize: 15, fontWeight: 600, color: '#1A1A1A', margin: '0 0 4px' }}>Agent Payment Failure Scenarios</h2>
        <p style={{ fontSize: 12, color: '#6B7280', margin: 0 }}>
          Click "Run Scenario" to trace how Recovery Router diagnoses and recovers each failure type
        </p>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 14, marginBottom: 20 }}>
        {FAILURE_TYPES.map(f => (
          <FailureScenario key={f.id} failure={f} />
        ))}
      </div>

      <RazorpayFit />
    </div>
  )
}
