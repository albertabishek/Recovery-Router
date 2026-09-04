import { describe, it, expect, beforeEach, vi } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import App from '../App'
import { LoadingProvider } from '../components/LoadingBar'

vi.mock('../lib/api', async (importOriginal) => {
  const actual = await importOriginal()
  return {
    ...actual,
    getAuthToken: vi.fn(() => ''),
    login: vi.fn(),
    fetchAnalytics: vi.fn(() => Promise.resolve(null)),
    fetchEvents: vi.fn(() => Promise.resolve({ events: [] })),
  }
})

function renderApp() {
  return render(
    <LoadingProvider>
      <App />
    </LoadingProvider>
  )
}

describe('Login Page', () => {
  beforeEach(() => {
    sessionStorage.clear()
    vi.clearAllMocks()
  })

  it('renders login form when not authenticated', () => {
    renderApp()
    expect(screen.getByText('Recovery Router')).toBeInTheDocument()
    expect(screen.getByPlaceholderText('Password')).toBeInTheDocument()
    expect(screen.getByText('Sign In')).toBeInTheDocument()
  })

  it('disables sign in button when password is empty', () => {
    renderApp()
    const btn = screen.getByText('Sign In')
    expect(btn).toBeDisabled()
  })

  it('enables sign in button when password is entered', () => {
    renderApp()
    fireEvent.change(screen.getByPlaceholderText('Password'), { target: { value: 'test' } })
    expect(screen.getByText('Sign In')).not.toBeDisabled()
  })

  it('shows error on failed login', async () => {
    const { login } = await import('../lib/api')
    login.mockResolvedValue(false)

    renderApp()
    fireEvent.change(screen.getByPlaceholderText('Password'), { target: { value: 'wrong' } })
    fireEvent.click(screen.getByText('Sign In'))

    await waitFor(() => {
      expect(screen.getByText('Invalid password')).toBeInTheDocument()
    })
  })

  it('has password input with type password', () => {
    renderApp()
    const input = screen.getByPlaceholderText('Password')
    expect(input).toHaveAttribute('type', 'password')
  })
})
