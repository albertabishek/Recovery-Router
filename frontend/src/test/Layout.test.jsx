import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import Layout from '../components/Layout'

function renderLayout(props = {}) {
  const defaults = {
    activePage: 'overview',
    onNavigate: vi.fn(),
    onLogout: vi.fn(),
    children: <div>Page Content</div>,
  }
  return { ...defaults, ...props, result: render(<Layout {...defaults} {...props} />) }
}

describe('Layout', () => {
  it('renders children inside main area', () => {
    renderLayout({ children: <div>Test Content</div> })
    expect(screen.getByText('Test Content')).toBeInTheDocument()
  })

  it('renders sidebar navigation items', () => {
    renderLayout()
    expect(screen.getByText('Home')).toBeInTheDocument()
    expect(screen.getByText('Recovery Events')).toBeInTheDocument()
    expect(screen.getByText('Reports')).toBeInTheDocument()
    expect(screen.getByText('Simulator')).toBeInTheDocument()
    expect(screen.getByText('Audit Logs')).toBeInTheDocument()
    expect(screen.getByText('Agentic Recovery')).toBeInTheDocument()
  })

  it('renders section headers in sidebar', () => {
    renderLayout()
    expect(screen.getByText('Recovery Tools')).toBeInTheDocument()
    expect(screen.getByText('Vision')).toBeInTheDocument()
  })

  it('calls onNavigate when a nav item is clicked', () => {
    const onNavigate = vi.fn()
    renderLayout({ onNavigate })
    fireEvent.click(screen.getByText('Recovery Events'))
    expect(onNavigate).toHaveBeenCalledWith('events')
  })

  it('calls onLogout when logout button is clicked', () => {
    const onLogout = vi.fn()
    renderLayout({ onLogout })
    fireEvent.click(screen.getByText('Logout'))
    expect(onLogout).toHaveBeenCalled()
  })

  it('does not render logout when onLogout is not provided', () => {
    renderLayout({ onLogout: undefined })
    expect(screen.queryByText('Logout')).not.toBeInTheDocument()
  })

  it('renders mobile menu toggle button', () => {
    renderLayout()
    expect(screen.getByLabelText('Toggle menu')).toBeInTheDocument()
  })

  it('opens mobile menu on toggle click', () => {
    renderLayout()
    fireEvent.click(screen.getByLabelText('Toggle menu'))
    expect(document.querySelector('.sidebar-open')).toBeTruthy()
  })

  it('renders Account & Settings item', () => {
    renderLayout()
    expect(screen.getByText('Account & Settings')).toBeInTheDocument()
  })
})
