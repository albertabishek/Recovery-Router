import { Component, useCallback, useEffect, useRef, useState } from 'react'
import { fetchAnalytics, fetchEvents, setLoadingHooks, setAuthErrorHandler, getAuthToken, login as apiLogin, clearAuthToken } from './lib/api'
import Layout from './components/Layout'
import OverviewPage from './components/OverviewPage'
import EventsPage from './components/EventsPage'
import AnalyticsPage from './components/AnalyticsPage'
import SimulatorPage from './components/SimulatorPage'
import AuditLogsPage from './components/AuditLogsPage'
import { getDateParams } from './components/DateRangePicker'
import { useLoading } from './components/LoadingBar'

class ErrorBoundary extends Component {
  constructor(props) {
    super(props)
    this.state = { hasError: false, error: null }
  }
  static getDerivedStateFromError(error) {
    return { hasError: true, error }
  }
  render() {
    if (this.state.hasError) {
      return (
        <div style={{ padding: 40, textAlign: 'center' }}>
          <h2 style={{ color: '#B42318', marginBottom: 12 }}>Something went wrong</h2>
          <p style={{ color: '#6B7280', marginBottom: 20 }}>{this.state.error?.message || 'An unexpected error occurred'}</p>
          <button onClick={() => { this.setState({ hasError: false, error: null }); window.location.reload() }}
            style={{ padding: '8px 20px', background: '#528FF0', color: '#fff', border: 'none', borderRadius: 6, cursor: 'pointer' }}>
            Reload
          </button>
        </div>
      )
    }
    return this.props.children
  }
}

function LoginPage({ onLogin }) {
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      const ok = await apiLogin(password)
      if (ok) {
        onLogin()
      } else {
        setError('Invalid password')
      }
    } catch {
      setError('Connection failed')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={{
      minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center',
      background: 'linear-gradient(135deg, #1A1A2E 0%, #16213E 50%, #0F3460 100%)',
    }}>
      <form onSubmit={handleSubmit} style={{
        background: '#fff', borderRadius: 16, padding: '48px 40px', width: 400,
        boxShadow: '0 20px 60px rgba(0,0,0,0.3)', textAlign: 'center',
      }}>
        <div style={{ fontSize: 36, marginBottom: 8 }}>🔐</div>
        <h1 style={{ fontSize: 22, fontWeight: 700, color: '#1A1A2E', margin: '0 0 8px' }}>Recovery Router</h1>
        <p style={{ fontSize: 14, color: '#6B7280', margin: '0 0 28px' }}>Enter your password to access the dashboard</p>
        <input
          type="password"
          value={password}
          onChange={e => setPassword(e.target.value)}
          placeholder="Password"
          autoFocus
          style={{
            width: '100%', padding: '12px 16px', fontSize: 15, border: '1px solid #D0D5DD',
            borderRadius: 8, outline: 'none', boxSizing: 'border-box', marginBottom: 16,
            fontFamily: 'inherit',
          }}
        />
        {error && <p style={{ color: '#B42318', fontSize: 13, margin: '0 0 12px' }}>{error}</p>}
        <button
          type="submit"
          disabled={loading || !password}
          style={{
            width: '100%', padding: '12px 0', fontSize: 15, fontWeight: 600,
            color: '#fff', background: loading || !password ? '#94A3B8' : '#528FF0',
            border: 'none', borderRadius: 8, cursor: loading ? 'not-allowed' : 'pointer',
            fontFamily: 'inherit',
          }}
        >
          {loading ? 'Signing in...' : 'Sign In'}
        </button>
      </form>
    </div>
  )
}

export default function App() {
  const { start, done } = useLoading()
  const [authed, setAuthed] = useState(!!getAuthToken())

  useEffect(() => { setLoadingHooks(start, done) }, [start, done])
  useEffect(() => { setAuthErrorHandler(() => setAuthed(false)) }, [])

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
    if (!authed) return
    load()
    timerRef.current = setInterval(load, 30000)
    return () => clearInterval(timerRef.current)
  }, [load, authed])

  const navigate = useCallback((target, eventId) => {
    setPage(target)
    if (eventId) setSelectedEventId(eventId)
    else setSelectedEventId(null)
  }, [])

  const onSimulated = useCallback(() => {
    setTimeout(load, 2000)
    setTimeout(load, 6000)
  }, [load])

  if (!authed) {
    return <LoginPage onLogin={() => setAuthed(true)} />
  }

  return (
    <ErrorBoundary>
      <Layout activePage={page} onNavigate={navigate} dateRange={dateRange} onDateChange={setDateRange} onLogout={() => { clearAuthToken(); setAuthed(false) }}>
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
    </ErrorBoundary>
  )
}
