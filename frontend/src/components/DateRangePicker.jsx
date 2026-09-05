import { useState, useRef, useEffect } from 'react'

const PRESETS = [
  { id: 'today', label: 'Today' },
  { id: 'yesterday', label: 'Yesterday' },
  { id: '7d', label: 'Last 7 Days' },
  { id: '30d', label: 'Last 30 Days' },
  { id: 'all', label: 'All Time' },
]

function toDateStr(d) {
  return d.toISOString().slice(0, 10)
}

function resolvePreset(id) {
  const now = new Date()
  const today = toDateStr(now)
  const yesterday = toDateStr(new Date(now.getTime() - 86400000))

  switch (id) {
    case 'today':
      return { from_date: today, to_date: today }
    case 'yesterday':
      return { from_date: yesterday, to_date: yesterday }
    case '7d':
      return { from_date: toDateStr(new Date(now.getTime() - 7 * 86400000)), to_date: today }
    case '30d':
      return { from_date: toDateStr(new Date(now.getTime() - 30 * 86400000)), to_date: today }
    case 'all':
    default:
      return { from_date: '', to_date: '' }
  }
}

export function getDateParams(dateRange) {
  const params = {}
  if (dateRange.from_date) params.from_date = dateRange.from_date
  if (dateRange.to_date) params.to_date = dateRange.to_date
  return params
}

export function getPresetLabel(dateRange) {
  if (!dateRange.from_date && !dateRange.to_date) return 'All Time'
  const now = new Date()
  const today = toDateStr(now)
  const yesterday = toDateStr(new Date(now.getTime() - 86400000))

  if (dateRange.from_date === today && dateRange.to_date === today) return 'Today'
  if (dateRange.from_date === yesterday && dateRange.to_date === yesterday) return 'Yesterday'

  const d7 = toDateStr(new Date(now.getTime() - 7 * 86400000))
  if (dateRange.from_date === d7 && dateRange.to_date === today) return 'Last 7 Days'

  const d30 = toDateStr(new Date(now.getTime() - 30 * 86400000))
  if (dateRange.from_date === d30 && dateRange.to_date === today) return 'Last 30 Days'

  if (dateRange.from_date && dateRange.to_date) {
    return `${dateRange.from_date} — ${dateRange.to_date}`
  }
  if (dateRange.from_date) return `From ${dateRange.from_date}`
  return `Until ${dateRange.to_date}`
}

export default function DateRangePicker({ value, onChange }) {
  const [open, setOpen] = useState(false)
  const [customFrom, setCustomFrom] = useState(value.from_date || '')
  const [customTo, setCustomTo] = useState(value.to_date || '')
  const ref = useRef(null)

  useEffect(() => {
    const handler = (e) => {
      if (ref.current && !ref.current.contains(e.target)) setOpen(false)
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [])

  useEffect(() => {
    setCustomFrom(value.from_date || '')
    setCustomTo(value.to_date || '')
  }, [value])

  const label = getPresetLabel(value)

  const applyPreset = (id) => {
    onChange(resolvePreset(id))
    setOpen(false)
  }

  const applyCustom = () => {
    onChange({ from_date: customFrom, to_date: customTo })
    setOpen(false)
  }

  return (
    <div ref={ref} style={{ position: 'relative', display: 'inline-block' }}>
      <button
        onClick={() => setOpen(v => !v)}
        style={{
          display: 'flex', alignItems: 'center', gap: 8,
          padding: '7px 14px', background: '#fff',
          border: '1px solid #ebecf0', borderRadius: 4,
          fontSize: 13, fontWeight: 500, color: '#172b4d',
          cursor: 'pointer', fontFamily: 'inherit',
          whiteSpace: 'nowrap',
        }}
      >
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#5e6c84" strokeWidth="2">
          <rect x="3" y="4" width="18" height="18" rx="2" />
          <line x1="16" y1="2" x2="16" y2="6" /><line x1="8" y1="2" x2="8" y2="6" />
          <line x1="3" y1="10" x2="21" y2="10" />
        </svg>
        {label}
        <svg width="10" height="10" viewBox="0 0 12 12" fill="none"
          style={{ transform: open ? 'rotate(180deg)' : 'rotate(0)', transition: 'transform 0.15s' }}>
          <path d="M2.5 4.5L6 8l3.5-3.5" stroke="#5e6c84" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
        </svg>
      </button>

      {open && (
        <div style={{
          position: 'absolute', top: '100%', right: 0, marginTop: 4,
          background: '#fff', border: '1px solid #ebecf0', borderRadius: 6,
          boxShadow: '0 4px 16px rgba(0,0,0,0.10)', zIndex: 50,
          padding: 8, minWidth: 240,
        }}>
          {PRESETS.map(p => (
            <button
              key={p.id}
              onClick={() => applyPreset(p.id)}
              style={{
                display: 'block', width: '100%', textAlign: 'left',
                padding: '8px 12px', fontSize: 13, fontWeight: 500,
                color: '#172b4d', background: 'none', border: 'none',
                borderRadius: 6, cursor: 'pointer', fontFamily: 'inherit',
              }}
              onMouseEnter={e => e.currentTarget.style.background = '#f4f5f7'}
              onMouseLeave={e => e.currentTarget.style.background = 'none'}
            >
              {p.label}
            </button>
          ))}

          <div style={{
            borderTop: '1px solid #ebecf0', margin: '6px 0', padding: '10px 12px 4px',
          }}>
            <div style={{ fontSize: 11, fontWeight: 600, color: '#5e6c84', textTransform: 'uppercase', letterSpacing: '0.04em', marginBottom: 8 }}>
              Custom Range
            </div>
            <div style={{ display: 'flex', gap: 8, marginBottom: 8 }}>
              <input
                type="date"
                value={customFrom}
                onChange={e => setCustomFrom(e.target.value)}
                style={{
                  flex: 1, padding: '6px 8px', border: '1px solid #ebecf0',
                  borderRadius: 6, fontSize: 12, fontFamily: 'inherit', color: '#172b4d',
                }}
              />
              <input
                type="date"
                value={customTo}
                onChange={e => setCustomTo(e.target.value)}
                style={{
                  flex: 1, padding: '6px 8px', border: '1px solid #ebecf0',
                  borderRadius: 6, fontSize: 12, fontFamily: 'inherit', color: '#172b4d',
                }}
              />
            </div>
            <button
              onClick={applyCustom}
              style={{
                width: '100%', padding: '7px 0', background: '#0D94FB', color: '#fff',
                border: 'none', borderRadius: 6, fontSize: 13, fontWeight: 500,
                cursor: 'pointer', fontFamily: 'inherit',
              }}
            >
              Apply
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
