export default function AILift({ aiLift }) {
  const fmt = (n) => new Intl.NumberFormat('en-IN', { maximumFractionDigits: 0 }).format(n)

  return (
    <div className="rounded-xl p-6 border" style={{ background: 'var(--bg-card)', borderColor: 'var(--border)' }}>
      <h3 className="text-lg font-semibold" style={{ color: 'var(--text-primary)' }}>
        Observed Recovery vs Industry Baseline
      </h3>
      <p className="text-xs mb-4" style={{ color: 'var(--text-secondary)' }}>
        {aiLift.baseline_source || 'Industry baseline: 15-20% recovery via simple retries (Razorpay blog)'}
      </p>
      <div className="grid grid-cols-2 gap-6">
        <div>
          <p className="text-sm" style={{ color: 'var(--text-secondary)' }}>Razorpay Baseline</p>
          <p className="text-2xl font-bold" style={{ color: 'var(--text-secondary)' }}>
            {aiLift.baseline_rate_percent}%
          </p>
          <div className="w-full rounded-full h-3 mt-2" style={{ background: 'var(--border)' }}>
            <div
              className="rounded-full h-3"
              style={{
                width: `${Math.min(aiLift.baseline_rate_percent, 100)}%`,
                background: 'var(--text-secondary)',
              }}
            />
          </div>
        </div>
        <div>
          <p className="text-sm" style={{ color: 'var(--accent)' }}>Recovery Router</p>
          <p className="text-2xl font-bold" style={{ color: 'var(--accent)' }}>
            {aiLift.ai_recovery_rate_percent}%
          </p>
          <div className="w-full rounded-full h-3 mt-2" style={{ background: 'var(--border)' }}>
            <div
              className="rounded-full h-3"
              style={{
                width: `${Math.min(aiLift.ai_recovery_rate_percent, 100)}%`,
                background: 'var(--accent)',
              }}
            />
          </div>
        </div>
      </div>
      <div className="mt-4 pt-4" style={{ borderTop: '1px solid var(--border)' }}>
        <div className="flex justify-between text-sm">
          <span style={{ color: 'var(--text-secondary)' }}>Observed Improvement</span>
          <span
            className="font-semibold"
            style={{ color: aiLift.improvement_points >= 0 ? 'var(--success)' : 'var(--text-secondary)' }}
          >
            {aiLift.improvement_points >= 0 ? '+' : ''}{aiLift.improvement_points} pts ({aiLift.lift_multiplier}x lift)
          </span>
        </div>
        <div className="flex justify-between text-sm mt-1">
          <span style={{ color: 'var(--text-secondary)' }}>Observed Recovery Amount</span>
          <span className="font-semibold" style={{ color: 'var(--success)' }}>
            ₹{fmt(aiLift.additional_revenue_recovered)}
          </span>
        </div>
      </div>
    </div>
  )
}
