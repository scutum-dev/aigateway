import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import Login from './Login'

// Mock the authApi module
vi.mock('../api/client', () => ({
  authApi: {
    login: vi.fn(),
  },
}))

import { authApi } from '../api/client'

const mockedLogin = vi.mocked(authApi.login)

beforeEach(() => {
  vi.clearAllMocks()
})

describe('Login', () => {
  it('renders login form with API Key input', () => {
    render(<Login onLogin={vi.fn()} />)
    expect(screen.getByLabelText('API Key')).toBeInTheDocument()
  })

  it('renders the heading and subtitle', () => {
    render(<Login onLogin={vi.fn()} />)
    expect(screen.getByText('AI Control Plane')).toBeInTheDocument()
    expect(screen.getByText('Admin Console')).toBeInTheDocument()
  })

  it('shows "Sign In" button', () => {
    render(<Login onLogin={vi.fn()} />)
    expect(screen.getByRole('button', { name: 'Sign In' })).toBeInTheDocument()
  })

  it('input has placeholder "sk-litellm-..."', () => {
    render(<Login onLogin={vi.fn()} />)
    const input = screen.getByPlaceholderText('sk-litellm-...')
    expect(input).toBeInTheDocument()
  })

  it('calls onLogin with token and expiresAt on successful login', async () => {
    const onLogin = vi.fn()
    mockedLogin.mockResolvedValueOnce({
      access_token: 'jwt-token-123',
      expires_at: '2026-03-01T00:00:00Z',
      token_type: 'bearer',
    })

    render(<Login onLogin={onLogin} />)
    await userEvent.type(screen.getByLabelText('API Key'), 'sk-litellm-test-key')
    await userEvent.click(screen.getByRole('button', { name: 'Sign In' }))

    await waitFor(() => {
      expect(onLogin).toHaveBeenCalledWith('jwt-token-123', '2026-03-01T00:00:00Z')
    })
    expect(mockedLogin).toHaveBeenCalledWith('sk-litellm-test-key')
  })

  it('shows error message on failed login', async () => {
    mockedLogin.mockRejectedValueOnce({
      response: { data: { detail: 'Invalid API key' } },
    })

    render(<Login onLogin={vi.fn()} />)
    await userEvent.type(screen.getByLabelText('API Key'), 'bad-key')
    await userEvent.click(screen.getByRole('button', { name: 'Sign In' }))

    await waitFor(() => {
      expect(screen.getByText('Invalid API key')).toBeInTheDocument()
    })
  })

  it('shows generic error when no detail in response', async () => {
    mockedLogin.mockRejectedValueOnce(new Error('Network error'))

    render(<Login onLogin={vi.fn()} />)
    await userEvent.type(screen.getByLabelText('API Key'), 'some-key')
    await userEvent.click(screen.getByRole('button', { name: 'Sign In' }))

    await waitFor(() => {
      expect(screen.getByText('Login failed')).toBeInTheDocument()
    })
  })

  it('shows "Signing in..." while loading', async () => {
    // Create a promise we control to keep the loading state
    let resolveLogin: (value: { access_token: string; expires_at: string; token_type: string }) => void
    mockedLogin.mockReturnValueOnce(
      new Promise((resolve) => {
        resolveLogin = resolve
      })
    )

    render(<Login onLogin={vi.fn()} />)
    await userEvent.type(screen.getByLabelText('API Key'), 'sk-litellm-test')
    await userEvent.click(screen.getByRole('button', { name: 'Sign In' }))

    expect(screen.getByText('Signing in...')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Signing in...' })).toBeDisabled()

    // Resolve to clean up
    resolveLogin!({ access_token: 'tok', expires_at: 'exp', token_type: 'bearer' })
    await waitFor(() => {
      expect(screen.getByText('Sign In')).toBeInTheDocument()
    })
  })

  it('has a password type input for the API key', () => {
    render(<Login onLogin={vi.fn()} />)
    const input = screen.getByLabelText('API Key')
    expect(input).toHaveAttribute('type', 'password')
  })
})
