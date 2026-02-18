import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import Workflows from './Workflows'

const mockUseWorkflows = vi.fn()
const mockUseCreateWorkflow = vi.fn()
const mockUseExecuteWorkflow = vi.fn()
const mockUseWorkflowExecutions = vi.fn()
const mockUseWorkflowExecution = vi.fn()

vi.mock('../api/hooks', () => ({
  useWorkflows: () => mockUseWorkflows(),
  useCreateWorkflow: () => mockUseCreateWorkflow(),
  useExecuteWorkflow: () => mockUseExecuteWorkflow(),
  useWorkflowExecutions: () => mockUseWorkflowExecutions(),
  useWorkflowExecution: () => mockUseWorkflowExecution(),
}))

vi.mock('../components/Toast', () => ({
  useToast: () => vi.fn(),
}))

function renderPage() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter>
        <Workflows />
      </MemoryRouter>
    </QueryClientProvider>
  )
}

describe('Workflows', () => {
  beforeEach(() => {
    mockUseCreateWorkflow.mockReturnValue({ mutateAsync: vi.fn(), isPending: false })
    mockUseExecuteWorkflow.mockReturnValue({ mutateAsync: vi.fn(), isPending: false })
    mockUseWorkflowExecutions.mockReturnValue({ data: [] })
    mockUseWorkflowExecution.mockReturnValue({ data: null })
  })

  it('shows loading state', () => {
    mockUseWorkflows.mockReturnValue({ data: undefined, isLoading: true, error: null })
    renderPage()
    expect(screen.getByText('Workflows')).toBeInTheDocument()
    expect(screen.getByText('Pre-built and custom workflow templates')).toBeInTheDocument()
  })

  it('shows error state', () => {
    mockUseWorkflows.mockReturnValue({ data: undefined, isLoading: false, error: new Error('fail') })
    renderPage()
    expect(screen.getByText('Failed to load workflows')).toBeInTheDocument()
  })

  it('shows Create Workflow button', () => {
    mockUseWorkflows.mockReturnValue({ data: [], isLoading: false, error: null })
    renderPage()
    expect(screen.getAllByText('Create Workflow').length).toBeGreaterThanOrEqual(1)
  })

  it('shows pre-built templates', () => {
    mockUseWorkflows.mockReturnValue({ data: [], isLoading: false, error: null })
    renderPage()
    expect(screen.getByText('Pre-built Templates')).toBeInTheDocument()
    expect(screen.getByText('Research Agent')).toBeInTheDocument()
    expect(screen.getByText('Coding Agent')).toBeInTheDocument()
    expect(screen.getByText('Data Analysis Agent')).toBeInTheDocument()
  })

  it('shows custom workflows when data exists', () => {
    mockUseWorkflows.mockReturnValue({
      data: [
        { id: 'w1', name: 'My Pipeline', template_type: 'research', is_active: true, description: 'Custom research', created_at: '2025-01-01T00:00:00Z' },
      ],
      isLoading: false,
      error: null,
    })
    renderPage()
    expect(screen.getByText('Custom Workflows')).toBeInTheDocument()
    expect(screen.getByText('My Pipeline')).toBeInTheDocument()
  })

  it('shows empty state for custom workflows when none exist', () => {
    mockUseWorkflows.mockReturnValue({ data: [], isLoading: false, error: null })
    renderPage()
    expect(screen.getByText('No custom workflows')).toBeInTheDocument()
    expect(screen.getByText('Create custom workflows based on the templates above.')).toBeInTheDocument()
  })

  it('shows execution history section', () => {
    mockUseWorkflows.mockReturnValue({ data: [], isLoading: false, error: null })
    renderPage()
    expect(screen.getByText('Execution History')).toBeInTheDocument()
    expect(screen.getByText('No executions yet. Test a workflow above to see execution history.')).toBeInTheDocument()
  })

  it('pre-built templates show descriptions', () => {
    mockUseWorkflows.mockReturnValue({ data: [], isLoading: false, error: null })
    renderPage()
    expect(screen.getByText('Multi-source research with web search, database queries, and report generation')).toBeInTheDocument()
    expect(screen.getByText('Iterative code generation with analysis and refinement')).toBeInTheDocument()
    expect(screen.getByText('SQL query generation, data analysis, and visualization recommendations')).toBeInTheDocument()
  })

  it('template cards have Test Workflow buttons', () => {
    mockUseWorkflows.mockReturnValue({ data: [], isLoading: false, error: null })
    renderPage()
    const testButtons = screen.getAllByText('Test Workflow')
    expect(testButtons.length).toBe(3)
  })

  it('execution history shows column headers when data exists', () => {
    mockUseWorkflows.mockReturnValue({ data: [], isLoading: false, error: null })
    mockUseWorkflowExecutions.mockReturnValue({
      data: [
        {
          id: 'exec-12345678-abcd',
          workflow_name: 'My Research',
          status: 'completed',
          total_cost: 0.0512,
          started_at: '2025-01-15T10:00:00Z',
          completed_at: '2025-01-15T10:01:00Z',
        },
      ],
    })
    renderPage()
    expect(screen.getByText('Workflow')).toBeInTheDocument()
    expect(screen.getByText('Status')).toBeInTheDocument()
    expect(screen.getByText('Cost')).toBeInTheDocument()
    expect(screen.getByText('Duration')).toBeInTheDocument()
  })

  it('shows execution data when executions exist', () => {
    mockUseWorkflows.mockReturnValue({ data: [], isLoading: false, error: null })
    mockUseWorkflowExecutions.mockReturnValue({
      data: [
        {
          id: 'exec-12345678-abcd',
          workflow_name: 'My Research',
          status: 'completed',
          total_cost: 0.0512,
          started_at: '2025-01-15T10:00:00Z',
          completed_at: '2025-01-15T10:01:00Z',
        },
      ],
    })
    renderPage()
    expect(screen.getByText('My Research')).toBeInTheDocument()
    expect(screen.getByText('completed')).toBeInTheDocument()
    expect(screen.getByText('$0.0512')).toBeInTheDocument()
  })
})
