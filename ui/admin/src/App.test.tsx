import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'

vi.mock('./api/client', () => ({
  authApi: {
    me: vi.fn().mockResolvedValue({ id: '1', email: 'admin@test.com', role: 'admin' }),
    login: vi.fn(),
  },
}))

// Mock all lazy-loaded page components to avoid deep dependency issues
vi.mock('./pages/Dashboard', () => ({ default: () => <div>Dashboard Page</div> }))
vi.mock('./pages/Models', () => ({ default: () => <div>Models Page</div> }))
vi.mock('./pages/APIKeys', () => ({ default: () => <div>APIKeys Page</div> }))
vi.mock('./pages/Teams', () => ({ default: () => <div>Teams Page</div> }))
vi.mock('./pages/Budgets', () => ({ default: () => <div>Budgets Page</div> }))
vi.mock('./pages/MCPServers', () => ({ default: () => <div>MCPServers Page</div> }))
vi.mock('./pages/Agents', () => ({ default: () => <div>Agents Page</div> }))
vi.mock('./pages/Guardrails', () => ({ default: () => <div>Guardrails Page</div> }))
vi.mock('./pages/Workflows', () => ({ default: () => <div>Workflows Page</div> }))
vi.mock('./pages/Settings', () => ({ default: () => <div>Settings Page</div> }))
vi.mock('./pages/Organizations', () => ({ default: () => <div>Organizations Page</div> }))
vi.mock('./pages/OrganizationDetail', () => ({ default: () => <div>OrgDetail Page</div> }))
vi.mock('./pages/AuditLog', () => ({ default: () => <div>AuditLog Page</div> }))
vi.mock('./pages/Prompts', () => ({ default: () => <div>Prompts Page</div> }))
vi.mock('./pages/RateLimits', () => ({ default: () => <div>RateLimits Page</div> }))
vi.mock('./pages/ModelAccess', () => ({ default: () => <div>ModelAccess Page</div> }))
vi.mock('./pages/Chargeback', () => ({ default: () => <div>Chargeback Page</div> }))
vi.mock('./pages/SLAMonitoring', () => ({ default: () => <div>SLAMonitoring Page</div> }))
vi.mock('./pages/ABTests', () => ({ default: () => <div>ABTests Page</div> }))
vi.mock('./pages/Events', () => ({ default: () => <div>Events Page</div> }))
vi.mock('./pages/SSOComplete', () => ({ default: () => <div>SSOComplete Page</div> }))
vi.mock('./pages/Login', () => ({
  default: ({ onLogin }: { onLogin: (token: string, expiresAt: string) => void }) => (
    <div>
      <span>Login Page</span>
      <button onClick={() => onLogin('test-token', '2099-01-01T00:00:00Z')}>Mock Login</button>
    </div>
  ),
}))
vi.mock('./components/Layout', () => ({
  default: ({ children, onLogout }: { children: React.ReactNode; onLogout: () => void }) => (
    <div>
      <span>Layout</span>
      <button onClick={onLogout}>Logout</button>
      {children}
    </div>
  ),
}))
vi.mock('./components/ErrorBoundary', () => ({
  default: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
}))

import App from './App'

function renderApp(initialEntries = ['/']) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={initialEntries}>
        <App />
      </MemoryRouter>
    </QueryClientProvider>
  )
}

describe('App', () => {
  beforeEach(() => {
    localStorage.clear()
  })

  afterEach(() => {
    localStorage.clear()
  })

  it('renders Login page when not authenticated', () => {
    renderApp()
    expect(screen.getByText('Login Page')).toBeInTheDocument()
  })

  it('renders layout with Dashboard when authenticated', async () => {
    localStorage.setItem('admin_token', 'test-token')
    localStorage.setItem('token_expires_at', '2099-01-01T00:00:00Z')
    renderApp()
    await waitFor(() => {
      expect(screen.getByText('Layout')).toBeInTheDocument()
    })
    expect(screen.getByText('Dashboard Page')).toBeInTheDocument()
  })

  it('clears expired tokens and shows login', () => {
    localStorage.setItem('admin_token', 'test-token')
    localStorage.setItem('token_expires_at', '2020-01-01T00:00:00Z')
    renderApp()
    expect(screen.getByText('Login Page')).toBeInTheDocument()
    expect(localStorage.getItem('admin_token')).toBeNull()
  })

  it('handles logout by clearing token and showing login', async () => {
    localStorage.setItem('admin_token', 'test-token')
    localStorage.setItem('token_expires_at', '2099-01-01T00:00:00Z')
    renderApp()
    await waitFor(() => {
      expect(screen.getByText('Logout')).toBeInTheDocument()
    })
    await userEvent.click(screen.getByText('Logout'))
    expect(screen.getByText('Login Page')).toBeInTheDocument()
    expect(localStorage.getItem('admin_token')).toBeNull()
  })
})
