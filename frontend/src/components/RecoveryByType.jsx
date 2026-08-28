const TYPE_CONFIG = {
  payment_failure: { label: 'Payment Failures', icon: '💳' },
  cart_abandonment: { label: 'Cart Abandonment', icon: '🛒' },
  invoice_overdue: { label: 'Invoice Overdue', icon: '📄' },
}

export default function RecoveryByType({ byEventType }) {
  const fmt = (n) => new Intl.NumberFormat('en-IN', { maximumFractionDigits: 0 }).format(n)

  return (
    <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
      {Object.entries(TYPE_CONFIG).map(([key, config]) => {
        const data = byEventType[key] || { total: 0, recovered: 0, amount: 0, recovery_rate: 0 }
        return (
          <div key={key} className="rounded-xl p-5 border"
            style={{ background: 'var(--bg-card)', borderColor: 'var(--border)' }}>
            <div className="flex items-center gap-2 mb-3">
              <span className="text-xl">{config.icon}</span>
              <span className="text-sm font-medium" style={{ color: 'var(--text-primary)' }}>
                {config.label}
              </span>
            </div>
            <div className="space-y-2">
              <div className="flex justify-between text-sm">
                <span style={{ color: 'var(--text-secondary)' }}>Events</span>
                <span className="font-medium" style={{ color: 'var(--text-primary)' }}>{data.total}</span>
              </div>
              <div className="flex justify-between text-sm">
                <span style={{ color: 'var(--text-secondary)' }}>Amount</span>
                <span className="font-medium" style={{ color: 'var(--text-primary)' }}>₹{fmt(data.amount)}</span>
              </div>
              <div className="flex justify-between text-sm">
                <span style={{ color: 'var(--text-secondary)' }}>Recovery Rate</span>
                <span className="font-semibold" style={{ color: 'var(--accent)' }}>{data.recovery_rate}%</span>
              </div>
            </div>
          </div>
        )
      })}
    </div>
  )
}
