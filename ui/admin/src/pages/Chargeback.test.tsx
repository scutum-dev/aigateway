import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { describe, it, expect, vi, beforeEach } from 'vitest'

const mockUseCostAllocationRules = vi.fn()
const mockUseCreateCostAllocationRule = vi.fn()
const mockUseDeleteCostAllocationRule = vi.fn()
const mockUseChargebackReports = vi.fn()
const mockUseBudgetForecasts = vi.fn()

vi.mock('../api/hooks', () => ({
  useCostAllocationRules: () => mockUseCostAllocationRules(),
  useCreateCostAllocationRule: () => mockUseCreateCostAllocationRule(),
  useDeleteCostAllocationRule: () => mockUseDeleteCostAllocationRule(),
  useChargebackReports: () => mockUseChargebackReports(),
  useBudgetForecasts: () => mockUseBudgetForecasts(),
}))

vi.mock('../api/client', () => ({
  chargebackApi: {
    generateReport: vi.fn(),
    exportReport: vi.fn(),
    finalizeReport: vi.fn(),
    generateForecast: vi.fn(),
  },
}))

vi.mock('../components/Toast', () => ({
  useToast: () => vi.fn(),
}))

import Chargeback from './Chargeback'

function renderPage() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter>
        <Chargeback />
      </MemoryRouter>
    </QueryClientProvider>
  )
}

describe('Chargeback', () => {
  beforeEach(() => {
    mockUseCreateCostAllocationRule.mockReturnValue({ mutateAsync: vi.fn(), isPending: false })
    mockUseDeleteCostAllocationRule.mockReturnValue({ mutateAsync: vi.fn() })
  })

  it('renders loading state', () => {
    mockUseCostAllocationRules.mockReturnValue({ data: undefined, isLoading: true })
    mockUseChargebackReports.mockReturnValue({ data: undefined, isLoading: true })
    mockUseBudgetForecasts.mockReturnValue({ data: undefined, isLoading: true })
    renderPage()
    expect(screen.getByText('Chargeback')).toBeInTheDocument()
    expect(screen.getByText('Cost allocation, chargeback reports, and budget forecasts')).toBeInTheDocument()
  })

  it('renders tabs for rules, reports, and forecasts', () => {
    mockUseCostAllocationRules.mockReturnValue({ data: [], isLoading: false })
    mockUseChargebackReports.mockReturnValue({ data: [], isLoading: false })
    mockUseBudgetForecasts.mockReturnValue({ data: [], isLoading: false })
    renderPage()
    expect(screen.getByText('Allocation Rules')).toBeInTheDocument()
    expect(screen.getByText('Reports')).toBeInTheDocument()
    expect(screen.getByText('Forecasts')).toBeInTheDocument()
  })

  it('renders empty rules tab', () => {
    mockUseCostAllocationRules.mockReturnValue({ data: [], isLoading: false })
    mockUseChargebackReports.mockReturnValue({ data: [], isLoading: false })
    mockUseBudgetForecasts.mockReturnValue({ data: [], isLoading: false })
    renderPage()
    expect(screen.getByText('No allocation rules defined')).toBeInTheDocument()
  })

  it('renders rule data in table', () => {
    mockUseCostAllocationRules.mockReturnValue({
      data: [
        { id: '1', name: 'Eng Split', team_id: null, allocation_type: 'department', allocation_target: 'engineering', allocation_percent: 70 },
      ],
      isLoading: false,
    })
    mockUseChargebackReports.mockReturnValue({ data: [], isLoading: false })
    mockUseBudgetForecasts.mockReturnValue({ data: [], isLoading: false })
    renderPage()
    expect(screen.getByText('Eng Split')).toBeInTheDocument()
    expect(screen.getByText('department')).toBeInTheDocument()
    expect(screen.getByText('engineering')).toBeInTheDocument()
    expect(screen.getByText('70%')).toBeInTheDocument()
  })

  it('shows New Rule button on rules tab', () => {
    mockUseCostAllocationRules.mockReturnValue({ data: [], isLoading: false })
    mockUseChargebackReports.mockReturnValue({ data: [], isLoading: false })
    mockUseBudgetForecasts.mockReturnValue({ data: [], isLoading: false })
    renderPage()
    expect(screen.getByText('New Rule')).toBeInTheDocument()
  })

  it('renders rule with team_id', () => {
    mockUseCostAllocationRules.mockReturnValue({
      data: [
        { id: '1', name: 'Team Rule', team_id: 'team-abc-123', allocation_type: 'project', allocation_target: 'alpha', allocation_percent: 50 },
      ],
      isLoading: false,
    })
    mockUseChargebackReports.mockReturnValue({ data: [], isLoading: false })
    mockUseBudgetForecasts.mockReturnValue({ data: [], isLoading: false })
    renderPage()
    expect(screen.getByText('team-abc-123')).toBeInTheDocument()
    expect(screen.getByText('project')).toBeInTheDocument()
    expect(screen.getByText('50%')).toBeInTheDocument()
  })

  it('renders rule without team_id as dashes', () => {
    mockUseCostAllocationRules.mockReturnValue({
      data: [
        { id: '2', name: 'No Team', team_id: null, allocation_type: 'department', allocation_target: 'eng', allocation_percent: 100 },
      ],
      isLoading: false,
    })
    mockUseChargebackReports.mockReturnValue({ data: [], isLoading: false })
    mockUseBudgetForecasts.mockReturnValue({ data: [], isLoading: false })
    renderPage()
    expect(screen.getByText('--')).toBeInTheDocument()
  })

  it('opens and closes create rule modal', async () => {
    mockUseCostAllocationRules.mockReturnValue({ data: [], isLoading: false })
    mockUseChargebackReports.mockReturnValue({ data: [], isLoading: false })
    mockUseBudgetForecasts.mockReturnValue({ data: [], isLoading: false })
    renderPage()
    await userEvent.click(screen.getByText('New Rule'))
    expect(screen.getByText('Create Allocation Rule')).toBeInTheDocument()
    expect(screen.getByPlaceholderText('e.g. Engineering Team Split')).toBeInTheDocument()
    expect(screen.getByPlaceholderText('UUID of the team')).toBeInTheDocument()
    expect(screen.getByPlaceholderText('e.g. engineering, marketing')).toBeInTheDocument()
    await userEvent.click(screen.getByText('Cancel'))
    expect(screen.queryByText('Create Allocation Rule')).not.toBeInTheDocument()
  })

  it('submits create rule form', async () => {
    const mockMutateAsync = vi.fn().mockResolvedValue({})
    mockUseCreateCostAllocationRule.mockReturnValue({ mutateAsync: mockMutateAsync, isPending: false })
    mockUseCostAllocationRules.mockReturnValue({ data: [], isLoading: false })
    mockUseChargebackReports.mockReturnValue({ data: [], isLoading: false })
    mockUseBudgetForecasts.mockReturnValue({ data: [], isLoading: false })
    renderPage()
    await userEvent.click(screen.getByText('New Rule'))
    await userEvent.type(screen.getByPlaceholderText('e.g. Engineering Team Split'), 'My Rule')
    await userEvent.type(screen.getByPlaceholderText('e.g. engineering, marketing'), 'engineering')
    await userEvent.click(screen.getByRole('button', { name: 'Create' }))
    expect(mockMutateAsync).toHaveBeenCalled()
  })

  it('create rule form disables Create button when name or target is empty', async () => {
    mockUseCostAllocationRules.mockReturnValue({ data: [], isLoading: false })
    mockUseChargebackReports.mockReturnValue({ data: [], isLoading: false })
    mockUseBudgetForecasts.mockReturnValue({ data: [], isLoading: false })
    renderPage()
    await userEvent.click(screen.getByText('New Rule'))
    const createBtn = screen.getByRole('button', { name: 'Create' })
    expect(createBtn).toBeDisabled()
  })

  it('shows allocation type options in create rule form', async () => {
    mockUseCostAllocationRules.mockReturnValue({ data: [], isLoading: false })
    mockUseChargebackReports.mockReturnValue({ data: [], isLoading: false })
    mockUseBudgetForecasts.mockReturnValue({ data: [], isLoading: false })
    renderPage()
    await userEvent.click(screen.getByText('New Rule'))
    expect(screen.getByText('Department')).toBeInTheDocument()
    expect(screen.getByText('Project')).toBeInTheDocument()
    expect(screen.getByText('Cost Center')).toBeInTheDocument()
    expect(screen.getByText('Direct')).toBeInTheDocument()
  })

  it('shows delete button on rules', () => {
    mockUseCostAllocationRules.mockReturnValue({
      data: [
        { id: '1', name: 'Rule1', team_id: null, allocation_type: 'department', allocation_target: 'eng', allocation_percent: 100 },
      ],
      isLoading: false,
    })
    mockUseChargebackReports.mockReturnValue({ data: [], isLoading: false })
    mockUseBudgetForecasts.mockReturnValue({ data: [], isLoading: false })
    renderPage()
    expect(screen.getByTitle('Delete rule')).toBeInTheDocument()
  })

  it('switches to Reports tab and shows empty state', async () => {
    mockUseCostAllocationRules.mockReturnValue({ data: [], isLoading: false })
    mockUseChargebackReports.mockReturnValue({ data: [], isLoading: false })
    mockUseBudgetForecasts.mockReturnValue({ data: [], isLoading: false })
    renderPage()
    await userEvent.click(screen.getByText('Reports'))
    expect(screen.getByText('No chargeback reports')).toBeInTheDocument()
    expect(screen.getByText('Generate a report for a billing period to see cost breakdowns.')).toBeInTheDocument()
  })

  it('shows Generate Report button on reports tab', async () => {
    mockUseCostAllocationRules.mockReturnValue({ data: [], isLoading: false })
    mockUseChargebackReports.mockReturnValue({ data: [], isLoading: false })
    mockUseBudgetForecasts.mockReturnValue({ data: [], isLoading: false })
    renderPage()
    await userEvent.click(screen.getByText('Reports'))
    expect(screen.getByText('Generate Report')).toBeInTheDocument()
  })

  it('opens and closes generate report modal', async () => {
    mockUseCostAllocationRules.mockReturnValue({ data: [], isLoading: false })
    mockUseChargebackReports.mockReturnValue({ data: [], isLoading: false })
    mockUseBudgetForecasts.mockReturnValue({ data: [], isLoading: false })
    renderPage()
    await userEvent.click(screen.getByText('Reports'))
    await userEvent.click(screen.getByText('Generate Report'))
    expect(screen.getByText('Generate Chargeback Report')).toBeInTheDocument()
    expect(screen.getByText('Report Period (YYYY-MM)')).toBeInTheDocument()
    await userEvent.click(screen.getByText('Cancel'))
    expect(screen.queryByText('Generate Chargeback Report')).not.toBeInTheDocument()
  })

  it('renders report data with draft status and action buttons', async () => {
    mockUseCostAllocationRules.mockReturnValue({ data: [], isLoading: false })
    mockUseChargebackReports.mockReturnValue({
      data: [
        {
          id: 'rpt1',
          report_period: '2025-06',
          status: 'draft',
          total_cost: 1234.5678,
          generated_by: 'admin@co.com',
          created_at: '2025-07-01T12:00:00Z',
        },
      ],
      isLoading: false,
    })
    mockUseBudgetForecasts.mockReturnValue({ data: [], isLoading: false })
    renderPage()
    await userEvent.click(screen.getByText('Reports'))
    expect(screen.getByText('2025-06')).toBeInTheDocument()
    expect(screen.getByText('draft')).toBeInTheDocument()
    expect(screen.getByText('$1234.5678')).toBeInTheDocument()
    expect(screen.getByText('admin@co.com')).toBeInTheDocument()
    expect(screen.getByTitle('Export CSV')).toBeInTheDocument()
    expect(screen.getByTitle('Finalize report')).toBeInTheDocument()
  })

  it('renders finalized report without finalize button', async () => {
    mockUseCostAllocationRules.mockReturnValue({ data: [], isLoading: false })
    mockUseChargebackReports.mockReturnValue({
      data: [
        {
          id: 'rpt2',
          report_period: '2025-05',
          status: 'finalized',
          total_cost: 999.0,
          generated_by: null,
          created_at: null,
        },
      ],
      isLoading: false,
    })
    mockUseBudgetForecasts.mockReturnValue({ data: [], isLoading: false })
    renderPage()
    await userEvent.click(screen.getByText('Reports'))
    expect(screen.getByText('finalized')).toBeInTheDocument()
    expect(screen.queryByTitle('Finalize report')).not.toBeInTheDocument()
    expect(screen.getByTitle('Export CSV')).toBeInTheDocument()
  })

  it('renders report with missing generated_by as dashes', async () => {
    mockUseCostAllocationRules.mockReturnValue({ data: [], isLoading: false })
    mockUseChargebackReports.mockReturnValue({
      data: [
        {
          id: 'rpt3',
          report_period: '2025-04',
          status: 'draft',
          total_cost: 0.0,
          generated_by: '',
          created_at: null,
        },
      ],
      isLoading: false,
    })
    mockUseBudgetForecasts.mockReturnValue({ data: [], isLoading: false })
    renderPage()
    await userEvent.click(screen.getByText('Reports'))
    const dashes = screen.getAllByText('--')
    expect(dashes.length).toBeGreaterThanOrEqual(1)
  })

  it('switches to Forecasts tab and shows empty state', async () => {
    mockUseCostAllocationRules.mockReturnValue({ data: [], isLoading: false })
    mockUseChargebackReports.mockReturnValue({ data: [], isLoading: false })
    mockUseBudgetForecasts.mockReturnValue({ data: [], isLoading: false })
    renderPage()
    await userEvent.click(screen.getByText('Forecasts'))
    expect(screen.getByText('No forecasts generated')).toBeInTheDocument()
    expect(screen.getByText('Generate a forecast based on historical spending patterns.')).toBeInTheDocument()
  })

  it('shows Generate Forecast button on forecasts tab', async () => {
    mockUseCostAllocationRules.mockReturnValue({ data: [], isLoading: false })
    mockUseChargebackReports.mockReturnValue({ data: [], isLoading: false })
    mockUseBudgetForecasts.mockReturnValue({ data: [], isLoading: false })
    renderPage()
    await userEvent.click(screen.getByText('Forecasts'))
    expect(screen.getByText('Generate Forecast')).toBeInTheDocument()
  })

  it('renders forecast data with costs and confidence range', async () => {
    mockUseCostAllocationRules.mockReturnValue({ data: [], isLoading: false })
    mockUseChargebackReports.mockReturnValue({ data: [], isLoading: false })
    mockUseBudgetForecasts.mockReturnValue({
      data: [
        {
          id: 'fc1',
          forecast_period: '2025-07',
          team_id: 'team-abc',
          forecast_type: 'linear',
          forecasted_cost: 5000.1234,
          confidence_low: 4000.0,
          confidence_high: 6000.0,
          actual_cost: null,
        },
      ],
      isLoading: false,
    })
    renderPage()
    await userEvent.click(screen.getByText('Forecasts'))
    expect(screen.getByText('2025-07')).toBeInTheDocument()
    expect(screen.getByText('Team: team-abc')).toBeInTheDocument()
    expect(screen.getByText('linear')).toBeInTheDocument()
    expect(screen.getByText('$5000.1234')).toBeInTheDocument()
    expect(screen.getByText('$4000.00 - $6000.00')).toBeInTheDocument()
  })

  it('renders forecast with actual cost', async () => {
    mockUseCostAllocationRules.mockReturnValue({ data: [], isLoading: false })
    mockUseChargebackReports.mockReturnValue({ data: [], isLoading: false })
    mockUseBudgetForecasts.mockReturnValue({
      data: [
        {
          id: 'fc2',
          forecast_period: '2025-06',
          team_id: null,
          forecast_type: 'exponential',
          forecasted_cost: 3000.0,
          confidence_low: 2500.0,
          confidence_high: 3500.0,
          actual_cost: 2800.5678,
        },
      ],
      isLoading: false,
    })
    renderPage()
    await userEvent.click(screen.getByText('Forecasts'))
    expect(screen.getByText('All Teams')).toBeInTheDocument()
    expect(screen.getByText('$2800.5678')).toBeInTheDocument()
  })

  it('displays tab counts when data is present', () => {
    mockUseCostAllocationRules.mockReturnValue({
      data: [
        { id: '1', name: 'R1', team_id: null, allocation_type: 'department', allocation_target: 'eng', allocation_percent: 100 },
        { id: '2', name: 'R2', team_id: null, allocation_type: 'project', allocation_target: 'alpha', allocation_percent: 50 },
      ],
      isLoading: false,
    })
    mockUseChargebackReports.mockReturnValue({
      data: [
        { id: 'rpt1', report_period: '2025-06', status: 'draft', total_cost: 100, generated_by: null, created_at: null },
      ],
      isLoading: false,
    })
    mockUseBudgetForecasts.mockReturnValue({ data: [], isLoading: false })
    renderPage()
    expect(screen.getByText('2')).toBeInTheDocument()
    expect(screen.getByText('1')).toBeInTheDocument()
  })

  it('generate report modal disables Generate button when period is empty', async () => {
    mockUseCostAllocationRules.mockReturnValue({ data: [], isLoading: false })
    mockUseChargebackReports.mockReturnValue({ data: [], isLoading: false })
    mockUseBudgetForecasts.mockReturnValue({ data: [], isLoading: false })
    renderPage()
    await userEvent.click(screen.getByText('Reports'))
    await userEvent.click(screen.getByText('Generate Report'))
    const generateBtn = screen.getByRole('button', { name: 'Generate' })
    expect(generateBtn).toBeDisabled()
  })

  it('renders forecast for all teams when team_id is null', async () => {
    mockUseCostAllocationRules.mockReturnValue({ data: [], isLoading: false })
    mockUseChargebackReports.mockReturnValue({ data: [], isLoading: false })
    mockUseBudgetForecasts.mockReturnValue({
      data: [
        {
          id: 'fc3',
          forecast_period: '2025-08',
          team_id: null,
          forecast_type: 'linear',
          forecasted_cost: 1000.0,
          confidence_low: 800.0,
          confidence_high: 1200.0,
          actual_cost: null,
        },
      ],
      isLoading: false,
    })
    renderPage()
    await userEvent.click(screen.getByText('Forecasts'))
    expect(screen.getByText('All Teams')).toBeInTheDocument()
    expect(screen.queryByText(/Actual/)).not.toBeInTheDocument()
  })
})
