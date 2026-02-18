import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import SSOComplete from './SSOComplete'

const mockNavigate = vi.fn()

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom')
  return {
    ...actual,
    useNavigate: () => mockNavigate,
  }
})

function renderPage(initialEntries: string[] = ['/sso-complete']) {
  return render(
    <MemoryRouter initialEntries={initialEntries}>
      <SSOComplete />
    </MemoryRouter>
  )
}

describe('SSOComplete', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    localStorage.clear()
  })

  it('renders "Completing SSO authentication..." text', () => {
    renderPage()
    expect(screen.getByText('Completing SSO authentication...')).toBeInTheDocument()
  })

  it('stores token in localStorage when token param is present', () => {
    renderPage(['/sso-complete?token=abc123'])
    expect(localStorage.getItem('admin_token')).toBe('abc123')
  })

  it('stores expires_at in localStorage when both params are present', () => {
    renderPage(['/sso-complete?token=abc123&expires_at=2026-12-31T00:00:00Z'])
    expect(localStorage.getItem('admin_token')).toBe('abc123')
    expect(localStorage.getItem('token_expires_at')).toBe('2026-12-31T00:00:00Z')
  })

  it('navigates to / with replace when token is present', () => {
    renderPage(['/sso-complete?token=abc123'])
    expect(mockNavigate).toHaveBeenCalledWith('/', { replace: true })
  })

  it('navigates to / with replace when token is missing', () => {
    renderPage(['/sso-complete'])
    expect(mockNavigate).toHaveBeenCalledWith('/', { replace: true })
  })

  it('does NOT store expires_at when it is absent', () => {
    renderPage(['/sso-complete?token=abc123'])
    expect(localStorage.getItem('admin_token')).toBe('abc123')
    expect(localStorage.getItem('token_expires_at')).toBeNull()
  })
})
