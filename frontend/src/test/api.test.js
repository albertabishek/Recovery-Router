import { describe, it, expect, beforeEach } from 'vitest'
import { getAuthToken, setAuthToken, clearAuthToken } from '../lib/api'

describe('Auth token management', () => {
  beforeEach(() => {
    sessionStorage.clear()
  })

  it('returns empty string when no token', () => {
    expect(getAuthToken()).toBe('')
  })

  it('stores and retrieves token', () => {
    setAuthToken('test-token-123')
    expect(getAuthToken()).toBe('test-token-123')
  })

  it('clears token', () => {
    setAuthToken('token-to-clear')
    clearAuthToken()
    expect(getAuthToken()).toBe('')
  })

  it('overwrites existing token', () => {
    setAuthToken('first')
    setAuthToken('second')
    expect(getAuthToken()).toBe('second')
  })
})
