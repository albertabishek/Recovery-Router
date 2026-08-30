const BASE = `${import.meta.env.VITE_API_BASE || ''}/api`

let _onStart = null
let _onDone = null
let _onAuthError = null

export function setLoadingHooks(onStart, onDone) {
  _onStart = onStart
  _onDone = onDone
}

export function setAuthErrorHandler(handler) {
  _onAuthError = handler
}

export function getAuthToken() {
  return sessionStorage.getItem('rr_auth_token') || ''
}

export function setAuthToken(token) {
  sessionStorage.setItem('rr_auth_token', token)
}

export function clearAuthToken() {
  sessionStorage.removeItem('rr_auth_token')
}

export async function login(password) {
  const res = await fetch(`${BASE}/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ password }),
  })
  const data = await res.json()
  if (data.status === 'ok') {
    setAuthToken(data.token)
    return true
  }
  return false
}

function authHeaders() {
  const token = getAuthToken()
  if (!token) return {}
  return { Authorization: `Bearer ${token}` }
}

async function apiFetch(url, opts = {}) {
  _onStart?.()
  try {
    const headers = { ...authHeaders(), ...(opts.headers || {}) }
    const res = await fetch(url, { ...opts, headers })
    if (res.status === 401) {
      clearAuthToken()
      _onAuthError?.()
      throw new Error('Unauthorized')
    }
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

export async function fetchEventCounts(params = {}) {
  const qs = new URLSearchParams(params).toString()
  return apiFetch(`${BASE}/events/counts${qs ? '?' + qs : ''}`)
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

export async function createLiveCheckout(data) {
  return apiFetch(`${BASE}/live-checkout`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  })
}

export async function controlEvent(eventId, action) {
  return apiFetch(`${BASE}/events/${eventId}/control`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ action }),
  })
}
