import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import Agents from './Agents'

const mockUseAgents = vi.fn()
const mockUseCreateAgent = vi.fn()
const mockUseUpdateAgent = vi.fn()
const mockUseDeleteAgent = vi.fn()
const mockUseTestAgent = vi.fn()
const mockUseSyncMCPToGateway = vi.fn()
const mockUseGatewayConfigPreview = vi.fn()

vi.mock('../api/hooks', () => ({
  useAgents: () => mockUseAgents(),
  useCreateAgent: () => mockUseCreateAgent(),
  useUpdateAgent: () => mockUseUpdateAgent(),
  useDeleteAgent: () => mockUseDeleteAgent(),
  useTestAgent: () => mockUseTestAgent(),
  useSyncMCPToGateway: () => mockUseSyncMCPToGateway(),
  useGatewayConfigPreview: () => mockUseGatewayConfigPreview(),
}))

vi.mock('../components/Toast', () => ({
  useToast: () => vi.fn(),
}))

function renderPage() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter>
        <Agents />
      </MemoryRouter>
    </QueryClientProvider>
  )
}

describe('Agents', () => {
  beforeEach(() => {
    mockUseCreateAgent.mockReturnValue({ mutateAsync: vi.fn(), isPending: false })
    mockUseUpdateAgent.mockReturnValue({ mutateAsync: vi.fn(), isPending: false })
    mockUseDeleteAgent.mockReturnValue({ mutateAsync: vi.fn(), isPending: false })
    mockUseTestAgent.mockReturnValue({ mutateAsync: vi.fn(), isPending: false })
    mockUseSyncMCPToGateway.mockReturnValue({ mutateAsync: vi.fn(), isPending: false })
    mockUseGatewayConfigPreview.mockReturnValue({ data: null, refetch: vi.fn(), isFetching: false })
  })

  it('shows loading state', () => {
    mockUseAgents.mockReturnValue({ data: undefined, isLoading: true, error: null })
    renderPage()
    expect(screen.getByText('A2A Agents')).toBeInTheDocument()
    expect(screen.getByText('Configure Agent-to-Agent protocol agents')).toBeInTheDocument()
  })

  it('shows error state', () => {
    mockUseAgents.mockReturnValue({ data: undefined, isLoading: false, error: new Error('fail') })
    renderPage()
    expect(screen.getByText('Failed to load A2A agents')).toBeInTheDocument()
  })

  it('shows Add Agent button', () => {
    mockUseAgents.mockReturnValue({
      data: [{ id: 'a1', name: 'code-reviewer', url: 'http://localhost:8088', is_active: true, skills: ['review'], description: 'Reviews code' }],
      isLoading: false,
      error: null,
    })
    renderPage()
    expect(screen.getByText('Add Agent')).toBeInTheDocument()
  })

  it('shows agent list with data', () => {
    mockUseAgents.mockReturnValue({
      data: [
        { id: 'a1', name: 'code-reviewer', url: 'http://localhost:8088', is_active: true, skills: ['review', 'testing'], description: 'Reviews code' },
        { id: 'a2', name: 'doc-writer', url: 'http://localhost:8089', is_active: false, skills: ['docs'], description: '' },
      ],
      isLoading: false,
      error: null,
    })
    renderPage()
    expect(screen.getByText('code-reviewer')).toBeInTheDocument()
    expect(screen.getByText('doc-writer')).toBeInTheDocument()
  })

  it('shows empty state when no agents', () => {
    mockUseAgents.mockReturnValue({ data: [], isLoading: false, error: null })
    renderPage()
    expect(screen.getByText('No A2A agents configured')).toBeInTheDocument()
    expect(screen.getByText('Add A2A agents to enable agent-to-agent communication through your gateway.')).toBeInTheDocument()
  })

  it('opens create form when Add Agent is clicked', async () => {
    mockUseAgents.mockReturnValue({
      data: [{ id: 'a1', name: 'code-reviewer', url: 'http://localhost:8088', is_active: true, skills: [], description: '' }],
      isLoading: false,
      error: null,
    })
    renderPage()
    await userEvent.click(screen.getByText('Add Agent'))
    expect(screen.getByText('Add A2A Agent')).toBeInTheDocument()
    expect(screen.getByLabelText('Name')).toBeInTheDocument()
    expect(screen.getByLabelText('URL')).toBeInTheDocument()
    expect(screen.getByLabelText('Description')).toBeInTheDocument()
    expect(screen.getByLabelText('Skills (comma-separated)')).toBeInTheDocument()
  })

  it('submits create form and calls mutateAsync', async () => {
    const mockCreate = vi.fn().mockResolvedValue({})
    mockUseCreateAgent.mockReturnValue({ mutateAsync: mockCreate, isPending: false })
    mockUseAgents.mockReturnValue({
      data: [{ id: 'a1', name: 'existing', url: 'http://localhost:8088', is_active: true, skills: [], description: '' }],
      isLoading: false,
      error: null,
    })
    renderPage()
    await userEvent.click(screen.getByText('Add Agent'))
    await userEvent.type(screen.getByLabelText('Name'), 'test-agent')
    await userEvent.type(screen.getByLabelText('URL'), 'http://localhost:9000')
    await userEvent.type(screen.getByLabelText('Description'), 'A test agent')
    await userEvent.type(screen.getByLabelText('Skills (comma-separated)'), 'coding, testing')
    const addButtons = screen.getAllByRole('button', { name: 'Add Agent' })
    await userEvent.click(addButtons[addButtons.length - 1])
    await waitFor(() => {
      expect(mockCreate).toHaveBeenCalledWith(
        expect.objectContaining({
          name: 'test-agent',
          url: 'http://localhost:9000',
          description: 'A test agent',
          skills: ['coding', 'testing'],
        })
      )
    })
  })

  it('closes form on cancel', async () => {
    mockUseAgents.mockReturnValue({
      data: [{ id: 'a1', name: 'existing', url: 'http://localhost:8088', is_active: true, skills: [], description: '' }],
      isLoading: false,
      error: null,
    })
    renderPage()
    await userEvent.click(screen.getByText('Add Agent'))
    expect(screen.getByText('Add A2A Agent')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Cancel' }))
    expect(screen.queryByText('Add A2A Agent')).not.toBeInTheDocument()
  })

  it('opens edit form with pre-filled data when Edit is clicked', async () => {
    mockUseAgents.mockReturnValue({
      data: [{ id: 'a1', name: 'code-reviewer', url: 'http://localhost:8088', is_active: true, skills: ['review', 'testing'], description: 'Reviews code' }],
      isLoading: false,
      error: null,
    })
    renderPage()
    await userEvent.click(screen.getByText('Edit'))
    expect(screen.getByText('Edit A2A Agent')).toBeInTheDocument()
    expect(screen.getByLabelText('Name')).toHaveValue('code-reviewer')
    expect(screen.getByLabelText('URL')).toHaveValue('http://localhost:8088')
    expect(screen.getByLabelText('Description')).toHaveValue('Reviews code')
    expect(screen.getByLabelText('Skills (comma-separated)')).toHaveValue('review, testing')
    expect(screen.getByRole('button', { name: 'Update Agent' })).toBeInTheDocument()
  })

  it('submits edit form and calls updateAgent mutateAsync', async () => {
    const mockUpdate = vi.fn().mockResolvedValue({})
    mockUseUpdateAgent.mockReturnValue({ mutateAsync: mockUpdate, isPending: false })
    mockUseAgents.mockReturnValue({
      data: [{ id: 'a1', name: 'code-reviewer', url: 'http://localhost:8088', is_active: true, skills: ['review'], description: 'Reviews code' }],
      isLoading: false,
      error: null,
    })
    renderPage()
    await userEvent.click(screen.getByText('Edit'))
    await userEvent.clear(screen.getByLabelText('Name'))
    await userEvent.type(screen.getByLabelText('Name'), 'updated-agent')
    await userEvent.click(screen.getByRole('button', { name: 'Update Agent' }))
    await waitFor(() => {
      expect(mockUpdate).toHaveBeenCalledWith(
        expect.objectContaining({ id: 'a1', data: expect.objectContaining({ name: 'updated-agent' }) })
      )
    })
  })

  it('shows delete confirmation dialog when Delete is clicked', async () => {
    mockUseAgents.mockReturnValue({
      data: [{ id: 'a1', name: 'code-reviewer', url: 'http://localhost:8088', is_active: true, skills: [], description: '' }],
      isLoading: false,
      error: null,
    })
    renderPage()
    await userEvent.click(screen.getByText('Delete'))
    expect(screen.getByText('Are you sure you want to delete this A2A agent? This action cannot be undone.')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Delete Agent' })).toBeInTheDocument()
  })

  it('calls deleteAgent mutateAsync on confirm delete', async () => {
    const mockDelete = vi.fn().mockResolvedValue({})
    mockUseDeleteAgent.mockReturnValue({ mutateAsync: mockDelete, isPending: false })
    mockUseAgents.mockReturnValue({
      data: [{ id: 'a1', name: 'code-reviewer', url: 'http://localhost:8088', is_active: true, skills: [], description: '' }],
      isLoading: false,
      error: null,
    })
    renderPage()
    await userEvent.click(screen.getByText('Delete'))
    await userEvent.click(screen.getByRole('button', { name: 'Delete Agent' }))
    await waitFor(() => {
      expect(mockDelete).toHaveBeenCalledWith('a1')
    })
  })

  it('cancels delete confirmation dialog', async () => {
    mockUseAgents.mockReturnValue({
      data: [{ id: 'a1', name: 'code-reviewer', url: 'http://localhost:8088', is_active: true, skills: [], description: '' }],
      isLoading: false,
      error: null,
    })
    renderPage()
    await userEvent.click(screen.getByText('Delete'))
    expect(screen.getByText('Are you sure you want to delete this A2A agent? This action cannot be undone.')).toBeInTheDocument()
    const cancelButtons = screen.getAllByText('Cancel')
    await userEvent.click(cancelButtons[cancelButtons.length - 1])
    expect(screen.queryByText('Are you sure you want to delete this A2A agent? This action cannot be undone.')).not.toBeInTheDocument()
  })

  it('calls testAgent mutateAsync when Test button is clicked', async () => {
    const mockTest = vi.fn().mockResolvedValue({ status: 'ok', message: 'Connected' })
    mockUseTestAgent.mockReturnValue({ mutateAsync: mockTest, isPending: false })
    mockUseAgents.mockReturnValue({
      data: [{ id: 'a1', name: 'code-reviewer', url: 'http://localhost:8088', is_active: true, skills: [], description: '' }],
      isLoading: false,
      error: null,
    })
    renderPage()
    await userEvent.click(screen.getByText('Test'))
    await waitFor(() => {
      expect(mockTest).toHaveBeenCalledWith('a1')
    })
  })

  it('toggles active status when Active/Inactive button is clicked', async () => {
    const mockUpdate = vi.fn().mockResolvedValue({})
    mockUseUpdateAgent.mockReturnValue({ mutateAsync: mockUpdate, isPending: false })
    mockUseAgents.mockReturnValue({
      data: [{ id: 'a1', name: 'code-reviewer', url: 'http://localhost:8088', is_active: true, skills: [], description: '' }],
      isLoading: false,
      error: null,
    })
    renderPage()
    await userEvent.click(screen.getByText('Active'))
    await waitFor(() => {
      expect(mockUpdate).toHaveBeenCalledWith({ id: 'a1', data: { is_active: false } })
    })
  })

  it('displays agent URL and skills badges', () => {
    mockUseAgents.mockReturnValue({
      data: [{
        id: 'a1', name: 'code-reviewer', url: 'http://localhost:8088',
        is_active: true, skills: ['code-review', 'testing', 'documentation'], description: 'Reviews code',
      }],
      isLoading: false,
      error: null,
    })
    renderPage()
    expect(screen.getByText('http://localhost:8088')).toBeInTheDocument()
    expect(screen.getByText('code-review')).toBeInTheDocument()
    expect(screen.getByText('testing')).toBeInTheDocument()
    expect(screen.getByText('documentation')).toBeInTheDocument()
    expect(screen.getByText('Reviews code')).toBeInTheDocument()
  })

  it('does not display skills section when agent has no skills', () => {
    mockUseAgents.mockReturnValue({
      data: [{ id: 'a1', name: 'basic-agent', url: 'http://localhost:8088', is_active: true, skills: [], description: null }],
      isLoading: false,
      error: null,
    })
    renderPage()
    expect(screen.queryByText('Skills:')).not.toBeInTheDocument()
  })

  it('shows Preview Config panel when clicked', async () => {
    const mockRefetch = vi.fn()
    mockUseGatewayConfigPreview.mockReturnValue({
      data: { active_servers: 2, active_agents: 1, config_yaml: 'agents:\n  - name: reviewer' },
      refetch: mockRefetch,
      isFetching: false,
    })
    mockUseAgents.mockReturnValue({
      data: [{ id: 'a1', name: 'code-reviewer', url: 'http://localhost:8088', is_active: true, skills: [], description: '' }],
      isLoading: false,
      error: null,
    })
    renderPage()
    await userEvent.click(screen.getByText('Preview Config'))
    expect(mockRefetch).toHaveBeenCalled()
    expect(screen.getByText('Agent Gateway Config Preview')).toBeInTheDocument()
    expect(screen.getByText('2 MCP server(s) and 1 A2A agent(s) will be deployed')).toBeInTheDocument()
    expect(screen.getByText(/agents:/)).toBeInTheDocument()
  })

  it('hides Preview Config panel when clicked again', async () => {
    mockUseGatewayConfigPreview.mockReturnValue({
      data: { active_servers: 1, active_agents: 0, config_yaml: 'yaml: content' },
      refetch: vi.fn(),
      isFetching: false,
    })
    mockUseAgents.mockReturnValue({
      data: [{ id: 'a1', name: 'code-reviewer', url: 'http://localhost:8088', is_active: true, skills: [], description: '' }],
      isLoading: false,
      error: null,
    })
    renderPage()
    await userEvent.click(screen.getByText('Preview Config'))
    expect(screen.getByText('Agent Gateway Config Preview')).toBeInTheDocument()
    await userEvent.click(screen.getByText('Hide Preview'))
    expect(screen.queryByText('Agent Gateway Config Preview')).not.toBeInTheDocument()
  })

  it('shows loading preview text when fetching preview', async () => {
    mockUseGatewayConfigPreview.mockReturnValue({ data: null, refetch: vi.fn(), isFetching: true })
    mockUseAgents.mockReturnValue({
      data: [{ id: 'a1', name: 'code-reviewer', url: 'http://localhost:8088', is_active: true, skills: [], description: '' }],
      isLoading: false,
      error: null,
    })
    renderPage()
    await userEvent.click(screen.getByText('Preview Config'))
    expect(screen.getByText('Loading preview...')).toBeInTheDocument()
  })

  it('shows no preview available when preview data is null', async () => {
    mockUseGatewayConfigPreview.mockReturnValue({ data: null, refetch: vi.fn(), isFetching: false })
    mockUseAgents.mockReturnValue({
      data: [{ id: 'a1', name: 'code-reviewer', url: 'http://localhost:8088', is_active: true, skills: [], description: '' }],
      isLoading: false,
      error: null,
    })
    renderPage()
    await userEvent.click(screen.getByText('Preview Config'))
    expect(screen.getByText('No preview available')).toBeInTheDocument()
  })

  it('opens deploy confirmation dialog', async () => {
    mockUseAgents.mockReturnValue({
      data: [{ id: 'a1', name: 'code-reviewer', url: 'http://localhost:8088', is_active: true, skills: [], description: '' }],
      isLoading: false,
      error: null,
    })
    renderPage()
    await userEvent.click(screen.getByRole('button', { name: /Deploy to Gateway/ }))
    expect(screen.getByText(/This will push all active MCP servers and A2A agents/)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Deploy' })).toBeInTheDocument()
  })

  it('calls syncToGateway on deploy confirm', async () => {
    const mockSync = vi.fn().mockResolvedValue({ status: 'ok', servers_synced: 1 })
    mockUseSyncMCPToGateway.mockReturnValue({ mutateAsync: mockSync, isPending: false })
    mockUseAgents.mockReturnValue({
      data: [{ id: 'a1', name: 'code-reviewer', url: 'http://localhost:8088', is_active: true, skills: [], description: '' }],
      isLoading: false,
      error: null,
    })
    renderPage()
    await userEvent.click(screen.getByRole('button', { name: /Deploy to Gateway/ }))
    await userEvent.click(screen.getByRole('button', { name: 'Deploy' }))
    await waitFor(() => {
      expect(mockSync).toHaveBeenCalled()
    })
  })

  it('cancels deploy confirmation dialog', async () => {
    mockUseAgents.mockReturnValue({
      data: [{ id: 'a1', name: 'code-reviewer', url: 'http://localhost:8088', is_active: true, skills: [], description: '' }],
      isLoading: false,
      error: null,
    })
    renderPage()
    await userEvent.click(screen.getByRole('button', { name: /Deploy to Gateway/ }))
    expect(screen.getByText(/This will push all active MCP servers and A2A agents/)).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Cancel' }))
    expect(screen.queryByText(/This will push all active MCP servers and A2A agents/)).not.toBeInTheDocument()
  })

  it('shows active count badge on Deploy button', () => {
    mockUseAgents.mockReturnValue({
      data: [
        { id: 'a1', name: 'reviewer', url: 'http://x', is_active: true, skills: [], description: '' },
        { id: 'a2', name: 'writer', url: 'http://y', is_active: true, skills: [], description: '' },
        { id: 'a3', name: 'offline', url: 'http://z', is_active: false, skills: [], description: '' },
      ],
      isLoading: false,
      error: null,
    })
    renderPage()
    expect(screen.getByText('2')).toBeInTheDocument()
  })

  it('shows Inactive badge for inactive agents', () => {
    mockUseAgents.mockReturnValue({
      data: [{ id: 'a1', name: 'inactive-agent', url: 'http://localhost:8088', is_active: false, skills: [], description: '' }],
      isLoading: false,
      error: null,
    })
    renderPage()
    expect(screen.getByText('Inactive')).toBeInTheDocument()
  })

  it('handles agent with null description gracefully', () => {
    mockUseAgents.mockReturnValue({
      data: [{ id: 'a1', name: 'no-desc-agent', url: 'http://localhost:8088', is_active: true, skills: ['skill1'], description: null }],
      isLoading: false,
      error: null,
    })
    renderPage()
    expect(screen.getByText('no-desc-agent')).toBeInTheDocument()
    expect(screen.getByText('http://localhost:8088')).toBeInTheDocument()
    expect(screen.getByText('skill1')).toBeInTheDocument()
  })
})
