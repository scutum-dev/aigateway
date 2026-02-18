import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { describe, it, expect, vi, beforeEach } from 'vitest'

const mockUseRateLimitPolicies = vi.fn()
const mockUseCreateRateLimitPolicy = vi.fn()
const mockUseDeleteRateLimitPolicy = vi.fn()
const mockUseRateLimitEvents = vi.fn()

vi.mock('../api/hooks', () => ({
  useRateLimitPolicies: () => mockUseRateLimitPolicies(),
  useCreateRateLimitPolicy: () => mockUseCreateRateLimitPolicy(),
  useDeleteRateLimitPolicy: () => mockUseDeleteRateLimitPolicy(),
  useRateLimitEvents: () => mockUseRateLimitEvents(),
}))

vi.mock('../api/client', () => ({
  rateLimitsApi: { update: vi.fn() },
}))

vi.mock('../components/Toast', () => ({
  useToast: () => vi.fn(),
}))

import RateLimits from './RateLimits'

function renderPage() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter>
        <RateLimits />
      </MemoryRouter>
    </QueryClientProvider>
  )
}

describe('RateLimits', () => {
  beforeEach(() => {
    mockUseCreateRateLimitPolicy.mockReturnValue({ mutateAsync: vi.fn(), isPending: false })
    mockUseDeleteRateLimitPolicy.mockReturnValue({ mutateAsync: vi.fn() })
    mockUseRateLimitEvents.mockReturnValue({ data: [] })
  })

  it('renders loading state', () => {
    mockUseRateLimitPolicies.mockReturnValue({ data: undefined, isLoading: true, error: null })
    renderPage()
    expect(screen.getByText('Rate Limits')).toBeInTheDocument()
    expect(screen.getByText('Granular rate limit policies')).toBeInTheDocument()
  })

  it('renders error state', () => {
    mockUseRateLimitPolicies.mockReturnValue({ data: undefined, isLoading: false, error: new Error('fail') })
    renderPage()
    expect(screen.getByText('Failed to load rate limit policies')).toBeInTheDocument()
  })

  it('renders empty state when no policies', () => {
    mockUseRateLimitPolicies.mockReturnValue({ data: [], isLoading: false, error: null })
    renderPage()
    expect(screen.getByText('No rate limit policies')).toBeInTheDocument()
  })

  it('renders policy data in a table', () => {
    mockUseRateLimitPolicies.mockReturnValue({
      data: [
        {
          id: '1',
          name: 'Default User Limit',
          scope: 'user',
          scope_value: null,
          rpm_limit: 60,
          tpm_limit: 100000,
          rpd_limit: null,
          tpd_limit: null,
          burst_multiplier: 1.5,
          burst_window_seconds: 10,
          priority: 0,
          is_active: true,
        },
      ],
      isLoading: false,
      error: null,
    })
    renderPage()
    expect(screen.getByText('1 policy')).toBeInTheDocument()
    expect(screen.getByText('Default User Limit')).toBeInTheDocument()
    expect(screen.getByText('User')).toBeInTheDocument()
    expect(screen.getAllByText('Active').length).toBeGreaterThanOrEqual(1)
  })

  it('opens create modal when New Policy button is clicked', async () => {
    mockUseRateLimitPolicies.mockReturnValue({ data: [], isLoading: false, error: null })
    renderPage()
    await userEvent.click(screen.getByText('New Policy'))
    expect(screen.getByText('Create Rate Limit Policy')).toBeInTheDocument()
  })

  it('create form shows name, scope, rpm, tpm fields after opening modal', async () => {
    mockUseRateLimitPolicies.mockReturnValue({ data: [], isLoading: false, error: null })
    renderPage()
    await userEvent.click(screen.getByText('New Policy'))
    expect(screen.getByText('Name')).toBeInTheDocument()
    expect(screen.getByText('Scope')).toBeInTheDocument()
    expect(screen.getByText('RPM (Requests/min)')).toBeInTheDocument()
    expect(screen.getByText('TPM (Tokens/min)')).toBeInTheDocument()
  })

  it('shows priority value in policy data', () => {
    mockUseRateLimitPolicies.mockReturnValue({
      data: [
        {
          id: '1',
          name: 'Default User Limit',
          scope: 'user',
          scope_value: null,
          rpm_limit: 60,
          tpm_limit: 100000,
          rpd_limit: null,
          tpd_limit: null,
          burst_multiplier: 1.5,
          burst_window_seconds: 10,
          priority: 5,
          is_active: true,
        },
      ],
      isLoading: false,
      error: null,
    })
    renderPage()
    expect(screen.getByText('5')).toBeInTheDocument()
  })

  it('shows policy count for multiple items', () => {
    mockUseRateLimitPolicies.mockReturnValue({
      data: [
        { id: '1', name: 'Policy A', scope: 'user', scope_value: null, rpm_limit: 60, tpm_limit: null, rpd_limit: null, tpd_limit: null, burst_multiplier: 1.5, burst_window_seconds: 10, priority: 0, is_active: true },
        { id: '2', name: 'Policy B', scope: 'team', scope_value: null, rpm_limit: 120, tpm_limit: null, rpd_limit: null, tpd_limit: null, burst_multiplier: 1.5, burst_window_seconds: 10, priority: 1, is_active: true },
      ],
      isLoading: false,
      error: null,
    })
    renderPage()
    expect(screen.getByText('2 policies')).toBeInTheDocument()
  })

  it('shows events section when events button clicked', async () => {
    mockUseRateLimitPolicies.mockReturnValue({ data: [], isLoading: false, error: null })
    mockUseRateLimitEvents.mockReturnValue({ data: [] })
    renderPage()
    await userEvent.click(screen.getByText('Events (0)'))
    expect(screen.getByText('Recent Rate Limit Events')).toBeInTheDocument()
    expect(screen.getByText('No rate limit events recorded yet.')).toBeInTheDocument()
  })

  it('shows RPM and TPM values in table', () => {
    mockUseRateLimitPolicies.mockReturnValue({
      data: [
        {
          id: '1',
          name: 'Default User Limit',
          scope: 'user',
          scope_value: null,
          rpm_limit: 60,
          tpm_limit: 100000,
          rpd_limit: null,
          tpd_limit: null,
          burst_multiplier: 1.5,
          burst_window_seconds: 10,
          priority: 0,
          is_active: true,
        },
      ],
      isLoading: false,
      error: null,
    })
    renderPage()
    expect(screen.getByText('60')).toBeInTheDocument()
    expect(screen.getByText('100,000')).toBeInTheDocument()
  })
})
