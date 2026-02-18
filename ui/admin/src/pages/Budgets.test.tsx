import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import Budgets from './Budgets'

const mockUseBudgets = vi.fn()
const mockUseCreateBudget = vi.fn()
const mockUseUpdateBudget = vi.fn()
const mockUseDeleteBudget = vi.fn()

vi.mock('../api/hooks', () => ({
  useBudgets: () => mockUseBudgets(),
  useCreateBudget: () => mockUseCreateBudget(),
  useUpdateBudget: () => mockUseUpdateBudget(),
  useDeleteBudget: () => mockUseDeleteBudget(),
}))

vi.mock('../components/Toast', () => ({
  useToast: () => vi.fn(),
}))

function renderPage() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter>
        <Budgets />
      </MemoryRouter>
    </QueryClientProvider>
  )
}

describe('Budgets', () => {
  beforeEach(() => {
    mockUseCreateBudget.mockReturnValue({ mutateAsync: vi.fn(), isPending: false })
    mockUseUpdateBudget.mockReturnValue({ mutateAsync: vi.fn(), isPending: false })
    mockUseDeleteBudget.mockReturnValue({ mutateAsync: vi.fn(), isPending: false })
  })

  it('shows loading state', () => {
    mockUseBudgets.mockReturnValue({ data: undefined, isLoading: true, error: null })
    renderPage()
    expect(screen.getByText('Budgets')).toBeInTheDocument()
    expect(screen.getByText('Manage spending limits and rate controls')).toBeInTheDocument()
  })

  it('shows error state', () => {
    mockUseBudgets.mockReturnValue({ data: undefined, isLoading: false, error: new Error('fail') })
    renderPage()
    expect(screen.getByText('Failed to load budgets')).toBeInTheDocument()
  })

  it('shows Create Budget button', () => {
    mockUseBudgets.mockReturnValue({
      data: [{ budget_id: 'b1', max_budget: 100, soft_budget: 80, max_parallel_requests: null, tpm_limit: null, rpm_limit: null }],
      isLoading: false,
      error: null,
    })
    renderPage()
    expect(screen.getByText('Create Budget')).toBeInTheDocument()
  })

  it('shows budget list with data', () => {
    mockUseBudgets.mockReturnValue({
      data: [
        { budget_id: 'b1', max_budget: 100, soft_budget: 80, max_parallel_requests: 10, tpm_limit: 5000, rpm_limit: 60 },
        { budget_id: 'b2', max_budget: 200, soft_budget: null, max_parallel_requests: null, tpm_limit: null, rpm_limit: null },
      ],
      isLoading: false,
      error: null,
    })
    renderPage()
    expect(screen.getByText('2 budgets configured')).toBeInTheDocument()
    expect(screen.getByText('$100.00 limit')).toBeInTheDocument()
  })

  it('shows empty state when no budgets', () => {
    mockUseBudgets.mockReturnValue({ data: [], isLoading: false, error: null })
    renderPage()
    expect(screen.getByText('No budgets configured')).toBeInTheDocument()
    expect(screen.getByText('Create budgets to control spending limits and rate controls for teams and keys.')).toBeInTheDocument()
  })
})
