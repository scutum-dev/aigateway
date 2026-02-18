import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import Dashboard from './Dashboard'

vi.mock('react-chartjs-2', () => ({
  Line: () => <div data-testid="line-chart" />,
  Doughnut: () => <div data-testid="doughnut-chart" />,
}))

vi.mock('chart.js', () => ({
  Chart: { register: vi.fn() },
  CategoryScale: vi.fn(),
  LinearScale: vi.fn(),
  PointElement: vi.fn(),
  LineElement: vi.fn(),
  ArcElement: vi.fn(),
  Filler: vi.fn(),
  Tooltip: vi.fn(),
  Legend: vi.fn(),
}))

const mockUseReportsSummary = vi.fn()
const mockUseMCPServers = vi.fn()
const mockUseGuardrails = vi.fn()
const mockUseSettings = vi.fn()

vi.mock('../api/hooks', () => ({
  useReportsSummary: () => mockUseReportsSummary(),
  useMCPServers: () => mockUseMCPServers(),
  useGuardrails: () => mockUseGuardrails(),
  useSettings: () => mockUseSettings(),
}))

vi.mock('../components/Onboarding', () => ({
  default: () => <div data-testid="onboarding" />,
}))

function renderPage() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter>
        <Dashboard />
      </MemoryRouter>
    </QueryClientProvider>
  )
}

describe('Dashboard', () => {
  beforeEach(() => {
    mockUseMCPServers.mockReturnValue({ data: [] })
    mockUseGuardrails.mockReturnValue({ data: [] })
    mockUseSettings.mockReturnValue({ data: null })
  })

  it('shows loading skeletons when isLoading', () => {
    mockUseReportsSummary.mockReturnValue({ data: undefined, isLoading: true, error: null })
    renderPage()
    expect(screen.getByText('Dashboard')).toBeInTheDocument()
    expect(screen.getByText('Platform overview and cost metrics')).toBeInTheDocument()
  })

  it('shows error message when error', () => {
    mockUseReportsSummary.mockReturnValue({ data: undefined, isLoading: false, error: new Error('fail') })
    renderPage()
    expect(screen.getByText('Failed to load metrics')).toBeInTheDocument()
  })

  it('shows stat cards with data', () => {
    mockUseReportsSummary.mockReturnValue({
      data: {
        requests_today: 1234,
        today: { cost: 56.78 },
        tokens_today: 9999,
        this_month: { cost: 123.45 },
        model_usage: { 'gpt-4o': 100 },
        top_models: [],
      },
      isLoading: false,
      error: null,
    })
    renderPage()
    expect(screen.getByText('Requests Today')).toBeInTheDocument()
    expect(screen.getByText('1,234')).toBeInTheDocument()
    expect(screen.getByText('Cost Today')).toBeInTheDocument()
    expect(screen.getByText('$56.78')).toBeInTheDocument()
    expect(screen.getByText('Tokens Today')).toBeInTheDocument()
    expect(screen.getByText('9,999')).toBeInTheDocument()
    expect(screen.getByText('Cost This Month')).toBeInTheDocument()
    expect(screen.getByText('$123.45')).toBeInTheDocument()
  })

  it('shows Cost Over Time chart heading', () => {
    mockUseReportsSummary.mockReturnValue({
      data: { requests_today: 0, today: { cost: 0 }, tokens_today: 0, this_month: { cost: 0 }, model_usage: {}, top_models: [] },
      isLoading: false,
      error: null,
    })
    renderPage()
    expect(screen.getByText('Cost Over Time')).toBeInTheDocument()
    expect(screen.getByTestId('line-chart')).toBeInTheDocument()
  })

  it('shows Model Usage chart heading', () => {
    mockUseReportsSummary.mockReturnValue({
      data: { requests_today: 0, today: { cost: 0 }, tokens_today: 0, this_month: { cost: 0 }, model_usage: { 'gpt-4o': 10 }, top_models: [] },
      isLoading: false,
      error: null,
    })
    renderPage()
    expect(screen.getByText('Model Usage')).toBeInTheDocument()
    expect(screen.getByTestId('doughnut-chart')).toBeInTheDocument()
  })

  it('shows no usage data message when model_usage is empty', () => {
    mockUseReportsSummary.mockReturnValue({
      data: { requests_today: 0, today: { cost: 0 }, tokens_today: 0, this_month: { cost: 0 }, model_usage: {}, top_models: [] },
      isLoading: false,
      error: null,
    })
    renderPage()
    expect(screen.getByText('No usage data available')).toBeInTheDocument()
  })

  it('renders Onboarding component', () => {
    mockUseReportsSummary.mockReturnValue({
      data: { requests_today: 0, today: { cost: 0 }, tokens_today: 0, this_month: { cost: 0 }, model_usage: {}, top_models: [] },
      isLoading: false,
      error: null,
    })
    renderPage()
    expect(screen.getByTestId('onboarding')).toBeInTheDocument()
  })

  it('shows $0.00 formatted cost when cost is zero', () => {
    mockUseReportsSummary.mockReturnValue({
      data: { requests_today: 0, today: { cost: 0 }, tokens_today: 0, this_month: { cost: 0 }, model_usage: {}, top_models: [] },
      isLoading: false,
      error: null,
    })
    renderPage()
    expect(screen.getAllByText('$0.00').length).toBe(2)
  })

  it('shows "0" for zero requests and tokens', () => {
    mockUseReportsSummary.mockReturnValue({
      data: { requests_today: 0, today: { cost: 0 }, tokens_today: 0, this_month: { cost: 0 }, model_usage: {}, top_models: [] },
      isLoading: false,
      error: null,
    })
    renderPage()
    expect(screen.getAllByText('0').length).toBeGreaterThanOrEqual(2)
  })

  it('shows Top Models section when top_models data exists', () => {
    mockUseReportsSummary.mockReturnValue({
      data: {
        requests_today: 10,
        today: { cost: 5.0 },
        tokens_today: 100,
        this_month: { cost: 50.0 },
        model_usage: { 'gpt-4o': 10 },
        top_models: [
          { model: 'gpt-4o', cost: 30.5 },
          { model: 'claude-3.5-sonnet', cost: 19.5 },
        ],
      },
      isLoading: false,
      error: null,
    })
    renderPage()
    expect(screen.getByText('Top Models (This Month)')).toBeInTheDocument()
    expect(screen.getByText('$30.5000')).toBeInTheDocument()
    expect(screen.getByText('$19.5000')).toBeInTheDocument()
  })

  it('does not show Top Models section when top_models is empty', () => {
    mockUseReportsSummary.mockReturnValue({
      data: { requests_today: 0, today: { cost: 0 }, tokens_today: 0, this_month: { cost: 0 }, model_usage: {}, top_models: [] },
      isLoading: false,
      error: null,
    })
    renderPage()
    expect(screen.queryByText('Top Models (This Month)')).not.toBeInTheDocument()
  })

  it('shows all 4 stat card labels', () => {
    mockUseReportsSummary.mockReturnValue({
      data: { requests_today: 0, today: { cost: 0 }, tokens_today: 0, this_month: { cost: 0 }, model_usage: {}, top_models: [] },
      isLoading: false,
      error: null,
    })
    renderPage()
    expect(screen.getByText('Requests Today')).toBeInTheDocument()
    expect(screen.getByText('Cost Today')).toBeInTheDocument()
    expect(screen.getByText('Tokens Today')).toBeInTheDocument()
    expect(screen.getByText('Cost This Month')).toBeInTheDocument()
  })
})
