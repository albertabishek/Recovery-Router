import { useCallback, useEffect, useRef, useState } from 'react'
import { fetchAnalytics, fetchEvents } from '../lib/api'
import StatTiles from './StatTiles'
import AILift from './AILift'
import RecoveryByType from './RecoveryByType'
import ChannelRanking from './ChannelRanking'
import LiveFeed from './LiveFeed'
import SimulatorPanel from './SimulatorPanel'
import HealthBadge from './HealthBadge'

const EMPTY_ANALYTICS = {
  summary: {
    total_events: 0, recovered_count: 0, pending_count: 0, exhausted_count: 0,
    no_action_count: 0, recovery_rate_percent: 0, total_amount: 0,
    recovered_amount: 0, pending_amount: 0, avg_attempts_to_recover: 0,
    avg_recovery_time_hours: 0,
  },
  ai_lift: {
    baseline_rate_percent: 17.5, ai_recovery_rate_percent: 0,
    improvement_points: 0, lift_multiplier: 0, additional_revenue_recovered: 0,
  },
  by_event_type: {},
  by_channel: {},
  channel_ranking: [],
  by_failure_category: {},
}

export default function Dashboard() {
  const [analytics, setAnalytics] = useState(EMPTY_ANALYTICS)
  const [events, setEvents] = useState([])
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(true)
  const timerRef = useRef(null)

  const load = useCallback(async () => {
    try {
      const [a, e] = await Promise.all([fetchAnalytics(), fetchEvents({ limit: 50 })])
      setAnalytics(a)
      setEvents(e.events || [])
      setError(null)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    load()
    timerRef.current = setInterval(load, 15000)
    return () => clearInterval(timerRef.current)
  }, [load])

  // After a simulate, the Celery task needs a moment before the row lands.
  const onSimulated = useCallback(() => {
    setTimeout(load, 3000)
    setTimeout(load, 8000)
  }, [load])

  return (
    <div className="min-h-screen" style={{ background: 'var(--bg-primary)' }}>
      <header
        className="sticky top-0 z-10 backdrop-blur"
        style={{ borderBottom: '1px solid var(--border)', background: 'color-mix(in srgb, var(--bg-primary) 85%, transparent)' }}
      >
        <div className="max-w-7xl mx-auto px-6 py-4 flex items-center justify-between">
          <div>
            <h1 className="text-xl font-bold tracking-tight" style={{ color: 'var(--text-primary)' }}>
              Recovery Router
            </h1>
            <p className="text-xs" style={{ color: 'var(--text-secondary)' }}>
              One engine. Every revenue leak — classified, routed, recovered.
            </p>
          </div>
          <div className="flex items-center gap-3">
            {loading && (
              <span className="text-xs" style={{ color: 'var(--text-secondary)' }}>syncing…</span>
            )}
            <HealthBadge />
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-6 py-6 space-y-6">
        {error && (
          <div
            className="rounded-lg px-4 py-3 text-sm border"
            style={{ borderColor: 'var(--danger)', color: 'var(--danger)', background: 'var(--bg-card)' }}
          >
            Backend unreachable: {error}
          </div>
        )}

        <StatTiles summary={analytics.summary} />

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <AILift aiLift={analytics.ai_lift} />
          <ChannelRanking channelRanking={analytics.channel_ranking} />
        </div>

        <RecoveryByType byEventType={analytics.by_event_type} />

        <LiveFeed events={events} />

        <SimulatorPanel onSimulated={onSimulated} />

        <footer className="pt-4 pb-8 text-center text-xs" style={{ color: 'var(--text-secondary)' }}>
          Razorpay AI Buildathon · Track 3 · Recovery Router
        </footer>
      </main>
    </div>
  )
}
