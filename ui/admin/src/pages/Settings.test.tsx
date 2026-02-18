import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import Settings from './Settings'

const mockUseSettings = vi.fn()
const mockUseUpdateSettings = vi.fn()

vi.mock('../api/hooks', () => ({
  useSettings: () => mockUseSettings(),
  useUpdateSettings: () => mockUseUpdateSettings(),
}))

vi.mock('../components/Toast', () => ({
  useToast: () => vi.fn(),
}))

function renderPage() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter>
        <Settings />
      </MemoryRouter>
    </QueryClientProvider>
  )
}

describe('Settings', () => {
  beforeEach(() => {
    mockUseUpdateSettings.mockReturnValue({ mutateAsync: vi.fn(), isPending: false })
  })

  it('shows loading state', () => {
    mockUseSettings.mockReturnValue({ data: undefined, isLoading: true, error: null })
    renderPage()
    expect(screen.getByText('Settings')).toBeInTheDocument()
    expect(screen.getByText('Platform-wide configuration')).toBeInTheDocument()
  })

  it('shows error state', () => {
    mockUseSettings.mockReturnValue({ data: undefined, isLoading: false, error: new Error('fail') })
    renderPage()
    expect(screen.getByText('Failed to load settings')).toBeInTheDocument()
  })

  it('shows settings form sections', () => {
    mockUseSettings.mockReturnValue({
      data: {
        default_model: 'gpt-4o-mini',
        global_rate_limit: 1000,
        enable_caching: true,
        cache_ttl_seconds: 3600,
        enable_cost_tracking: true,
        enable_budget_enforcement: true,
        enable_guardrails: true,
        maintenance_mode: false,
      },
      isLoading: false,
      error: null,
    })
    renderPage()
    expect(screen.getByText('General')).toBeInTheDocument()
    expect(screen.getByText('Caching')).toBeInTheDocument()
    expect(screen.getByText('Features')).toBeInTheDocument()
    expect(screen.getByText('Maintenance Mode')).toBeInTheDocument()
  })

  it('shows Save Settings button', () => {
    mockUseSettings.mockReturnValue({
      data: {
        default_model: 'gpt-4o-mini',
        global_rate_limit: 1000,
        enable_caching: true,
        cache_ttl_seconds: 3600,
        enable_cost_tracking: true,
        enable_budget_enforcement: true,
        enable_guardrails: true,
        maintenance_mode: false,
      },
      isLoading: false,
      error: null,
    })
    renderPage()
    expect(screen.getByText('Save Settings')).toBeInTheDocument()
  })

  it('renders feature toggle switches', () => {
    mockUseSettings.mockReturnValue({
      data: {
        default_model: 'gpt-4o-mini',
        global_rate_limit: 1000,
        enable_caching: true,
        cache_ttl_seconds: 3600,
        enable_cost_tracking: true,
        enable_budget_enforcement: true,
        enable_guardrails: true,
        maintenance_mode: false,
      },
      isLoading: false,
      error: null,
    })
    renderPage()
    expect(screen.getByText('Cost Tracking')).toBeInTheDocument()
    expect(screen.getByText('Budget Enforcement')).toBeInTheDocument()
    expect(screen.getByText('Guardrails')).toBeInTheDocument()
    const switches = screen.getAllByRole('switch')
    expect(switches.length).toBeGreaterThanOrEqual(4)
  })
})
