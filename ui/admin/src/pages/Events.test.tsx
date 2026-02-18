import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { describe, it, expect, vi, beforeEach } from 'vitest'

const mockUseEventSubscriptions = vi.fn()
const mockUseCreateEventSubscription = vi.fn()
const mockUseDeleteEventSubscription = vi.fn()
const mockUseEventLog = vi.fn()
const mockUseSendTestEvent = vi.fn()

vi.mock('../api/hooks', () => ({
  useEventSubscriptions: () => mockUseEventSubscriptions(),
  useCreateEventSubscription: () => mockUseCreateEventSubscription(),
  useDeleteEventSubscription: () => mockUseDeleteEventSubscription(),
  useEventLog: () => mockUseEventLog(),
  useSendTestEvent: () => mockUseSendTestEvent(),
}))

vi.mock('../components/Toast', () => ({
  useToast: () => vi.fn(),
}))

import Events from './Events'

function renderPage() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter>
        <Events />
      </MemoryRouter>
    </QueryClientProvider>
  )
}

describe('Events', () => {
  beforeEach(() => {
    mockUseCreateEventSubscription.mockReturnValue({ mutateAsync: vi.fn(), isPending: false })
    mockUseDeleteEventSubscription.mockReturnValue({ mutateAsync: vi.fn() })
    mockUseSendTestEvent.mockReturnValue({ mutateAsync: vi.fn(), isPending: false })
  })

  it('renders page header', () => {
    mockUseEventSubscriptions.mockReturnValue({ data: undefined, isLoading: true })
    mockUseEventLog.mockReturnValue({ data: undefined, isLoading: true })
    renderPage()
    expect(screen.getByText('Events')).toBeInTheDocument()
    expect(screen.getByText('Manage event subscriptions and view the event log')).toBeInTheDocument()
  })

  it('renders empty subscriptions state', () => {
    mockUseEventSubscriptions.mockReturnValue({ data: [], isLoading: false })
    mockUseEventLog.mockReturnValue({ data: [], isLoading: false })
    renderPage()
    expect(screen.getByText('No event subscriptions configured')).toBeInTheDocument()
  })

  it('renders subscription data in a table', () => {
    mockUseEventSubscriptions.mockReturnValue({
      data: [
        {
          id: '1',
          name: 'Slack Budget Alerts',
          channel: 'slack',
          event_types: ['budget.exceeded', 'budget.warning'],
          is_active: true,
          created_at: '2025-01-15T00:00:00Z',
        },
      ],
      isLoading: false,
    })
    mockUseEventLog.mockReturnValue({ data: [], isLoading: false })
    renderPage()
    expect(screen.getByText('Slack Budget Alerts')).toBeInTheDocument()
    expect(screen.getByText('slack')).toBeInTheDocument()
    expect(screen.getByText('budget.exceeded')).toBeInTheDocument()
    expect(screen.getByText('Active')).toBeInTheDocument()
  })

  it('shows Add Subscription and Send Test Event buttons', () => {
    mockUseEventSubscriptions.mockReturnValue({ data: [], isLoading: false })
    mockUseEventLog.mockReturnValue({ data: [], isLoading: false })
    renderPage()
    expect(screen.getByText('Add Subscription')).toBeInTheDocument()
    expect(screen.getByText('Send Test Event')).toBeInTheDocument()
  })

  it('opens create subscription modal', async () => {
    mockUseEventSubscriptions.mockReturnValue({ data: [], isLoading: false })
    mockUseEventLog.mockReturnValue({ data: [], isLoading: false })
    renderPage()
    await userEvent.click(screen.getByText('Add Subscription'))
    expect(screen.getByText('Create Event Subscription')).toBeInTheDocument()
  })
})
