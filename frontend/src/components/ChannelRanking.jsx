const CHANNEL_META = {
  whatsapp: { label: 'WhatsApp', icon: '💬' },
  email: { label: 'Email', icon: '✉️' },
  sms: { label: 'SMS', icon: '📱' },
  none: { label: 'No Action', icon: '⏸️' },
  unknown: { label: 'Unclassified', icon: '❔' },
}

export default function ChannelRanking({ channelRanking }) {
  const ranking = (channelRanking || []).filter((c) => c.total > 0)
  const maxRate = Math.max(...ranking.map((c) => c.recovery_rate), 1)

  return (
    <div className="rounded-xl p-6 border" style={{ background: 'var(--bg-card)', borderColor: 'var(--border)' }}>
      <h3 className="text-lg font-semibold mb-1" style={{ color: 'var(--text-primary)' }}>
        Channel Performance
      </h3>
      <p className="text-xs mb-4" style={{ color: 'var(--text-secondary)' }}>
        Ranked by recovery rate — the router learns which channel wins per failure type
      </p>

      {ranking.length === 0 ? (
        <p className="text-sm py-6 text-center" style={{ color: 'var(--text-secondary)' }}>
          No channel data yet.
        </p>
      ) : (
        <div className="space-y-4">
          {ranking.map((c, i) => {
            const meta = CHANNEL_META[c.channel] || { label: c.channel, icon: '•' }
            return (
              <div key={c.channel}>
                <div className="flex items-center justify-between mb-1.5">
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-mono w-4" style={{ color: 'var(--text-secondary)' }}>
                      #{i + 1}
                    </span>
                    <span>{meta.icon}</span>
                    <span className="text-sm font-medium" style={{ color: 'var(--text-primary)' }}>
                      {meta.label}
                    </span>
                  </div>
                  <div className="flex items-center gap-3 text-sm">
                    <span style={{ color: 'var(--text-secondary)' }}>
                      {c.recovered}/{c.total}
                    </span>
                    <span className="font-semibold w-12 text-right" style={{ color: 'var(--accent)' }}>
                      {c.recovery_rate}%
                    </span>
                  </div>
                </div>
                <div className="w-full rounded-full h-2" style={{ background: 'var(--border)' }}>
                  <div
                    className="rounded-full h-2 transition-all duration-500"
                    style={{
                      width: `${(c.recovery_rate / maxRate) * 100}%`,
                      background: i === 0 ? 'var(--success)' : 'var(--accent)',
                    }}
                  />
                </div>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
