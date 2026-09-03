import { useState, useEffect, useRef, useCallback } from 'react'

const CARD = {
  background: '#fff',
  border: '1px solid #E8EAED',
  borderRadius: 8,
}

const SCENARIOS = [
  {
    id: 'conversational',
    title: 'Conversational Recovery Agent',
    subtitle: 'The agent talks to the customer — not just at them',
    icon: '💬',
    color: '#528FF0',
    steps: [
      { type: 'system', text: 'UPI payment of ₹4,999 timed out for Ravi Kumar', delay: 600 },
      { type: 'agent-think', text: 'Classifying... UPI timeout → 85% recovery probability → WhatsApp immediate', delay: 1200 },
      { type: 'agent', text: 'Hi Ravi, your ₹4,999 payment didn\'t go through — looks like a network glitch. Tap here to retry: rzp.io/r/abc123', delay: 800 },
      { type: 'customer', text: 'I tried again but it\'s still failing 😕', delay: 1500 },
      { type: 'agent-think', text: 'Customer retry detected → payment.failed webhook received → same error_code TIMEOUT → bank issue likely', delay: 1000 },
      { type: 'agent', text: 'Looks like your bank\'s UPI is having issues right now. Want me to send you a card payment link instead? Same amount, no extra charges.', delay: 800 },
      { type: 'customer', text: 'Yes please', delay: 1200 },
      { type: 'agent-think', text: 'Creating Razorpay payment link with card method preference...', delay: 800 },
      { type: 'agent', text: 'Here you go: rzp.io/r/def456 — this one works with any card or net banking 👆', delay: 600 },
      { type: 'system', text: '✅ Payment captured — ₹4,999 recovered via card after UPI failure', delay: 1500 },
    ],
  },
  {
    id: 'crosschannel',
    title: 'Cross-Channel Intelligence',
    subtitle: 'Detect engagement signals, adapt the approach in real-time',
    icon: '🔀',
    color: '#12B76A',
    steps: [
      { type: 'system', text: 'Card expired for Priya Sharma — ₹8,499 payment failed', delay: 600 },
      { type: 'agent-think', text: 'Card expired → 50% probability → Email (needs card update instructions)', delay: 1000 },
      { type: 'channel', channel: 'email', status: 'sent', text: 'Email sent: "Update your card to complete your ₹8,499 payment"', delay: 800 },
      { type: 'signal', text: '📧 Email opened at 2:34 PM — but no click on payment link after 15 minutes', delay: 2000 },
      { type: 'agent-think', text: 'Open-without-click pattern detected → customer saw it but didn\'t act → needs shorter, more direct nudge → switch to WhatsApp', delay: 1200 },
      { type: 'channel', channel: 'whatsapp', status: 'sent', text: 'WhatsApp: "Hi Priya, quick one — your card on file expired. Tap to pay with a new card: rzp.io/r/ghi789"', delay: 800 },
      { type: 'signal', text: '📱 Link clicked at 2:52 PM — customer on checkout page', delay: 1500 },
      { type: 'system', text: '✅ Payment captured — ₹8,499 recovered. Channel switch: email → WhatsApp. Time: 18 minutes.', delay: 1200 },
      { type: 'learn', text: '🧠 Learning: For card_expired + email-open-no-click, WhatsApp follow-up has 73% conversion', delay: 800 },
    ],
  },
  {
    id: 'predictive',
    title: 'Predictive Pre-Recovery',
    subtitle: 'Detect patterns before they become problems',
    icon: '🔮',
    color: '#F79009',
    steps: [
      { type: 'signal', text: '⚠️ 14 UPI failures from HDFC Bank in last 30 minutes (normal: 2/hour)', delay: 800 },
      { type: 'agent-think', text: 'Anomaly detected → bank downtime pattern → HDFC UPI likely down', delay: 1000 },
      { type: 'system', text: '⏸️ Pausing all HDFC recovery attempts — sending now would waste the attempt budget', delay: 800 },
      { type: 'agent-think', text: 'Monitoring HDFC gateway... checking every 5 minutes...', delay: 2000 },
      { type: 'signal', text: '🟢 HDFC UPI success rate back to 98% — outage cleared after 47 minutes', delay: 1500 },
      { type: 'system', text: '▶️ Resuming 14 paused recoveries — sending WhatsApp with "Your bank is back online, tap to retry"', delay: 1000 },
      { type: 'agent-think', text: 'Timing recovery to 2 minutes after outage clears — customer\'s session is likely still warm', delay: 800 },
      { type: 'channel', channel: 'whatsapp', status: 'sent', text: '14 WhatsApp messages sent in batch — personalized with original amounts', delay: 800 },
      { type: 'system', text: '✅ 11 of 14 payments recovered (78.5%) — ₹67,493 total. Without prediction: ~4 recovered (28%).', delay: 1500 },
      { type: 'learn', text: '🧠 Pattern saved: HDFC UPI outages cluster between 1-3 PM on high-load days', delay: 800 },
    ],
  },
]

function ChatBubble({ step, visible }) {
  if (!visible) return null

  const baseStyle = {
    padding: '10px 14px',
    borderRadius: 12,
    fontSize: 13,
    lineHeight: 1.5,
    maxWidth: '85%',
    animation: 'fadeSlideIn 0.3s ease-out',
    wordBreak: 'break-word',
  }

  if (step.type === 'system') {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', margin: '8px 0' }}>
        <div style={{
          ...baseStyle,
          background: step.text.startsWith('✅') ? '#ECFDF3' : step.text.startsWith('⏸') ? '#FEF3F2' : step.text.startsWith('▶') ? '#EFF8FF' : '#F3F4F6',
          color: step.text.startsWith('✅') ? '#027A48' : step.text.startsWith('⏸') ? '#B42318' : '#374151',
          maxWidth: '90%', textAlign: 'center', fontWeight: 500, fontSize: 12,
          border: step.text.startsWith('✅') ? '1px solid #A6F4C5' : '1px solid #E5E7EB',
        }}>
          {step.text}
        </div>
      </div>
    )
  }

  if (step.type === 'agent-think') {
    return (
      <div style={{ display: 'flex', justifyContent: 'flex-start', margin: '6px 0' }}>
        <div style={{
          ...baseStyle,
          background: '#F0F4FF',
          color: '#4B5563',
          fontSize: 12,
          fontStyle: 'italic',
          border: '1px dashed #C7D2FE',
          display: 'flex', alignItems: 'center', gap: 6,
        }}>
          <span style={{ fontSize: 14 }}>🤖</span> {step.text}
        </div>
      </div>
    )
  }

  if (step.type === 'agent') {
    return (
      <div style={{ display: 'flex', justifyContent: 'flex-start', margin: '6px 0' }}>
        <div style={{
          ...baseStyle,
          background: '#528FF0',
          color: '#fff',
          borderBottomLeftRadius: 4,
        }}>
          {step.text}
        </div>
      </div>
    )
  }

  if (step.type === 'customer') {
    return (
      <div style={{ display: 'flex', justifyContent: 'flex-end', margin: '6px 0' }}>
        <div style={{
          ...baseStyle,
          background: '#F3F4F6',
          color: '#1A1A1A',
          borderBottomRightRadius: 4,
        }}>
          {step.text}
        </div>
      </div>
    )
  }

  if (step.type === 'channel') {
    return (
      <div style={{ display: 'flex', justifyContent: 'flex-start', margin: '6px 0' }}>
        <div style={{
          ...baseStyle,
          background: '#fff',
          border: '1px solid #E8EAED',
          color: '#374151',
          display: 'flex', alignItems: 'center', gap: 8,
        }}>
          <span style={{
            display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
            width: 22, height: 22, borderRadius: 4, fontSize: 11, fontWeight: 600,
            background: step.channel === 'whatsapp' ? '#25D366' : step.channel === 'email' ? '#528FF0' : '#F79009',
            color: '#fff',
          }}>
            {step.channel === 'whatsapp' ? 'WA' : step.channel === 'email' ? '✉' : 'SM'}
          </span>
          {step.text}
        </div>
      </div>
    )
  }

  if (step.type === 'signal') {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', margin: '8px 0' }}>
        <div style={{
          ...baseStyle,
          background: '#FFFAEB',
          color: '#93370D',
          border: '1px solid #FDE68A',
          maxWidth: '90%', textAlign: 'center', fontSize: 12,
        }}>
          {step.text}
        </div>
      </div>
    )
  }

  if (step.type === 'learn') {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', margin: '8px 0' }}>
        <div style={{
          ...baseStyle,
          background: '#F0FDF4',
          color: '#166534',
          border: '1px solid #BBF7D0',
          maxWidth: '90%', textAlign: 'center', fontSize: 12, fontWeight: 500,
        }}>
          {step.text}
        </div>
      </div>
    )
  }

  return null
}

function ScenarioPlayer({ scenario }) {
  const [visibleSteps, setVisibleSteps] = useState(0)
  const [playing, setPlaying] = useState(false)
  const [done, setDone] = useState(false)
  const chatRef = useRef(null)
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
    scenario.steps.forEach((step, i) => {
      cumulative += step.delay
      const t = setTimeout(() => {
        setVisibleSteps(i + 1)
        if (i === scenario.steps.length - 1) {
          setPlaying(false)
          setDone(true)
        }
      }, cumulative)
      timeoutsRef.current.push(t)
    })
  }, [scenario, reset])

  useEffect(() => {
    return () => timeoutsRef.current.forEach(clearTimeout)
  }, [])

  useEffect(() => {
    if (chatRef.current) {
      chatRef.current.scrollTop = chatRef.current.scrollHeight
    }
  }, [visibleSteps])

  return (
    <div style={{ ...CARD, overflow: 'hidden' }}>
      <div style={{
        padding: '20px 24px',
        borderBottom: '1px solid #E8EAED',
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <span style={{
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            width: 40, height: 40, borderRadius: 10,
            background: `${scenario.color}15`,
            fontSize: 20,
          }}>
            {scenario.icon}
          </span>
          <div>
            <div style={{ fontSize: 15, fontWeight: 600, color: '#1A1A1A' }}>{scenario.title}</div>
            <div style={{ fontSize: 12, color: '#6B7280', marginTop: 2 }}>{scenario.subtitle}</div>
          </div>
        </div>
        <div style={{ display: 'flex', gap: 8 }}>
          {done && (
            <button onClick={reset} style={{
              padding: '6px 14px', fontSize: 12, fontWeight: 500,
              border: '1px solid #E8EAED', borderRadius: 6,
              background: '#fff', color: '#374151', cursor: 'pointer',
              fontFamily: 'inherit',
            }}>
              Reset
            </button>
          )}
          <button
            onClick={play}
            disabled={playing}
            style={{
              padding: '6px 16px', fontSize: 12, fontWeight: 600,
              border: 'none', borderRadius: 6,
              background: playing ? '#94A3B8' : scenario.color,
              color: '#fff', cursor: playing ? 'not-allowed' : 'pointer',
              fontFamily: 'inherit',
              display: 'flex', alignItems: 'center', gap: 6,
            }}
          >
            {playing ? (
              <>
                <span style={{ display: 'inline-block', width: 6, height: 6, borderRadius: '50%', background: '#fff', animation: 'pulse 1s infinite' }} />
                Running...
              </>
            ) : done ? 'Replay' : 'Play Scenario'}
          </button>
        </div>
      </div>
      <div
        ref={chatRef}
        style={{
          padding: '16px 20px',
          height: 360,
          overflowY: 'auto',
          background: '#FAFBFC',
        }}
      >
        {visibleSteps === 0 && !playing && (
          <div style={{
            height: '100%', display: 'flex', flexDirection: 'column',
            alignItems: 'center', justifyContent: 'center', color: '#9CA3AF',
          }}>
            <span style={{ fontSize: 32, marginBottom: 12, opacity: 0.5 }}>{scenario.icon}</span>
            <span style={{ fontSize: 13 }}>Click "Play Scenario" to see the agent in action</span>
          </div>
        )}
        {scenario.steps.map((step, i) => (
          <ChatBubble key={i} step={step} visible={i < visibleSteps} />
        ))}
      </div>
    </div>
  )
}

function ComparisonTable() {
  const rows = [
    { feature: 'Channel selection', current: 'AI classifies, routes to best channel', agentic: 'Agent detects engagement signals, adapts in real-time' },
    { feature: 'Customer interaction', current: 'One-way: send message, wait', agentic: 'Two-way: agent reads replies, adjusts approach' },
    { feature: 'Failure handling', current: 'Retry with different provider', agentic: 'Understand why it failed, offer alternative payment method' },
    { feature: 'Timing', current: 'Rule-based delays (1h, 4h, etc.)', agentic: 'Predict optimal time from bank patterns + customer behavior' },
    { feature: 'Learning', current: 'Static rules + AI fallback', agentic: 'Continuous learning from every interaction' },
    { feature: 'Scope', current: 'Payment failures, carts, invoices', agentic: 'Same + subscriptions, mandates, recurring, refund recovery' },
  ]

  return (
    <div style={{ ...CARD, overflow: 'hidden' }}>
      <div style={{ padding: '20px 24px', borderBottom: '1px solid #E8EAED' }}>
        <div style={{ fontSize: 15, fontWeight: 600, color: '#1A1A1A' }}>Today vs. Agentic Future</div>
        <div style={{ fontSize: 12, color: '#6B7280', marginTop: 2 }}>What Recovery Router does now vs. what it becomes</div>
      </div>
      <div style={{ overflowX: 'auto' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
          <thead>
            <tr style={{ background: '#F9FAFB' }}>
              <th style={{ padding: '10px 16px', textAlign: 'left', fontWeight: 600, color: '#374151', borderBottom: '1px solid #E8EAED', width: '22%' }}>Capability</th>
              <th style={{ padding: '10px 16px', textAlign: 'left', fontWeight: 600, color: '#374151', borderBottom: '1px solid #E8EAED', width: '39%' }}>
                <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
                  <span style={{ width: 8, height: 8, borderRadius: '50%', background: '#528FF0', display: 'inline-block' }} />
                  Recovery Router Today
                </span>
              </th>
              <th style={{ padding: '10px 16px', textAlign: 'left', fontWeight: 600, color: '#374151', borderBottom: '1px solid #E8EAED', width: '39%' }}>
                <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
                  <span style={{ width: 8, height: 8, borderRadius: '50%', background: '#12B76A', display: 'inline-block' }} />
                  Agentic Recovery
                </span>
              </th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row, i) => (
              <tr key={i} style={{ borderBottom: '1px solid #F3F4F6' }}>
                <td style={{ padding: '10px 16px', fontWeight: 500, color: '#1A1A1A' }}>{row.feature}</td>
                <td style={{ padding: '10px 16px', color: '#6B7280' }}>{row.current}</td>
                <td style={{ padding: '10px 16px', color: '#027A48', fontWeight: 500 }}>{row.agentic}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

function MetricProjection() {
  const metrics = [
    { label: 'Recovery Rate', current: '~35%', projected: '~65%', icon: '📈' },
    { label: 'Avg Recovery Time', current: '~4 hours', projected: '~18 minutes', icon: '⚡' },
    { label: 'Channel Switches', current: 'Rule-based', projected: 'Signal-driven', icon: '🔀' },
    { label: 'Customer Satisfaction', current: 'Not measured', projected: 'NPS tracked per recovery', icon: '😊' },
  ]

  return (
    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 16 }}>
      {metrics.map((m, i) => (
        <div key={i} style={{ ...CARD, padding: '20px 16px', textAlign: 'center' }}>
          <div style={{ fontSize: 24, marginBottom: 8 }}>{m.icon}</div>
          <div style={{ fontSize: 12, fontWeight: 600, color: '#6B7280', marginBottom: 8, textTransform: 'uppercase', letterSpacing: '0.04em' }}>
            {m.label}
          </div>
          <div style={{ fontSize: 13, color: '#9CA3AF', marginBottom: 4 }}>{m.current}</div>
          <div style={{ fontSize: 10, color: '#D1D5DB', marginBottom: 4 }}>↓</div>
          <div style={{ fontSize: 15, fontWeight: 700, color: '#027A48' }}>{m.projected}</div>
        </div>
      ))}
    </div>
  )
}

export default function AgenticDemoPage() {
  return (
    <div style={{ padding: '28px 32px' }}>
      <style>{`
        @keyframes fadeSlideIn {
          from { opacity: 0; transform: translateY(8px); }
          to { opacity: 1; transform: translateY(0); }
        }
      `}</style>

      <div style={{ marginBottom: 28 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 6 }}>
          <h1 style={{ fontSize: 18, fontWeight: 600, color: '#1A1A1A', margin: 0 }}>
            Our Next Stop: Agentic Payment Recovery
          </h1>
          <span style={{
            padding: '2px 8px', fontSize: 11, fontWeight: 600,
            background: '#EFF8FF', color: '#528FF0', borderRadius: 4,
          }}>
            VISION
          </span>
        </div>
        <p style={{ fontSize: 14, color: '#6B7280', margin: 0, maxWidth: 720, lineHeight: 1.6 }}>
          Recovery Router today classifies, routes, and recovers autonomously. The next step: an agent that
          understands customer responses, detects engagement signals across channels, predicts bank outages
          before they cause failures, and learns from every interaction. Here's what that looks like.
        </p>
      </div>

      <MetricProjection />

      <div style={{ marginTop: 28, marginBottom: 12 }}>
        <h2 style={{ fontSize: 15, fontWeight: 600, color: '#1A1A1A', margin: '0 0 4px' }}>Interactive Scenarios</h2>
        <p style={{ fontSize: 13, color: '#6B7280', margin: 0 }}>Click "Play Scenario" to watch each agent capability in action</p>
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 20, marginBottom: 28 }}>
        {SCENARIOS.map(s => (
          <ScenarioPlayer key={s.id} scenario={s} />
        ))}
      </div>

      <ComparisonTable />

      <div style={{ ...CARD, padding: '24px 28px', marginTop: 20, background: 'linear-gradient(135deg, #1A1A2E 0%, #16213E 100%)' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 12 }}>
          <span style={{ fontSize: 24 }}>🚀</span>
          <div>
            <div style={{ fontSize: 15, fontWeight: 600, color: '#fff' }}>Built for Razorpay's Agentic Ecosystem</div>
            <div style={{ fontSize: 12, color: '#94A3B8', marginTop: 2 }}>
              Recovery Router is designed to plug into Razorpay's Agent Studio, Vulcan AI, and Sprint 2026 infrastructure
            </div>
          </div>
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 16, marginTop: 16 }}>
          {[
            { title: 'Vulcan AI Integration', desc: 'Replace OpenRouter with Razorpay\'s own payment-optimized AI model for classification and routing' },
            { title: 'Agent Studio Plugin', desc: 'Recovery Router as a drag-and-drop agent in Razorpay\'s Agent Studio — any merchant can enable it' },
            { title: 'MCP Server Extension', desc: 'Recovery analytics accessible via Razorpay\'s MCP Server for cashflow forecasting and AI conversations' },
          ].map((item, i) => (
            <div key={i} style={{ padding: '14px 16px', borderRadius: 8, background: 'rgba(255,255,255,0.08)', border: '1px solid rgba(255,255,255,0.12)' }}>
              <div style={{ fontSize: 13, fontWeight: 600, color: '#fff', marginBottom: 4 }}>{item.title}</div>
              <div style={{ fontSize: 12, color: '#94A3B8', lineHeight: 1.5 }}>{item.desc}</div>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
