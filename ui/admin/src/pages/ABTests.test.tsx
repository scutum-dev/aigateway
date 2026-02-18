import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { describe, it, expect, vi, beforeEach } from 'vitest'

const mockUseABTests = vi.fn()
const mockUseABTest = vi.fn()
const mockUseCreateABTest = vi.fn()
const mockUseDeleteABTest = vi.fn()
const mockUseStartABTest = vi.fn()
const mockUseStopABTest = vi.fn()
const mockUsePromoteABTest = vi.fn()
const mockUseABTestSnapshots = vi.fn()

vi.mock('../api/hooks', () => ({
  useABTests: () => mockUseABTests(),
  useABTest: () => mockUseABTest(),
  useCreateABTest: () => mockUseCreateABTest(),
  useDeleteABTest: () => mockUseDeleteABTest(),
  useStartABTest: () => mockUseStartABTest(),
  useStopABTest: () => mockUseStopABTest(),
  usePromoteABTest: () => mockUsePromoteABTest(),
  useABTestSnapshots: () => mockUseABTestSnapshots(),
}))

vi.mock('../components/Toast', () => ({
  useToast: () => vi.fn(),
}))

import ABTests from './ABTests'

function renderPage() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter>
        <ABTests />
      </MemoryRouter>
    </QueryClientProvider>
  )
}

describe('ABTests', () => {
  beforeEach(() => {
    mockUseCreateABTest.mockReturnValue({ mutateAsync: vi.fn(), isPending: false })
    mockUseDeleteABTest.mockReturnValue({ mutateAsync: vi.fn() })
    mockUseStartABTest.mockReturnValue({ mutateAsync: vi.fn() })
    mockUseStopABTest.mockReturnValue({ mutateAsync: vi.fn() })
    mockUsePromoteABTest.mockReturnValue({ mutateAsync: vi.fn() })
    mockUseABTest.mockReturnValue({ data: null })
    mockUseABTestSnapshots.mockReturnValue({ data: [] })
  })

  it('renders loading state', () => {
    mockUseABTests.mockReturnValue({ data: undefined, isLoading: true })
    renderPage()
    expect(screen.getByText('A/B Tests')).toBeInTheDocument()
    expect(screen.getByText('Compare model performance with controlled experiments')).toBeInTheDocument()
  })

  it('renders empty state when no tests', () => {
    mockUseABTests.mockReturnValue({ data: [], isLoading: false })
    renderPage()
    expect(screen.getByText('No A/B tests')).toBeInTheDocument()
    expect(screen.getByText('Create your first experiment to compare model performance.')).toBeInTheDocument()
  })

  it('renders test cards with data', () => {
    mockUseABTests.mockReturnValue({
      data: [
        {
          id: '1',
          name: 'GPT vs Claude Cost Test',
          status: 'running',
          base_model: 'gpt-4o',
          variant_model: 'claude-sonnet-4',
          traffic_split_percent: 20,
          success_metric: 'cost_efficiency',
          created_at: '2025-01-15T00:00:00Z',
        },
      ],
      isLoading: false,
    })
    renderPage()
    expect(screen.getByText('GPT vs Claude Cost Test')).toBeInTheDocument()
    expect(screen.getByText('running')).toBeInTheDocument()
    expect(screen.getByText('gpt-4o')).toBeInTheDocument()
    expect(screen.getByText('claude-sonnet-4')).toBeInTheDocument()
  })

  it('shows New Test button', () => {
    mockUseABTests.mockReturnValue({ data: [], isLoading: false })
    renderPage()
    expect(screen.getByText('New Test')).toBeInTheDocument()
  })

  it('opens create modal when New Test is clicked', async () => {
    mockUseABTests.mockReturnValue({ data: [], isLoading: false })
    renderPage()
    await userEvent.click(screen.getByText('New Test'))
    expect(screen.getByText('Create A/B Test')).toBeInTheDocument()
  })

  it('shows status badges for different statuses', () => {
    mockUseABTests.mockReturnValue({
      data: [
        {
          id: '1',
          name: 'Cost Test',
          status: 'draft',
          base_model: 'gpt-4o',
          variant_model: 'claude-sonnet-4',
          traffic_split_percent: 10,
          success_metric: 'cost_efficiency',
          created_at: '2025-01-01T00:00:00Z',
        },
        {
          id: '2',
          name: 'Latency Test',
          status: 'completed',
          base_model: 'gpt-4o',
          variant_model: 'gpt-4o-mini',
          traffic_split_percent: 20,
          success_metric: 'latency',
          created_at: '2025-01-02T00:00:00Z',
        },
      ],
      isLoading: false,
    })
    renderPage()
    expect(screen.getByText('draft')).toBeInTheDocument()
    expect(screen.getByText('completed')).toBeInTheDocument()
  })

  it('shows variant traffic split and success metric', () => {
    mockUseABTests.mockReturnValue({
      data: [
        {
          id: '1',
          name: 'Cost Test',
          status: 'running',
          base_model: 'gpt-4o',
          variant_model: 'claude-sonnet-4',
          traffic_split_percent: 20,
          success_metric: 'cost_efficiency',
          created_at: '2025-01-01T00:00:00Z',
        },
      ],
      isLoading: false,
    })
    renderPage()
    expect(screen.getByText('20% variant | Cost Efficiency')).toBeInTheDocument()
  })

  it('shows create form fields when modal is open', async () => {
    mockUseABTests.mockReturnValue({ data: [], isLoading: false })
    renderPage()
    await userEvent.click(screen.getByText('New Test'))
    expect(screen.getByText('Test Name')).toBeInTheDocument()
    expect(screen.getByText('Base Model')).toBeInTheDocument()
    expect(screen.getByText('Variant Model')).toBeInTheDocument()
    expect(screen.getByText('Traffic Split (% to variant)')).toBeInTheDocument()
    expect(screen.getByText('Success Metric')).toBeInTheDocument()
  })

  it('shows auto-promote and auto-rollback checkboxes in create form', async () => {
    mockUseABTests.mockReturnValue({ data: [], isLoading: false })
    renderPage()
    await userEvent.click(screen.getByText('New Test'))
    expect(screen.getByText('Auto-promote on success')).toBeInTheDocument()
    expect(screen.getByText('Auto-rollback on failure')).toBeInTheDocument()
  })
})
