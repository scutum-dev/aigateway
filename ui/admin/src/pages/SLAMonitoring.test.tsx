import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { describe, it, expect, vi, beforeEach } from 'vitest'

const mockUseSLADefinitions = vi.fn()
const mockUseCreateSLADefinition = vi.fn()
const mockUseProviderHealth = vi.fn()
const mockUseActiveViolations = vi.fn()
const mockUseFailoverRules = vi.fn()
const mockUseCreateFailoverRule = vi.fn()

vi.mock('../api/hooks', () => ({
  useSLADefinitions: () => mockUseSLADefinitions(),
  useCreateSLADefinition: () => mockUseCreateSLADefinition(),
  useProviderHealth: () => mockUseProviderHealth(),
  useActiveViolations: () => mockUseActiveViolations(),
  useFailoverRules: () => mockUseFailoverRules(),
  useCreateFailoverRule: () => mockUseCreateFailoverRule(),
}))

vi.mock('../api/client', () => ({
  slaApi: {
    deleteDefinition: vi.fn(),
    resolveViolation: vi.fn(),
    deleteFailoverRule: vi.fn(),
    triggerFailover: vi.fn(),
  },
}))

vi.mock('../components/Toast', () => ({
  useToast: () => vi.fn(),
}))

import SLAMonitoring from './SLAMonitoring'

function renderPage() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter>
        <SLAMonitoring />
      </MemoryRouter>
    </QueryClientProvider>
  )
}

describe('SLAMonitoring', () => {
  beforeEach(() => {
    mockUseCreateSLADefinition.mockReturnValue({ mutateAsync: vi.fn(), isPending: false })
    mockUseCreateFailoverRule.mockReturnValue({ mutateAsync: vi.fn(), isPending: false })
  })

  it('renders loading state', () => {
    mockUseProviderHealth.mockReturnValue({ data: undefined, isLoading: true })
    mockUseSLADefinitions.mockReturnValue({ data: undefined, isLoading: true })
    mockUseActiveViolations.mockReturnValue({ data: undefined, isLoading: true })
    mockUseFailoverRules.mockReturnValue({ data: undefined, isLoading: true })
    renderPage()
    expect(screen.getByText('SLA Monitor')).toBeInTheDocument()
    expect(screen.getByText('Provider health, SLA compliance, and failover management')).toBeInTheDocument()
  })

  it('renders tabs', () => {
    mockUseProviderHealth.mockReturnValue({ data: [], isLoading: false })
    mockUseSLADefinitions.mockReturnValue({ data: [], isLoading: false })
    mockUseActiveViolations.mockReturnValue({ data: [], isLoading: false })
    mockUseFailoverRules.mockReturnValue({ data: [], isLoading: false })
    renderPage()
    expect(screen.getByText('Provider Health')).toBeInTheDocument()
    expect(screen.getByText('SLA Definitions')).toBeInTheDocument()
    expect(screen.getByText('Violations')).toBeInTheDocument()
    expect(screen.getByText('Failover Rules')).toBeInTheDocument()
  })

  it('renders empty health tab', () => {
    mockUseProviderHealth.mockReturnValue({ data: [], isLoading: false })
    mockUseSLADefinitions.mockReturnValue({ data: [], isLoading: false })
    mockUseActiveViolations.mockReturnValue({ data: [], isLoading: false })
    mockUseFailoverRules.mockReturnValue({ data: [], isLoading: false })
    renderPage()
    expect(screen.getByText('No health metrics available')).toBeInTheDocument()
  })

  it('renders provider health data', () => {
    mockUseProviderHealth.mockReturnValue({
      data: [
        {
          id: '1',
          provider: 'openai',
          model: 'gpt-4o',
          bucket_start: '2025-01-15T10:00:00Z',
          request_count: 1000,
          error_count: 5,
          p50_latency_ms: 200,
          p95_latency_ms: 800,
          p99_latency_ms: 1500,
          total_tokens: 500000,
        },
      ],
      isLoading: false,
    })
    mockUseSLADefinitions.mockReturnValue({ data: [], isLoading: false })
    mockUseActiveViolations.mockReturnValue({ data: [], isLoading: false })
    mockUseFailoverRules.mockReturnValue({ data: [], isLoading: false })
    renderPage()
    expect(screen.getByText('openai')).toBeInTheDocument()
    expect(screen.getByText('gpt-4o')).toBeInTheDocument()
    expect(screen.getByText('1000')).toBeInTheDocument()
  })

  it('renders health metric error rate and latency values', () => {
    mockUseProviderHealth.mockReturnValue({
      data: [
        {
          id: '1',
          provider: 'openai',
          model: 'gpt-4o',
          bucket_start: '2025-01-15T10:00:00Z',
          request_count: 1000,
          error_count: 5,
          p50_latency_ms: 200,
          p95_latency_ms: 800,
          p99_latency_ms: 1500,
          total_tokens: 500000,
        },
      ],
      isLoading: false,
    })
    mockUseSLADefinitions.mockReturnValue({ data: [], isLoading: false })
    mockUseActiveViolations.mockReturnValue({ data: [], isLoading: false })
    mockUseFailoverRules.mockReturnValue({ data: [], isLoading: false })
    renderPage()
    expect(screen.getByText('0.50%')).toBeInTheDocument()
    expect(screen.getByText('200ms')).toBeInTheDocument()
    expect(screen.getByText('800ms')).toBeInTheDocument()
    expect(screen.getByText('1500ms')).toBeInTheDocument()
    expect(screen.getByText('500,000')).toBeInTheDocument()
  })

  it('renders health metric with null latency as dashes', () => {
    mockUseProviderHealth.mockReturnValue({
      data: [
        {
          id: '2',
          provider: 'anthropic',
          model: 'claude-3',
          bucket_start: '2025-01-15T10:00:00Z',
          request_count: 0,
          error_count: 0,
          p50_latency_ms: null,
          p95_latency_ms: null,
          p99_latency_ms: null,
          total_tokens: 0,
        },
      ],
      isLoading: false,
    })
    mockUseSLADefinitions.mockReturnValue({ data: [], isLoading: false })
    mockUseActiveViolations.mockReturnValue({ data: [], isLoading: false })
    mockUseFailoverRules.mockReturnValue({ data: [], isLoading: false })
    renderPage()
    const dashes = screen.getAllByText('--ms')
    expect(dashes.length).toBe(3)
  })

  it('switches to SLA Definitions tab and shows empty state', async () => {
    mockUseProviderHealth.mockReturnValue({ data: [], isLoading: false })
    mockUseSLADefinitions.mockReturnValue({ data: [], isLoading: false })
    mockUseActiveViolations.mockReturnValue({ data: [], isLoading: false })
    mockUseFailoverRules.mockReturnValue({ data: [], isLoading: false })
    renderPage()
    await userEvent.click(screen.getByText('SLA Definitions'))
    expect(screen.getByText('No SLA definitions')).toBeInTheDocument()
    expect(screen.getByText('Define SLA targets for your providers and models.')).toBeInTheDocument()
  })

  it('shows New SLA button only on definitions tab', async () => {
    mockUseProviderHealth.mockReturnValue({ data: [], isLoading: false })
    mockUseSLADefinitions.mockReturnValue({ data: [], isLoading: false })
    mockUseActiveViolations.mockReturnValue({ data: [], isLoading: false })
    mockUseFailoverRules.mockReturnValue({ data: [], isLoading: false })
    renderPage()
    expect(screen.queryByText('New SLA')).not.toBeInTheDocument()
    await userEvent.click(screen.getByText('SLA Definitions'))
    expect(screen.getByText('New SLA')).toBeInTheDocument()
  })

  it('opens and closes create SLA definition modal', async () => {
    mockUseProviderHealth.mockReturnValue({ data: [], isLoading: false })
    mockUseSLADefinitions.mockReturnValue({ data: [], isLoading: false })
    mockUseActiveViolations.mockReturnValue({ data: [], isLoading: false })
    mockUseFailoverRules.mockReturnValue({ data: [], isLoading: false })
    renderPage()
    await userEvent.click(screen.getByText('SLA Definitions'))
    await userEvent.click(screen.getByText('New SLA'))
    expect(screen.getByText('Create SLA Definition')).toBeInTheDocument()
    expect(screen.getByPlaceholderText('e.g. Production API SLA')).toBeInTheDocument()
    expect(screen.getByPlaceholderText('e.g. openai, anthropic')).toBeInTheDocument()
    expect(screen.getByPlaceholderText('e.g. gpt-4*, claude*')).toBeInTheDocument()
    await userEvent.click(screen.getByText('Cancel'))
    expect(screen.queryByText('Create SLA Definition')).not.toBeInTheDocument()
  })

  it('submits create SLA definition form', async () => {
    const mockMutateAsync = vi.fn().mockResolvedValue({})
    mockUseCreateSLADefinition.mockReturnValue({ mutateAsync: mockMutateAsync, isPending: false })
    mockUseProviderHealth.mockReturnValue({ data: [], isLoading: false })
    mockUseSLADefinitions.mockReturnValue({ data: [], isLoading: false })
    mockUseActiveViolations.mockReturnValue({ data: [], isLoading: false })
    mockUseFailoverRules.mockReturnValue({ data: [], isLoading: false })
    renderPage()
    await userEvent.click(screen.getByText('SLA Definitions'))
    await userEvent.click(screen.getByText('New SLA'))
    await userEvent.type(screen.getByPlaceholderText('e.g. Production API SLA'), 'My SLA')
    await userEvent.type(screen.getByPlaceholderText('e.g. openai, anthropic'), 'openai')
    await userEvent.click(screen.getByRole('button', { name: 'Create' }))
    expect(mockMutateAsync).toHaveBeenCalled()
  })

  it('renders SLA definitions with provider and model badges', async () => {
    mockUseProviderHealth.mockReturnValue({ data: [], isLoading: false })
    mockUseSLADefinitions.mockReturnValue({
      data: [
        {
          id: 'd1',
          name: 'Prod SLA',
          provider: 'openai',
          model_pattern: 'gpt-4*',
          is_active: true,
          target_p50_ms: 500,
          target_p95_ms: 2000,
          target_p99_ms: 5000,
          target_error_rate: 0.01,
          target_availability: 0.999,
          evaluation_window_minutes: 60,
        },
      ],
      isLoading: false,
    })
    mockUseActiveViolations.mockReturnValue({ data: [], isLoading: false })
    mockUseFailoverRules.mockReturnValue({ data: [], isLoading: false })
    renderPage()
    await userEvent.click(screen.getByText('SLA Definitions'))
    expect(screen.getByText('Prod SLA')).toBeInTheDocument()
    expect(screen.getByText('openai')).toBeInTheDocument()
    expect(screen.getByText('gpt-4*')).toBeInTheDocument()
    expect(screen.getByText('Active')).toBeInTheDocument()
    expect(screen.getByText('500ms')).toBeInTheDocument()
    expect(screen.getByText('2000ms')).toBeInTheDocument()
    expect(screen.getByText('5000ms')).toBeInTheDocument()
    expect(screen.getByText('1.00%')).toBeInTheDocument()
    expect(screen.getByText('99.9%')).toBeInTheDocument()
    expect(screen.getByText('60m')).toBeInTheDocument()
  })

  it('renders inactive SLA definition badge', async () => {
    mockUseProviderHealth.mockReturnValue({ data: [], isLoading: false })
    mockUseSLADefinitions.mockReturnValue({
      data: [
        {
          id: 'd2',
          name: 'Old SLA',
          provider: '',
          model_pattern: '',
          is_active: false,
          target_error_rate: 0.02,
          target_availability: 0.99,
          evaluation_window_minutes: 30,
        },
      ],
      isLoading: false,
    })
    mockUseActiveViolations.mockReturnValue({ data: [], isLoading: false })
    mockUseFailoverRules.mockReturnValue({ data: [], isLoading: false })
    renderPage()
    await userEvent.click(screen.getByText('SLA Definitions'))
    expect(screen.getByText('Inactive')).toBeInTheDocument()
  })

  it('switches to Violations tab and shows empty state', async () => {
    mockUseProviderHealth.mockReturnValue({ data: [], isLoading: false })
    mockUseSLADefinitions.mockReturnValue({ data: [], isLoading: false })
    mockUseActiveViolations.mockReturnValue({ data: [], isLoading: false })
    mockUseFailoverRules.mockReturnValue({ data: [], isLoading: false })
    renderPage()
    await userEvent.click(screen.getByText('Violations'))
    expect(screen.getByText('No active violations')).toBeInTheDocument()
    expect(screen.getByText('All providers are operating within SLA targets.')).toBeInTheDocument()
  })

  it('renders violation data in table', async () => {
    mockUseProviderHealth.mockReturnValue({ data: [], isLoading: false })
    mockUseSLADefinitions.mockReturnValue({ data: [], isLoading: false })
    mockUseActiveViolations.mockReturnValue({
      data: [
        {
          id: 'v1',
          violation_type: 'error_rate',
          provider: 'openai',
          model: 'gpt-4o',
          threshold_value: 0.01,
          actual_value: 0.05,
          resolved_at: null,
          created_at: '2025-06-01T12:00:00Z',
        },
      ],
      isLoading: false,
    })
    mockUseFailoverRules.mockReturnValue({ data: [], isLoading: false })
    renderPage()
    await userEvent.click(screen.getByText('Violations'))
    expect(screen.getByText('error_rate')).toBeInTheDocument()
    expect(screen.getByText('0.05')).toBeInTheDocument()
    expect(screen.getByText('0.01')).toBeInTheDocument()
    const activeStatuses = screen.getAllByText('Active')
    expect(activeStatuses.length).toBeGreaterThan(0)
  })

  it('renders resolved violation without resolve button', async () => {
    mockUseProviderHealth.mockReturnValue({ data: [], isLoading: false })
    mockUseSLADefinitions.mockReturnValue({ data: [], isLoading: false })
    mockUseActiveViolations.mockReturnValue({
      data: [
        {
          id: 'v2',
          violation_type: 'latency_p95',
          provider: 'anthropic',
          model: 'claude-3',
          threshold_value: 2000,
          actual_value: 3500,
          resolved_at: '2025-06-02T14:00:00Z',
          created_at: '2025-06-01T12:00:00Z',
        },
      ],
      isLoading: false,
    })
    mockUseFailoverRules.mockReturnValue({ data: [], isLoading: false })
    renderPage()
    await userEvent.click(screen.getByText('Violations'))
    expect(screen.getByText('Resolved')).toBeInTheDocument()
    expect(screen.queryByTitle('Resolve')).not.toBeInTheDocument()
  })

  it('switches to Failover Rules tab and shows empty state', async () => {
    mockUseProviderHealth.mockReturnValue({ data: [], isLoading: false })
    mockUseSLADefinitions.mockReturnValue({ data: [], isLoading: false })
    mockUseActiveViolations.mockReturnValue({ data: [], isLoading: false })
    mockUseFailoverRules.mockReturnValue({ data: [], isLoading: false })
    renderPage()
    await userEvent.click(screen.getByText('Failover Rules'))
    expect(screen.getByText('No failover rules')).toBeInTheDocument()
    expect(screen.getByText('Create rules to automatically failover between models.')).toBeInTheDocument()
  })

  it('shows New Failover Rule button only on failover tab', async () => {
    mockUseProviderHealth.mockReturnValue({ data: [], isLoading: false })
    mockUseSLADefinitions.mockReturnValue({ data: [], isLoading: false })
    mockUseActiveViolations.mockReturnValue({ data: [], isLoading: false })
    mockUseFailoverRules.mockReturnValue({ data: [], isLoading: false })
    renderPage()
    expect(screen.queryByText('New Failover Rule')).not.toBeInTheDocument()
    await userEvent.click(screen.getByText('Failover Rules'))
    expect(screen.getByText('New Failover Rule')).toBeInTheDocument()
  })

  it('opens and closes create failover rule modal', async () => {
    mockUseProviderHealth.mockReturnValue({ data: [], isLoading: false })
    mockUseSLADefinitions.mockReturnValue({ data: [], isLoading: false })
    mockUseActiveViolations.mockReturnValue({ data: [], isLoading: false })
    mockUseFailoverRules.mockReturnValue({ data: [], isLoading: false })
    renderPage()
    await userEvent.click(screen.getByText('Failover Rules'))
    await userEvent.click(screen.getByText('New Failover Rule'))
    expect(screen.getByText('Create Failover Rule')).toBeInTheDocument()
    expect(screen.getByPlaceholderText('e.g. gpt-4o')).toBeInTheDocument()
    expect(screen.getByPlaceholderText('e.g. claude-sonnet-4')).toBeInTheDocument()
    await userEvent.click(screen.getByText('Cancel'))
    expect(screen.queryByText('Create Failover Rule')).not.toBeInTheDocument()
  })

  it('submits create failover rule form', async () => {
    const mockMutateAsync = vi.fn().mockResolvedValue({})
    mockUseCreateFailoverRule.mockReturnValue({ mutateAsync: mockMutateAsync, isPending: false })
    mockUseProviderHealth.mockReturnValue({ data: [], isLoading: false })
    mockUseSLADefinitions.mockReturnValue({ data: [], isLoading: false })
    mockUseActiveViolations.mockReturnValue({ data: [], isLoading: false })
    mockUseFailoverRules.mockReturnValue({ data: [], isLoading: false })
    renderPage()
    await userEvent.click(screen.getByText('Failover Rules'))
    await userEvent.click(screen.getByText('New Failover Rule'))
    await userEvent.type(screen.getByPlaceholderText('e.g. gpt-4o'), 'gpt-4o')
    await userEvent.type(screen.getByPlaceholderText('e.g. claude-sonnet-4'), 'claude-sonnet-4')
    await userEvent.click(screen.getByRole('button', { name: 'Create' }))
    expect(mockMutateAsync).toHaveBeenCalled()
  })

  it('renders failover rules with model names and status', async () => {
    mockUseProviderHealth.mockReturnValue({ data: [], isLoading: false })
    mockUseSLADefinitions.mockReturnValue({ data: [], isLoading: false })
    mockUseActiveViolations.mockReturnValue({ data: [], isLoading: false })
    mockUseFailoverRules.mockReturnValue({
      data: [
        {
          id: 'f1',
          primary_model: 'gpt-4o',
          fallback_model: 'claude-sonnet-4',
          is_active: true,
          trigger_condition: 'error_rate',
          trigger_threshold: 0.05,
          cooldown_minutes: 15,
          last_triggered_at: null,
        },
      ],
      isLoading: false,
    })
    renderPage()
    await userEvent.click(screen.getByText('Failover Rules'))
    expect(screen.getByText('gpt-4o')).toBeInTheDocument()
    expect(screen.getByText('claude-sonnet-4')).toBeInTheDocument()
    const activeStatuses = screen.getAllByText('Active')
    expect(activeStatuses.length).toBeGreaterThan(0)
    expect(screen.getByText('error_rate: 0.05')).toBeInTheDocument()
    expect(screen.getByText('Cooldown: 15 minutes')).toBeInTheDocument()
  })

  it('renders failover rule with last triggered date', async () => {
    mockUseProviderHealth.mockReturnValue({ data: [], isLoading: false })
    mockUseSLADefinitions.mockReturnValue({ data: [], isLoading: false })
    mockUseActiveViolations.mockReturnValue({ data: [], isLoading: false })
    mockUseFailoverRules.mockReturnValue({
      data: [
        {
          id: 'f2',
          primary_model: 'gpt-4',
          fallback_model: 'gpt-3.5',
          is_active: false,
          trigger_condition: 'latency_p95',
          trigger_threshold: 3000,
          cooldown_minutes: 30,
          last_triggered_at: '2025-06-01T10:00:00Z',
        },
      ],
      isLoading: false,
    })
    renderPage()
    await userEvent.click(screen.getByText('Failover Rules'))
    expect(screen.getByText('Inactive')).toBeInTheDocument()
    expect(screen.getByText(/Last triggered:/)).toBeInTheDocument()
  })

  it('displays tab counts when data is present', () => {
    mockUseProviderHealth.mockReturnValue({
      data: [
        { id: '1', provider: 'openai', model: 'gpt-4o', bucket_start: '2025-01-15T10:00:00Z', request_count: 100, error_count: 1, p50_latency_ms: 200, p95_latency_ms: 800, p99_latency_ms: 1500, total_tokens: 5000 },
      ],
      isLoading: false,
    })
    mockUseSLADefinitions.mockReturnValue({
      data: [
        { id: 'd1', name: 'SLA1', provider: '', model_pattern: '', is_active: true, target_error_rate: 0.01, target_availability: 0.999, evaluation_window_minutes: 60 },
        { id: 'd2', name: 'SLA2', provider: '', model_pattern: '', is_active: true, target_error_rate: 0.01, target_availability: 0.999, evaluation_window_minutes: 60 },
      ],
      isLoading: false,
    })
    mockUseActiveViolations.mockReturnValue({ data: [], isLoading: false })
    mockUseFailoverRules.mockReturnValue({ data: [], isLoading: false })
    renderPage()
    expect(screen.getByText('1')).toBeInTheDocument()
    expect(screen.getByText('2')).toBeInTheDocument()
  })

  it('renders violation with missing provider and model as dashes', async () => {
    mockUseProviderHealth.mockReturnValue({ data: [], isLoading: false })
    mockUseSLADefinitions.mockReturnValue({ data: [], isLoading: false })
    mockUseActiveViolations.mockReturnValue({
      data: [
        {
          id: 'v3',
          violation_type: 'availability',
          provider: '',
          model: '',
          threshold_value: 0.999,
          actual_value: 0.95,
          resolved_at: null,
          created_at: null,
        },
      ],
      isLoading: false,
    })
    mockUseFailoverRules.mockReturnValue({ data: [], isLoading: false })
    renderPage()
    await userEvent.click(screen.getByText('Violations'))
    const dashes = screen.getAllByText('--')
    expect(dashes.length).toBeGreaterThanOrEqual(2)
  })

  it('shows resolve button for active violations', async () => {
    mockUseProviderHealth.mockReturnValue({ data: [], isLoading: false })
    mockUseSLADefinitions.mockReturnValue({ data: [], isLoading: false })
    mockUseActiveViolations.mockReturnValue({
      data: [
        {
          id: 'v4',
          violation_type: 'error_rate',
          provider: 'openai',
          model: 'gpt-4o',
          threshold_value: 0.01,
          actual_value: 0.05,
          resolved_at: null,
          created_at: '2025-06-01T12:00:00Z',
        },
      ],
      isLoading: false,
    })
    mockUseFailoverRules.mockReturnValue({ data: [], isLoading: false })
    renderPage()
    await userEvent.click(screen.getByText('Violations'))
    expect(screen.getByTitle('Resolve')).toBeInTheDocument()
  })

  it('shows delete and manual trigger buttons on failover rules', async () => {
    mockUseProviderHealth.mockReturnValue({ data: [], isLoading: false })
    mockUseSLADefinitions.mockReturnValue({ data: [], isLoading: false })
    mockUseActiveViolations.mockReturnValue({ data: [], isLoading: false })
    mockUseFailoverRules.mockReturnValue({
      data: [
        {
          id: 'f3',
          primary_model: 'gpt-4o',
          fallback_model: 'claude-3',
          is_active: true,
          trigger_condition: 'error_rate',
          trigger_threshold: 0.05,
          cooldown_minutes: 10,
          last_triggered_at: null,
        },
      ],
      isLoading: false,
    })
    renderPage()
    await userEvent.click(screen.getByText('Failover Rules'))
    expect(screen.getByTitle('Manual trigger')).toBeInTheDocument()
    expect(screen.getByTitle('Delete')).toBeInTheDocument()
  })

  it('shows delete button on SLA definitions', async () => {
    mockUseProviderHealth.mockReturnValue({ data: [], isLoading: false })
    mockUseSLADefinitions.mockReturnValue({
      data: [
        {
          id: 'd3',
          name: 'Test SLA',
          provider: 'openai',
          model_pattern: '',
          is_active: true,
          target_error_rate: 0.01,
          target_availability: 0.999,
          evaluation_window_minutes: 60,
        },
      ],
      isLoading: false,
    })
    mockUseActiveViolations.mockReturnValue({ data: [], isLoading: false })
    mockUseFailoverRules.mockReturnValue({ data: [], isLoading: false })
    renderPage()
    await userEvent.click(screen.getByText('SLA Definitions'))
    expect(screen.getByTitle('Delete')).toBeInTheDocument()
  })

  it('create SLA form disables Create button when name is empty', async () => {
    mockUseProviderHealth.mockReturnValue({ data: [], isLoading: false })
    mockUseSLADefinitions.mockReturnValue({ data: [], isLoading: false })
    mockUseActiveViolations.mockReturnValue({ data: [], isLoading: false })
    mockUseFailoverRules.mockReturnValue({ data: [], isLoading: false })
    renderPage()
    await userEvent.click(screen.getByText('SLA Definitions'))
    await userEvent.click(screen.getByText('New SLA'))
    const createBtn = screen.getByRole('button', { name: 'Create' })
    expect(createBtn).toBeDisabled()
  })

  it('create failover form disables Create button when models are empty', async () => {
    mockUseProviderHealth.mockReturnValue({ data: [], isLoading: false })
    mockUseSLADefinitions.mockReturnValue({ data: [], isLoading: false })
    mockUseActiveViolations.mockReturnValue({ data: [], isLoading: false })
    mockUseFailoverRules.mockReturnValue({ data: [], isLoading: false })
    renderPage()
    await userEvent.click(screen.getByText('Failover Rules'))
    await userEvent.click(screen.getByText('New Failover Rule'))
    const createBtn = screen.getByRole('button', { name: 'Create' })
    expect(createBtn).toBeDisabled()
  })
})
