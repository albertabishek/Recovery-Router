import { useCallback, useEffect, useRef, useState } from 'react'
import { fetchAnalytics, fetchEvents, setLoadingHooks } from './lib/api'
import { supabase } from './lib/supabase'
import Layout from './components/Layout'
import OverviewPage from './components/OverviewPage'
import EventsPage from './components/EventsPage'
import AnalyticsPage from './components/AnalyticsPage'
import SimulatorPage from './components/SimulatorPage'
import AuditLogsPage from './components/AuditLogsPage'
import { getDateParams } from './components/DateRangePicker'
import { useLoading } from './components/LoadingBar'

export default function App() {
  const { start, done } = useLoading()
  useEffect(() => { setLoadingHooks(start, done) }, [start, done])
  const [page, setPage] = useState('overview')
  const [selectedEventId, setSelectedEventId] = useState(null)
  const [analytics, setAnalytics] = useState(null)
  const [events, setEvents] = useState([])
  const [dateRange, setDateRange] = useState({ from_date: '', to_date: '' })
  const timerRef = useRef(null)

  const load = useCallback(async () => {
    try {
      const dp = getDateParams(dateRange)
      const [a, e] = await Promise.all([
        fetchAnalytics(dp),
        fetchEvents({ limit: 100, ...dp }),
      ])
      setAnalytics(a)
      setEvents(e.events || [])
    } catch (err) {
      console.error('Failed to load data:', err)
    }
  }, [dateRange])

  useEffect(() => {
    load()
    timerRef.current = setInterval(load, 60000)
    return () => clearInterval(timerRef.current)
  }, [load])

  useEffect(() => {
    const channel = supabase
      .channel('recovery-events-realtime')
      .on('postgres_changes', { event: '*', schema: 'public', table: 'recovery_events' }, (payload) => {
        if (payload.eventType === 'INSERT') {
          setEvents(prev => [payload.new, ...prev].slice(0, 100))
        } else if (payload.eventType === 'UPDATE') {
          setEvents(prev => prev.map(e => e.id === payload.new.id ? payload.new : e))
        }
      })
      .subscribe()

    return () => { supabase.removeChannel(channel) }
  }, [])

  const navigate = useCallback((target, eventId) => {
    setPage(target)
    if (eventId) setSelectedEventId(eventId)
    else setSelectedEventId(null)
  }, [])

  const onSimulated = useCallback(() => {
    setTimeout(load, 2000)
    setTimeout(load, 6000)
  }, [load])

  return (
    <Layout activePage={page} onNavigate={navigate} dateRange={dateRange} onDateChange={setDateRange}>
      {page === 'overview' && (
        <OverviewPage analytics={analytics} events={events} onNavigate={navigate} dateRange={dateRange} />
      )}
      {page === 'events' && (
        <EventsPage selectedEventId={selectedEventId} dateRange={dateRange} />
      )}
      {page === 'analytics' && (
        <AnalyticsPage analytics={analytics} />
      )}
      {page === 'simulator' && (
        <SimulatorPage events={events} onSimulated={onSimulated} />
      )}
      {page === 'audit-logs' && (
        <AuditLogsPage dateRange={dateRange} />
      )}
    </Layout>
  )
}
