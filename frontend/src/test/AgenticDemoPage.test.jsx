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
    expect(screen.getByText('Expired Authorization Mandate')).toBeInTheDocument()
    expect(screen.getByText('Amount Exceeds Delegated Limit')).toBeInTheDocument()
    expect(screen.getByText('Consumed Payment Credential')).toBeInTheDocument()
    expect(screen.getByText('Untrusted Agent Identity')).toBeInTheDocument()
    expect(screen.getByText('PSP Timeout — Unknown Settlement')).toBeInTheDocument()
    expect(screen.getByText('Payment Succeeded, Service Delivery Failed')).toBeInTheDocument()
  })

  it('renders the pipeline overview with all 5 phases', () => {
    render(<AgenticDemoPage />)
    expect(screen.getByText('Agent Payment')).toBeInTheDocument()
    expect(screen.getByText('Failure Diagnosis')).toBeInTheDocument()
    expect(screen.getByText('Reconciliation')).toBeInTheDocument()
    expect(screen.getByText('Policy Check')).toBeInTheDocument()
    expect(screen.getByText('Recovery Action')).toBeInTheDocument()
  })

  it('renders Run Scenario buttons for each card', () => {
    render(<AgenticDemoPage />)
    const buttons = screen.getAllByText('Run Scenario')
    expect(buttons).toHaveLength(6)
  })

  it('shows prompt text before running a scenario', () => {
    render(<AgenticDemoPage />)
    const prompts = screen.getAllByText(/Click "Run Scenario" to trace the recovery pipeline/)
    expect(prompts.length).toBeGreaterThan(0)
  })

  it('starts animation when Run Scenario is clicked', async () => {
    render(<AgenticDemoPage />)
    const buttons = screen.getAllByText('Run Scenario')
    fireEvent.click(buttons[0])
    await waitFor(() => {
      expect(screen.getByText('Running...')).toBeInTheDocument()
    })
  })

  it('shows pipeline steps after animation completes', async () => {
    vi.useFakeTimers()
    render(<AgenticDemoPage />)
    const buttons = screen.getAllByText('Run Scenario')

    await vi.runAllTimersAsync()
    fireEvent.click(buttons[0])
    await vi.runAllTimersAsync()

    expect(screen.getByText('TRIGGER')).toBeInTheDocument()
    expect(screen.getByText('DIAGNOSE')).toBeInTheDocument()
    vi.useRealTimers()
  })

  it('renders the context section about agent payments', () => {
    render(<AgenticDemoPage />)
    expect(screen.getByText('Why Agent Payments Fail Differently')).toBeInTheDocument()
  })

  it('renders Razorpay ecosystem fit section', () => {
    render(<AgenticDemoPage />)
    expect(screen.getByText(/Recovery Router as Razorpay/)).toBeInTheDocument()
  })
})
