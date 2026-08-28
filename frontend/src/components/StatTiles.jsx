export default function StatTiles({ summary }) {
  const fmt = (n) => new Intl.NumberFormat('en-IN', { maximumFractionDigits: 0 }).format(n)

  return (
    <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
      <div className="rounded-xl p-6 border" style={{ background: 'var(--bg-card)', borderColor: 'var(--border)' }}>
        <p className="text-sm font-medium" style={{ color: 'var(--danger)' }}>Revenue at Risk</p>
        <p className="text-3xl font-bold mt-1" style={{ color: 'var(--text-primary)' }}>
          ₹{fmt(summary.total_amount)}
        </p>
        <p className="text-sm mt-1" style={{ color: 'var(--text-secondary)' }}>
          {summary.total_events} events
        </p>
      </div>

      <div className="rounded-xl p-6 border" style={{ background: 'var(--bg-card)', borderColor: 'var(--border)' }}>
        <p className="text-sm font-medium" style={{ color: 'var(--success)' }}>Revenue Recovered</p>
        <p className="text-3xl font-bold mt-1" style={{ color: 'var(--text-primary)' }}>
          ₹{fmt(summary.recovered_amount)}
        </p>
        <p className="text-sm mt-1" style={{ color: 'var(--text-secondary)' }}>
          {summary.recovered_count} recovered
        </p>
      </div>

      <div className="rounded-xl p-6 border" style={{ background: 'var(--bg-card)', borderColor: 'var(--border)' }}>
        <p className="text-sm font-medium" style={{ color: 'var(--accent)' }}>Recovery Rate</p>
        <p className="text-3xl font-bold mt-1" style={{ color: 'var(--text-primary)' }}>
          {summary.recovery_rate_percent}%
        </p>
        <p className="text-sm mt-1" style={{ color: 'var(--text-secondary)' }}>
          avg {summary.avg_attempts_to_recover} attempts
        </p>
      </div>
    </div>
  )
}
