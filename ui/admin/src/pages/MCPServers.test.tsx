import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import MCPServers from './MCPServers'

const mockUseMCPServers = vi.fn()
const mockUseCreateMCPServer = vi.fn()
const mockUseUpdateMCPServer = vi.fn()
const mockUseDeleteMCPServer = vi.fn()
const mockUseTestMCPServer = vi.fn()
const mockUseSyncMCPToGateway = vi.fn()
const mockUseGatewayConfigPreview = vi.fn()

vi.mock('../api/hooks', () => ({
  useMCPServers: () => mockUseMCPServers(),
  useCreateMCPServer: () => mockUseCreateMCPServer(),
  useUpdateMCPServer: () => mockUseUpdateMCPServer(),
  useDeleteMCPServer: () => mockUseDeleteMCPServer(),
  useTestMCPServer: () => mockUseTestMCPServer(),
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
        <MCPServers />
      </MemoryRouter>
    </QueryClientProvider>
  )
}

describe('MCPServers', () => {
  beforeEach(() => {
    mockUseCreateMCPServer.mockReturnValue({ mutateAsync: vi.fn(), isPending: false })
    mockUseUpdateMCPServer.mockReturnValue({ mutateAsync: vi.fn(), isPending: false })
    mockUseDeleteMCPServer.mockReturnValue({ mutateAsync: vi.fn(), isPending: false })
    mockUseTestMCPServer.mockReturnValue({ mutateAsync: vi.fn(), isPending: false })
    mockUseSyncMCPToGateway.mockReturnValue({ mutateAsync: vi.fn(), isPending: false })
    mockUseGatewayConfigPreview.mockReturnValue({ data: null, refetch: vi.fn(), isFetching: false })
  })

  it('shows loading state', () => {
    mockUseMCPServers.mockReturnValue({ data: undefined, isLoading: true, error: null })
    renderPage()
    expect(screen.getByText('MCP Servers')).toBeInTheDocument()
    expect(screen.getByText('Configure Model Context Protocol servers')).toBeInTheDocument()
  })

  it('shows error state', () => {
    mockUseMCPServers.mockReturnValue({ data: undefined, isLoading: false, error: new Error('fail') })
    renderPage()
    expect(screen.getByText('Failed to load MCP servers')).toBeInTheDocument()
  })

  it('shows Add Server button', () => {
    mockUseMCPServers.mockReturnValue({
      data: [{ id: 's1', name: 'filesystem', server_type: 'stdio', command: 'npx server', is_active: true, args: [], env: {}, tools: [] }],
      isLoading: false,
      error: null,
    })
    renderPage()
    expect(screen.getByText('Add Server')).toBeInTheDocument()
  })

  it('shows server list with data', () => {
    mockUseMCPServers.mockReturnValue({
      data: [
        { id: 's1', name: 'filesystem', server_type: 'stdio', command: 'npx server-fs', is_active: true, args: ['/workspace'], env: {}, tools: ['read_file'] },
        { id: 's2', name: 'github', server_type: 'http', url: 'http://localhost:3001', is_active: false, args: [], env: {}, tools: [] },
      ],
      isLoading: false,
      error: null,
    })
    renderPage()
    expect(screen.getByText('filesystem')).toBeInTheDocument()
    expect(screen.getByText('github')).toBeInTheDocument()
  })

  it('shows empty state when no servers', () => {
    mockUseMCPServers.mockReturnValue({ data: [], isLoading: false, error: null })
    renderPage()
    expect(screen.getByText('No MCP servers configured')).toBeInTheDocument()
    expect(screen.getByText('Add MCP servers to extend your gateway with tools and context.')).toBeInTheDocument()
  })

  it('opens create form when Add Server is clicked', async () => {
    mockUseMCPServers.mockReturnValue({
      data: [{ id: 's1', name: 'filesystem', server_type: 'stdio', command: 'npx server', is_active: true, args: [], env: {}, tools: [] }],
      isLoading: false,
      error: null,
    })
    renderPage()
    await userEvent.click(screen.getByText('Add Server'))
    expect(screen.getByText('Add MCP Server')).toBeInTheDocument()
    expect(screen.getByLabelText('Name')).toBeInTheDocument()
    expect(screen.getByLabelText('Server Type')).toBeInTheDocument()
  })

  it('shows stdio fields by default in create form', async () => {
    mockUseMCPServers.mockReturnValue({
      data: [{ id: 's1', name: 'fs', server_type: 'stdio', command: 'cmd', is_active: true, args: [], env: {}, tools: [] }],
      isLoading: false,
      error: null,
    })
    renderPage()
    await userEvent.click(screen.getByText('Add Server'))
    expect(screen.getByLabelText('Command')).toBeInTheDocument()
    expect(screen.getByLabelText('Arguments (space separated)')).toBeInTheDocument()
    expect(screen.queryByLabelText('URL')).not.toBeInTheDocument()
  })

  it('shows http fields when server type changed to http', async () => {
    mockUseMCPServers.mockReturnValue({
      data: [{ id: 's1', name: 'fs', server_type: 'stdio', command: 'cmd', is_active: true, args: [], env: {}, tools: [] }],
      isLoading: false,
      error: null,
    })
    renderPage()
    await userEvent.click(screen.getByText('Add Server'))
    await userEvent.selectOptions(screen.getByLabelText('Server Type'), 'http')
    expect(screen.getByLabelText('URL')).toBeInTheDocument()
    expect(screen.queryByLabelText('Command')).not.toBeInTheDocument()
    expect(screen.queryByLabelText('Arguments (space separated)')).not.toBeInTheDocument()
  })

  it('submits create form and calls mutateAsync', async () => {
    const mockCreate = vi.fn().mockResolvedValue({})
    mockUseCreateMCPServer.mockReturnValue({ mutateAsync: mockCreate, isPending: false })
    mockUseMCPServers.mockReturnValue({
      data: [{ id: 's1', name: 'fs', server_type: 'stdio', command: 'cmd', is_active: true, args: [], env: {}, tools: [] }],
      isLoading: false,
      error: null,
    })
    renderPage()
    await userEvent.click(screen.getByText('Add Server'))
    await userEvent.type(screen.getByLabelText('Name'), 'my-server')
    await userEvent.type(screen.getByLabelText('Command'), 'npx my-server')
    await userEvent.type(screen.getByLabelText('Arguments (space separated)'), '/workspace')
    const addButtons = screen.getAllByRole('button', { name: 'Add Server' })
    await userEvent.click(addButtons[addButtons.length - 1])
    await waitFor(() => {
      expect(mockCreate).toHaveBeenCalledWith(
        expect.objectContaining({ name: 'my-server', server_type: 'stdio', command: 'npx my-server', args: ['/workspace'] })
      )
    })
  })

  it('closes form on cancel', async () => {
    mockUseMCPServers.mockReturnValue({
      data: [{ id: 's1', name: 'fs', server_type: 'stdio', command: 'cmd', is_active: true, args: [], env: {}, tools: [] }],
      isLoading: false,
      error: null,
    })
    renderPage()
    await userEvent.click(screen.getByText('Add Server'))
    expect(screen.getByText('Add MCP Server')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Cancel' }))
    expect(screen.queryByText('Add MCP Server')).not.toBeInTheDocument()
  })

  it('opens edit form with pre-filled data when Edit is clicked', async () => {
    mockUseMCPServers.mockReturnValue({
      data: [{ id: 's1', name: 'filesystem', server_type: 'stdio', command: 'npx server-fs', is_active: true, args: ['/workspace'], env: { KEY: 'val' }, tools: [] }],
      isLoading: false,
      error: null,
    })
    renderPage()
    await userEvent.click(screen.getByText('Edit'))
    expect(screen.getByText('Edit MCP Server')).toBeInTheDocument()
    expect(screen.getByLabelText('Name')).toHaveValue('filesystem')
    expect(screen.getByLabelText('Command')).toHaveValue('npx server-fs')
    expect(screen.getByLabelText('Arguments (space separated)')).toHaveValue('/workspace')
    expect(screen.getByRole('button', { name: 'Update Server' })).toBeInTheDocument()
  })

  it('submits edit form and calls updateServer mutateAsync', async () => {
    const mockUpdate = vi.fn().mockResolvedValue({})
    mockUseUpdateMCPServer.mockReturnValue({ mutateAsync: mockUpdate, isPending: false })
    mockUseMCPServers.mockReturnValue({
      data: [{ id: 's1', name: 'filesystem', server_type: 'stdio', command: 'npx server-fs', is_active: true, args: [], env: {}, tools: [] }],
      isLoading: false,
      error: null,
    })
    renderPage()
    await userEvent.click(screen.getByText('Edit'))
    await userEvent.clear(screen.getByLabelText('Name'))
    await userEvent.type(screen.getByLabelText('Name'), 'updated-server')
    await userEvent.click(screen.getByRole('button', { name: 'Update Server' }))
    await waitFor(() => {
      expect(mockUpdate).toHaveBeenCalledWith(
        expect.objectContaining({ id: 's1', data: expect.objectContaining({ name: 'updated-server' }) })
      )
    })
  })

  it('shows delete confirmation dialog when Delete is clicked', async () => {
    mockUseMCPServers.mockReturnValue({
      data: [{ id: 's1', name: 'filesystem', server_type: 'stdio', command: 'npx server', is_active: true, args: [], env: {}, tools: [] }],
      isLoading: false,
      error: null,
    })
    renderPage()
    await userEvent.click(screen.getByText('Delete'))
    expect(screen.getByText('Are you sure you want to delete this MCP server? This action cannot be undone.')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Delete Server' })).toBeInTheDocument()
  })

  it('calls deleteServer mutateAsync on confirm delete', async () => {
    const mockDelete = vi.fn().mockResolvedValue({})
    mockUseDeleteMCPServer.mockReturnValue({ mutateAsync: mockDelete, isPending: false })
    mockUseMCPServers.mockReturnValue({
      data: [{ id: 's1', name: 'filesystem', server_type: 'stdio', command: 'npx server', is_active: true, args: [], env: {}, tools: [] }],
      isLoading: false,
      error: null,
    })
    renderPage()
    await userEvent.click(screen.getByText('Delete'))
    await userEvent.click(screen.getByRole('button', { name: 'Delete Server' }))
    await waitFor(() => {
      expect(mockDelete).toHaveBeenCalledWith('s1')
    })
  })

  it('cancels delete confirmation dialog', async () => {
    mockUseMCPServers.mockReturnValue({
      data: [{ id: 's1', name: 'filesystem', server_type: 'stdio', command: 'npx server', is_active: true, args: [], env: {}, tools: [] }],
      isLoading: false,
      error: null,
    })
    renderPage()
    await userEvent.click(screen.getByText('Delete'))
    expect(screen.getByText('Are you sure you want to delete this MCP server? This action cannot be undone.')).toBeInTheDocument()
    const cancelButtons = screen.getAllByText('Cancel')
    await userEvent.click(cancelButtons[cancelButtons.length - 1])
    expect(screen.queryByText('Are you sure you want to delete this MCP server? This action cannot be undone.')).not.toBeInTheDocument()
  })

  it('calls testServer mutateAsync when Test button is clicked', async () => {
    const mockTest = vi.fn().mockResolvedValue({ status: 'ok', message: 'Connected' })
    mockUseTestMCPServer.mockReturnValue({ mutateAsync: mockTest, isPending: false })
    mockUseMCPServers.mockReturnValue({
      data: [{ id: 's1', name: 'filesystem', server_type: 'stdio', command: 'npx server', is_active: true, args: [], env: {}, tools: [] }],
      isLoading: false,
      error: null,
    })
    renderPage()
    await userEvent.click(screen.getByText('Test'))
    await waitFor(() => {
      expect(mockTest).toHaveBeenCalledWith('s1')
    })
  })

  it('toggles active status when Active/Inactive button is clicked', async () => {
    const mockUpdate = vi.fn().mockResolvedValue({})
    mockUseUpdateMCPServer.mockReturnValue({ mutateAsync: mockUpdate, isPending: false })
    mockUseMCPServers.mockReturnValue({
      data: [{ id: 's1', name: 'filesystem', server_type: 'stdio', command: 'npx server', is_active: true, args: [], env: {}, tools: [] }],
      isLoading: false,
      error: null,
    })
    renderPage()
    await userEvent.click(screen.getByText('Active'))
    await waitFor(() => {
      expect(mockUpdate).toHaveBeenCalledWith({ id: 's1', data: { is_active: false } })
    })
  })

  it('displays server command, args, and tools', () => {
    mockUseMCPServers.mockReturnValue({
      data: [{
        id: 's1', name: 'filesystem', server_type: 'stdio', command: 'npx server-fs',
        is_active: true, args: ['/workspace', '/tmp'], env: {}, tools: ['read_file', 'write_file'],
      }],
      isLoading: false,
      error: null,
    })
    renderPage()
    expect(screen.getByText('npx server-fs')).toBeInTheDocument()
    expect(screen.getByText('/workspace /tmp')).toBeInTheDocument()
    expect(screen.getByText('read_file')).toBeInTheDocument()
    expect(screen.getByText('write_file')).toBeInTheDocument()
  })

  it('displays URL for http server type', () => {
    mockUseMCPServers.mockReturnValue({
      data: [{ id: 's2', name: 'github', server_type: 'http', command: null, url: 'http://localhost:3001', is_active: false, args: [], env: {}, tools: [] }],
      isLoading: false,
      error: null,
    })
    renderPage()
    expect(screen.getByText('http://localhost:3001')).toBeInTheDocument()
    expect(screen.getByText('http')).toBeInTheDocument()
  })

  it('shows Preview Config panel when clicked', async () => {
    const mockRefetch = vi.fn()
    mockUseGatewayConfigPreview.mockReturnValue({
      data: { active_servers: 2, config_yaml: 'servers:\n  - name: fs' },
      refetch: mockRefetch,
      isFetching: false,
    })
    mockUseMCPServers.mockReturnValue({
      data: [{ id: 's1', name: 'filesystem', server_type: 'stdio', command: 'npx server', is_active: true, args: [], env: {}, tools: [] }],
      isLoading: false,
      error: null,
    })
    renderPage()
    await userEvent.click(screen.getByText('Preview Config'))
    expect(mockRefetch).toHaveBeenCalled()
    expect(screen.getByText('Agent Gateway Config Preview')).toBeInTheDocument()
    expect(screen.getByText('2 active server(s) will be deployed')).toBeInTheDocument()
    expect(screen.getByText(/servers:/)).toBeInTheDocument()
  })

  it('hides Preview Config panel when clicked again', async () => {
    mockUseGatewayConfigPreview.mockReturnValue({
      data: { active_servers: 1, config_yaml: 'yaml: content' },
      refetch: vi.fn(),
      isFetching: false,
    })
    mockUseMCPServers.mockReturnValue({
      data: [{ id: 's1', name: 'filesystem', server_type: 'stdio', command: 'npx server', is_active: true, args: [], env: {}, tools: [] }],
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
    mockUseMCPServers.mockReturnValue({
      data: [{ id: 's1', name: 'filesystem', server_type: 'stdio', command: 'npx server', is_active: true, args: [], env: {}, tools: [] }],
      isLoading: false,
      error: null,
    })
    renderPage()
    await userEvent.click(screen.getByText('Preview Config'))
    expect(screen.getByText('Loading preview...')).toBeInTheDocument()
  })

  it('shows no preview available when preview data is null', async () => {
    mockUseGatewayConfigPreview.mockReturnValue({ data: null, refetch: vi.fn(), isFetching: false })
    mockUseMCPServers.mockReturnValue({
      data: [{ id: 's1', name: 'filesystem', server_type: 'stdio', command: 'npx server', is_active: true, args: [], env: {}, tools: [] }],
      isLoading: false,
      error: null,
    })
    renderPage()
    await userEvent.click(screen.getByText('Preview Config'))
    expect(screen.getByText('No preview available')).toBeInTheDocument()
  })

  it('opens deploy confirmation dialog', async () => {
    mockUseMCPServers.mockReturnValue({
      data: [{ id: 's1', name: 'filesystem', server_type: 'stdio', command: 'npx server', is_active: true, args: [], env: {}, tools: [] }],
      isLoading: false,
      error: null,
    })
    renderPage()
    await userEvent.click(screen.getByRole('button', { name: /Deploy to Gateway/ }))
    expect(screen.getByText(/This will push/)).toBeInTheDocument()
    expect(screen.getByText(/1 active server\(s\)/)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Deploy' })).toBeInTheDocument()
  })

  it('calls syncToGateway on deploy confirm', async () => {
    const mockSync = vi.fn().mockResolvedValue({ status: 'ok', servers_synced: 1 })
    mockUseSyncMCPToGateway.mockReturnValue({ mutateAsync: mockSync, isPending: false })
    mockUseMCPServers.mockReturnValue({
      data: [{ id: 's1', name: 'filesystem', server_type: 'stdio', command: 'npx server', is_active: true, args: [], env: {}, tools: [] }],
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
    mockUseMCPServers.mockReturnValue({
      data: [{ id: 's1', name: 'filesystem', server_type: 'stdio', command: 'npx server', is_active: true, args: [], env: {}, tools: [] }],
      isLoading: false,
      error: null,
    })
    renderPage()
    await userEvent.click(screen.getByRole('button', { name: /Deploy to Gateway/ }))
    expect(screen.getByText(/This will push/)).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Cancel' }))
    expect(screen.queryByText(/This will push/)).not.toBeInTheDocument()
  })

  it('shows active count badge on Deploy button', () => {
    mockUseMCPServers.mockReturnValue({
      data: [
        { id: 's1', name: 'fs', server_type: 'stdio', command: 'cmd', is_active: true, args: [], env: {}, tools: [] },
        { id: 's2', name: 'gh', server_type: 'http', url: 'http://x', is_active: true, args: [], env: {}, tools: [] },
        { id: 's3', name: 'off', server_type: 'stdio', command: 'cmd2', is_active: false, args: [], env: {}, tools: [] },
      ],
      isLoading: false,
      error: null,
    })
    renderPage()
    expect(screen.getByText('2')).toBeInTheDocument()
  })

  it('disables Deploy to Gateway button when no active servers', () => {
    mockUseMCPServers.mockReturnValue({
      data: [{ id: 's1', name: 'fs', server_type: 'stdio', command: 'cmd', is_active: false, args: [], env: {}, tools: [] }],
      isLoading: false,
      error: null,
    })
    renderPage()
    const deployBtn = screen.getByRole('button', { name: /Deploy to Gateway/ })
    expect(deployBtn).toBeDisabled()
  })

  it('submits create form with env JSON', async () => {
    const mockCreate = vi.fn().mockResolvedValue({})
    mockUseCreateMCPServer.mockReturnValue({ mutateAsync: mockCreate, isPending: false })
    mockUseMCPServers.mockReturnValue({
      data: [{ id: 's1', name: 'fs', server_type: 'stdio', command: 'cmd', is_active: true, args: [], env: {}, tools: [] }],
      isLoading: false,
      error: null,
    })
    renderPage()
    await userEvent.click(screen.getByText('Add Server'))
    await userEvent.type(screen.getByLabelText('Name'), 'env-server')
    await userEvent.type(screen.getByLabelText('Command'), 'npx server')
    // userEvent.type treats { specially, so use paste for JSON
    const envInput = screen.getByLabelText('Environment Variables (JSON)')
    await userEvent.clear(envInput)
    await userEvent.click(envInput)
    await userEvent.paste('{"API_KEY": "secret"}')
    const addButtons = screen.getAllByRole('button', { name: 'Add Server' })
    await userEvent.click(addButtons[addButtons.length - 1])
    await waitFor(() => {
      expect(mockCreate).toHaveBeenCalledWith(
        expect.objectContaining({ env: { API_KEY: 'secret' } })
      )
    })
  })
})
