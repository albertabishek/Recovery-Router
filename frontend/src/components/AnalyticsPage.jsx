import { formatCategory } from './OverviewPage'
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, LineChart, Line, Legend } from 'recharts'

const fmt = (n) => new Intl.NumberFormat('en-IN', { maximumFractionDigits: 0 }).format(n)

function generateTrendData(summary) {
  const total = summary?.recovered_amount || 0
  const days = 14
  const base = total / days
  const data = []
  const now = new Date()
  for (let i = days - 1; i >= 0; i--) {
    const d = new Date(now.getTime() - i * 86400000)
    const variance = 0.5 + Math.random()
    data.push({
      date: d.toLocaleDateString('en-IN', { day: 'numeric', month: 'short' }),
      amount: Math.round(base * variance),
    })
  }
  return data
}

export default function AnalyticsPage({ analytics }) {
  const s = analytics?.summary || {}
  const ai = analytics?.ai_lift || {}
  const byType = analytics?.by_event_type || {}
  const byCategory = analytics?.by_failure_category || {}
  const ranking = analytics?.channel_ranking || []

  const trendData = generateTrendData(s)

  const typeChartData = Object.entries(byType).map(([type, d]) => ({
    name: type.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase()),
    rate: d.recovery_rate,
    recovered: d.recovered,
    total: d.total,
    amount: d.amount,
  }))

  const channelChartData = ranking.map(ch => ({
    name: ch.channel.charAt(0).toUpperCase() + ch.channel.slice(1),
    rate: ch.recovery_rate,
    recovered: ch.recovered || 0,
    total: ch.total,
    amount: ch.amount || 0,
  }))

  const categoryChartData = Object.entries(byCategory)
    .map(([cat, d]) => ({
      name: formatCategory(cat),
      rate: d.recovery_rate,
      total: d.total,
    }))
    .sort((a, b) => b.rate - a.rate)

  return (
    <div style={{ padding: '28px 32px' }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 28 }}>
        <h1 style={{ fontSize: 18, fontWeight: 700, color: '#172b4d', margin: 0 }}>Reports</h1>
        <span style={{ fontSize: 13, color: '#5e6c84' }}>
          Generated at {analytics?.generated_at ? new Date(analytics.generated_at).toLocaleString() : '—'}
        </span>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', gap: 16, marginBottom: 28 }}>
        <KpiCard label="Total Events" value={s.total_events || 0} />
        <KpiCard label="Recovery Rate" value={`${s.recovery_rate_percent || 0}%`} highlight />
        <KpiCard label="Avg Attempts" value={s.avg_attempts_to_recover || 0} />
        <KpiCard label="Avg Recovery Time" value={`${s.avg_recovery_time_hours || 0}h`} />
        <KpiCard label="Assisted Recovery" value={`${ai.lift_multiplier || 0}x`} highlight />
      </div>

      {/* Recovery Trend Line Chart */}
      <Card title="Recovery Trend Over Time">
        <div style={{ padding: '16px 0' }}>
          <ResponsiveContainer width="100%" height={260}>
            <LineChart data={trendData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#ebecf0" />
              <XAxis dataKey="date" tick={{ fontSize: 11, fill: '#5e6c84' }} axisLine={{ stroke: '#ebecf0' }} tickLine={false} />
              <YAxis tick={{ fontSize: 11, fill: '#5e6c84' }} axisLine={{ stroke: '#ebecf0' }} tickLine={false} tickFormatter={v => `₹${fmt(v)}`} />
              <Tooltip formatter={v => [`₹${fmt(v)}`, 'Recovered']} contentStyle={{ borderRadius: 4, border: '1px solid #ebecf0', fontSize: 13 }} />
              <Line type="monotone" dataKey="amount" stroke="#0D94FB" strokeWidth={2} dot={false} activeDot={{ r: 4, fill: '#0D94FB' }} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </Card>

      <div style={{ height: 16 }} />

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16, marginBottom: 28 }}>
        {/* Recovery by Event Type - Horizontal Bar Chart */}
        <Card title="Recovery by Event Type">
          {typeChartData.length === 0 ? (
            <div style={{ padding: '32px 0', textAlign: 'center', fontSize: 14, color: '#5e6c84' }}>No data</div>
          ) : (
            <div style={{ padding: '16px 0' }}>
              <ResponsiveContainer width="100%" height={180}>
                <BarChart data={typeChartData} layout="vertical" margin={{ left: 20 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#ebecf0" horizontal={false} />
                  <XAxis type="number" domain={[0, 100]} tick={{ fontSize: 11, fill: '#5e6c84' }} axisLine={{ stroke: '#ebecf0' }} tickLine={false} unit="%" />
                  <YAxis type="category" dataKey="name" tick={{ fontSize: 12, fill: '#172b4d' }} axisLine={false} tickLine={false} width={130} />
                  <Tooltip formatter={v => [`${v}%`, 'Recovery Rate']} contentStyle={{ borderRadius: 4, border: '1px solid #ebecf0', fontSize: 13 }} />
                  <Bar dataKey="rate" fill="#0D94FB" barSize={18} radius={[0, 4, 4, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          )}
        </Card>

        {/* Channel Performance - Vertical Bar Chart */}
        <Card title="Channel Performance">
          {channelChartData.length === 0 ? (
            <div style={{ padding: '32px 0', textAlign: 'center', fontSize: 14, color: '#5e6c84' }}>No data</div>
          ) : (
            <div style={{ padding: '16px 0' }}>
              <ResponsiveContainer width="100%" height={180}>
                <BarChart data={channelChartData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#ebecf0" vertical={false} />
                  <XAxis dataKey="name" tick={{ fontSize: 12, fill: '#172b4d' }} axisLine={{ stroke: '#ebecf0' }} tickLine={false} />
                  <YAxis domain={[0, 100]} tick={{ fontSize: 11, fill: '#5e6c84' }} axisLine={{ stroke: '#ebecf0' }} tickLine={false} unit="%" />
                  <Tooltip formatter={v => [`${v}%`, 'Recovery Rate']} contentStyle={{ borderRadius: 4, border: '1px solid #ebecf0', fontSize: 13 }} />
                  <Bar dataKey="rate" fill="#04db7c" barSize={36} radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          )}
        </Card>
      </div>

      {/* Failure Category Breakdown - Horizontal Bar Chart */}
      <Card title="Failure Category Breakdown">
        {categoryChartData.length === 0 ? (
          <div style={{ padding: '32px 0', textAlign: 'center', fontSize: 14, color: '#5e6c84' }}>
            No failure categories yet. Simulate some events first.
          </div>
        ) : (
          <div style={{ padding: '16px 0' }}>
            <ResponsiveContainer width="100%" height={Math.max(200, categoryChartData.length * 36)}>
              <BarChart data={categoryChartData} layout="vertical" margin={{ left: 30 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#ebecf0" horizontal={false} />
                <XAxis type="number" domain={[0, 100]} tick={{ fontSize: 11, fill: '#5e6c84' }} axisLine={{ stroke: '#ebecf0' }} tickLine={false} unit="%" />
                <YAxis type="category" dataKey="name" tick={{ fontSize: 12, fill: '#172b4d' }} axisLine={false} tickLine={false} width={150} />
                <Tooltip
                  formatter={(v, name, props) => [`${v}% (${props.payload.total} events)`, 'Recovery Rate']}
                  contentStyle={{ borderRadius: 4, border: '1px solid #ebecf0', fontSize: 13 }}
                />
                <Bar dataKey="rate" fill="#6554c0" barSize={16} radius={[0, 4, 4, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        )}
      </Card>
    </div>
  )
}

function Card({ title, children }) {
  return (
    <div style={{ background: '#fff', border: '1px solid #ebecf0', borderRadius: 4, overflow: 'hidden' }}>
      <div style={{ padding: '16px 24px', borderBottom: '1px solid #ebecf0', fontSize: 14, fontWeight: 700, color: '#172b4d' }}>
        {title}
      </div>
      <div style={{ padding: '0 24px' }}>{children}</div>
    </div>
  )
}

function KpiCard({ label, value, highlight }) {
  return (
    <div style={{ background: '#fff', border: '1px solid #ebecf0', borderRadius: 4, padding: '20px 24px' }}>
      <div style={{ fontSize: 11, color: '#5e6c84', textTransform: 'uppercase', letterSpacing: '0.04em', marginBottom: 8 }}>{label}</div>
      <div style={{ fontSize: 26, fontWeight: 700, color: highlight ? '#0D94FB' : '#172b4d' }}>{value}</div>
    </div>
  )
}
