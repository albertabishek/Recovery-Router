import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import AgenticDemoPage from '../components/AgenticDemoPage'

describe('AgenticDemoPage', () => {
  it('renders the page heading', () => {
    render(<AgenticDemoPage />)
    expect(screen.getByText(/Agentic Payment Recovery/)).toBeInTheDocument()
  })

  it('renders all 6 failure scenario cards', () => {
    render(<AgenticDemoPage />)
    expect(screen.getAllByText('Expired Mandate').length).toBeGreaterThanOrEqual(1)
    expect(screen.getAllByText('Delegation Exceeded').length).toBeGreaterThanOrEqual(1)
    expect(screen.getAllByText('Credential Consumed').length).toBeGreaterThanOrEqual(1)
    expect(screen.getAllByText('Identity Rejected').length).toBeGreaterThanOrEqual(1)
    expect(screen.getAllByText('Unknown Settlement').length).toBeGreaterThanOrEqual(1)
    expect(screen.getAllByText('Paid but Undelivered').length).toBeGreaterThanOrEqual(1)
  })

  it('renders the pipeline overview with all 5 phases', () => {
    render(<AgenticDemoPage />)
    expect(screen.getAllByText('Detect').length).toBeGreaterThanOrEqual(1)
    expect(screen.getAllByText('Diagnose').length).toBeGreaterThanOrEqual(1)
    expect(screen.getAllByText('Verify').length).toBeGreaterThanOrEqual(1)
    expect(screen.getAllByText('Decide').length).toBeGreaterThanOrEqual(1)
    expect(screen.getAllByText('Recover').length).toBeGreaterThanOrEqual(1)
  })

  it('renders Run Scenario button', () => {
    render(<AgenticDemoPage />)
    const button = screen.getByText('Run Scenario')
    expect(button).toBeInTheDocument()
  })

  it('shows prompt text before running a scenario', () => {
    render(<AgenticDemoPage />)
    const prompt = screen.getByText(/Click "Run Scenario" to watch/)
    expect(prompt).toBeInTheDocument()
  })

  it('starts animation when Run Scenario is clicked', async () => {
    render(<AgenticDemoPage />)
    const button = screen.getByText('Run Scenario')
    fireEvent.click(button)
    await waitFor(() => {
      expect(screen.getByText(/Processing/)).toBeInTheDocument()
    })
  })

  it('shows pipeline steps after animation completes', async () => {
    vi.useFakeTimers()
    render(<AgenticDemoPage />)
    const button = screen.getByText('Run Scenario')

    fireEvent.click(button)
    await vi.runAllTimersAsync()

    expect(screen.getByText(/Payment Attempt|Retry Attempt|Payment \+ Service/)).toBeInTheDocument()
    vi.useRealTimers()
  })

  it('renders the How It Works section', () => {
    render(<AgenticDemoPage />)
    expect(screen.getByText('How It Works')).toBeInTheDocument()
  })

  it('renders Razorpay ecosystem fit section', () => {
    render(<AgenticDemoPage />)
    expect(screen.getByText('Razorpay Ecosystem Fit')).toBeInTheDocument()
  })
})
