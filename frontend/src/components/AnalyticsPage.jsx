import { formatCategory } from './OverviewPage'

const fmt = (n) => new Intl.NumberFormat('en-IN', { maximumFractionDigits: 0 }).format(n)

export default function AnalyticsPage({ analytics }) {
  const s = analytics?.summary || {}
  const ai = analytics?.ai_lift || {}
  const byType = analytics?.by_event_type || {}
  const _byChannel = analytics?.by_channel || {}
  const byCategory = analytics?.by_failure_category || {}
  const ranking = analytics?.channel_ranking || []

  return (
    <div style={{ padding: '28px 32px' }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 28 }}>
        <h1 style={{ fontSize: 18, fontWeight: 600, color: '#1A1A1A', margin: 0 }}>Reports</h1>
        <span style={{ fontSize: 13, color: '#6B7280' }}>
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

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16, marginBottom: 28 }}>
        <Card title="Recovery by Event Type">
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr>
                {['Type', 'Events', 'Amount', 'Recovered', 'Rate'].map(h => (
                  <th key={h} style={thStyle}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {Object.entries(byType).map(([type, d]) => (
                <tr key={type} style={{ borderBottom: '1px solid #E8EAED' }}>
                  <td style={tdStyle}><span style={{ textTransform: 'capitalize' }}>{type.replace(/_/g, ' ')}</span></td>
                  <td style={tdStyle}>{d.total}</td>
                  <td style={tdStyle}>₹{fmt(d.amount)}</td>
                  <td style={tdStyle}>{d.recovered}</td>
                  <td style={{ ...tdStyle, fontWeight: 600, color: '#528FF0' }}>{d.recovery_rate}%</td>
                </tr>
              ))}
              {Object.keys(byType).length === 0 && (
                <tr><td colSpan={5} style={{ ...tdStyle, textAlign: 'center', color: '#6B7280' }}>No data</td></tr>
              )}
            </tbody>
          </table>
        </Card>

        <Card title="Channel Performance">
          {ranking.length === 0 ? (
            <div style={{ padding: '32px 0', textAlign: 'center', fontSize: 14, color: '#6B7280' }}>No data</div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 16, padding: '8px 0' }}>
              {ranking.map((ch, i) => {
                const maxRate = Math.max(...ranking.map(c => c.recovery_rate), 1)
                return (
                  <div key={ch.channel}>
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 6 }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                        <span style={{
                          width: 22, height: 22, borderRadius: '50%',
                          background: i === 0 ? '#ECFDF3' : '#F7F8FA',
                          color: i === 0 ? '#027A48' : '#6B7280',
                          display: 'flex', alignItems: 'center', justifyContent: 'center',
                          fontSize: 11, fontWeight: 700,
                        }}>{i + 1}</span>
                        <span style={{ fontSize: 14, fontWeight: 500, color: '#1A1A1A', textTransform: 'capitalize' }}>{ch.channel}</span>
                      </div>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                        <span style={{ fontSize: 13, color: '#6B7280' }}>{ch.recovered || 0}/{ch.total} · ₹{fmt(ch.amount || 0)}</span>
                        <span style={{ fontSize: 14, fontWeight: 700, color: '#528FF0', width: 44, textAlign: 'right' }}>{ch.recovery_rate}%</span>
                      </div>
                    </div>
                    <div style={{ height: 6, background: '#E8EAED', borderRadius: 3 }}>
                      <div style={{
                        height: 6, borderRadius: 3,
                        width: `${(ch.recovery_rate / maxRate) * 100}%`,
                        background: i === 0 ? '#12B76A' : '#528FF0',
                        transition: 'width 0.4s',
                      }} />
                    </div>
                  </div>
                )
              })}
            </div>
          )}
        </Card>
      </div>

      <Card title="Failure Category Breakdown">
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(220px, 1fr))', gap: 14, padding: '8px 0' }}>
          {Object.entries(byCategory).map(([cat, d]) => (
            <div key={cat} style={{ padding: '14px 18px', border: '1px solid #E8EAED', borderRadius: 8 }}>
              <div style={{ fontSize: 14, fontWeight: 500, color: '#1A1A1A', marginBottom: 10 }}>
                {formatCategory(cat)}
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 13, color: '#6B7280' }}>
                <span>{d.total} events</span>
                <span style={{ fontWeight: 600, color: '#528FF0' }}>{d.recovery_rate}%</span>
              </div>
              <div style={{ height: 4, background: '#E8EAED', borderRadius: 2, marginTop: 10 }}>
                <div style={{ height: 4, borderRadius: 2, background: '#528FF0', width: `${Math.min(d.recovery_rate, 100)}%` }} />
              </div>
            </div>
          ))}
          {Object.keys(byCategory).length === 0 && (
            <div style={{ padding: '32px 0', textAlign: 'center', fontSize: 14, color: '#6B7280', gridColumn: '1 / -1' }}>
              No failure categories yet. Simulate some events first.
            </div>
          )}
        </div>
      </Card>
    </div>
  )
}

function Card({ title, children }) {
  return (
    <div style={{ background: '#fff', border: '1px solid #E8EAED', borderRadius: 8, overflow: 'hidden' }}>
      <div style={{ padding: '16px 24px', borderBottom: '1px solid #E8EAED', fontSize: 14, fontWeight: 600, color: '#1A1A1A' }}>
        {title}
      </div>
      <div style={{ padding: '0 24px' }}>{children}</div>
    </div>
  )
}

function KpiCard({ label, value, highlight }) {
  return (
    <div style={{ background: '#fff', border: '1px solid #E8EAED', borderRadius: 8, padding: '20px 24px' }}>
      <div style={{ fontSize: 11, color: '#6B7280', textTransform: 'uppercase', letterSpacing: '0.04em', marginBottom: 8 }}>{label}</div>
      <div style={{ fontSize: 26, fontWeight: 700, color: highlight ? '#528FF0' : '#1A1A1A' }}>{value}</div>
    </div>
  )
}

const thStyle = {
  padding: '12px 14px', fontSize: 12, fontWeight: 600,
  color: '#6B7280', textAlign: 'left',
  textTransform: 'uppercase', letterSpacing: '0.04em',
  borderBottom: '1px solid #E8EAED',
}

const tdStyle = { padding: '12px 14px', fontSize: 14 }
