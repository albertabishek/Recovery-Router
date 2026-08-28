const BASE = `${import.meta.env.VITE_API_BASE || ''}/api`

let _onStart = null
let _onDone = null

export function setLoadingHooks(onStart, onDone) {
  _onStart = onStart
  _onDone = onDone
}

async function apiFetch(url, opts) {
  _onStart?.()
  try {
    const res = await fetch(url, opts)
    if (!res.ok) throw new Error(`API error: ${res.status}`)
    return res.json()
  } finally {
    _onDone?.()
  }
}

export async function fetchAnalytics(params = {}) {
  const qs = new URLSearchParams(params).toString()
  return apiFetch(`${BASE}/analytics${qs ? '?' + qs : ''}`)
}

export async function fetchEvents(params = {}) {
  const qs = new URLSearchParams(params).toString()
  return apiFetch(`${BASE}/events${qs ? '?' + qs : ''}`)
}

export async function simulateEvent(eventType, scenario, customer = {}) {
  const body = { event_type: eventType, scenario }
  if (customer.name) body.customer_name = customer.name
  if (customer.email) body.customer_email = customer.email
  if (customer.phone) body.customer_phone = customer.phone
  return apiFetch(`${BASE}/simulate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
}

export async function fetchHealth() {
  return apiFetch(`${BASE}/health`)
}

export async function fetchAuditLogs(params = {}) {
  const qs = new URLSearchParams(params).toString()
  return apiFetch(`${BASE}/audit-logs${qs ? '?' + qs : ''}`)
}

export async function fetchEventTrace(eventId) {
  return apiFetch(`${BASE}/events/${eventId}/trace`)
}
