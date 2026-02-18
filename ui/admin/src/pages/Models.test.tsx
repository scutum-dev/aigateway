import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import Models from './Models'

const mockUseModels = vi.fn()
const mockUseCreateModel = vi.fn()
const mockUseDeleteModel = vi.fn()

vi.mock('../api/hooks', () => ({
  useModels: () => mockUseModels(),
  useCreateModel: () => mockUseCreateModel(),
  useDeleteModel: () => mockUseDeleteModel(),
}))

vi.mock('../components/Toast', () => ({
  useToast: () => vi.fn(),
}))

function renderPage() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter>
        <Models />
      </MemoryRouter>
    </QueryClientProvider>
  )
}

describe('Models', () => {
  beforeEach(() => {
    mockUseCreateModel.mockReturnValue({ mutateAsync: vi.fn(), isPending: false })
    mockUseDeleteModel.mockReturnValue({ mutateAsync: vi.fn(), isPending: false })
  })

  it('shows loading state', () => {
    mockUseModels.mockReturnValue({ data: undefined, isLoading: true, error: null })
    renderPage()
    expect(screen.getByText('Models')).toBeInTheDocument()
    expect(screen.getByText('Manage LLM model configurations')).toBeInTheDocument()
  })

  it('shows error state', () => {
    mockUseModels.mockReturnValue({ data: undefined, isLoading: false, error: new Error('fail') })
    renderPage()
    expect(screen.getByText('Failed to load models')).toBeInTheDocument()
  })

  it('shows Add Model button when data loaded', () => {
    mockUseModels.mockReturnValue({
      data: { data: [{ model_name: 'gpt-4o', litellm_params: { model: 'openai/gpt-4o' }, model_info: { id: '1', mode: 'chat' } }] },
      isLoading: false,
      error: null,
    })
    renderPage()
    expect(screen.getByText('Add Model')).toBeInTheDocument()
  })

  it('shows model list when data loaded', () => {
    mockUseModels.mockReturnValue({
      data: {
        data: [
          { model_name: 'gpt-4o', litellm_params: { model: 'openai/gpt-4o' }, model_info: { id: '1', mode: 'chat' } },
          { model_name: 'claude-3.5-sonnet', litellm_params: { model: 'anthropic/claude-3.5-sonnet' }, model_info: { id: '2', mode: 'chat' } },
        ],
      },
      isLoading: false,
      error: null,
    })
    renderPage()
    expect(screen.getByText('gpt-4o')).toBeInTheDocument()
    expect(screen.getByText('claude-3.5-sonnet')).toBeInTheDocument()
    expect(screen.getByText('2 models configured')).toBeInTheDocument()
  })

  it('shows empty state when no models', () => {
    mockUseModels.mockReturnValue({ data: { data: [] }, isLoading: false, error: null })
    renderPage()
    expect(screen.getByText('No models configured')).toBeInTheDocument()
    expect(screen.getByText('Add models to route LLM requests through the gateway.')).toBeInTheDocument()
  })

  it('opens Add Model form when button clicked', async () => {
    mockUseModels.mockReturnValue({
      data: { data: [{ model_name: 'gpt-4o', litellm_params: { model: 'openai/gpt-4o' }, model_info: { id: '1', mode: 'chat' } }] },
      isLoading: false,
      error: null,
    })
    renderPage()
    await userEvent.click(screen.getByText('Add Model'))
    expect(screen.getByLabelText('Model Name (alias)')).toBeInTheDocument()
  })

  it('form shows model_name, model, custom_llm_provider fields', async () => {
    mockUseModels.mockReturnValue({
      data: { data: [{ model_name: 'gpt-4o', litellm_params: { model: 'openai/gpt-4o' }, model_info: { id: '1', mode: 'chat' } }] },
      isLoading: false,
      error: null,
    })
    renderPage()
    await userEvent.click(screen.getByText('Add Model'))
    expect(screen.getByLabelText('Model Name (alias)')).toBeInTheDocument()
    expect(screen.getByLabelText('Provider Model ID')).toBeInTheDocument()
    expect(screen.getByLabelText('Custom Provider (optional)')).toBeInTheDocument()
  })

  it('shows "No models match your search" for empty filter result', async () => {
    mockUseModels.mockReturnValue({
      data: { data: [{ model_name: 'gpt-4o', litellm_params: { model: 'openai/gpt-4o' }, model_info: { id: '1', mode: 'chat' } }] },
      isLoading: false,
      error: null,
    })
    renderPage()
    const searchInput = screen.getByPlaceholderText('Search models...')
    await userEvent.type(searchInput, 'zzzznonexistent')
    expect(screen.getByText('No models match your search')).toBeInTheDocument()
  })

  it('shows provider badges extracted from model path', () => {
    mockUseModels.mockReturnValue({
      data: { data: [{ model_name: 'gpt-4o', litellm_params: { model: 'openai/gpt-4o' }, model_info: { id: '1', mode: 'chat' } }] },
      isLoading: false,
      error: null,
    })
    renderPage()
    const matches = screen.getAllByText('openai')
    expect(matches.length).toBeGreaterThanOrEqual(1)
  })

  it('shows "1 model configured" singular text', () => {
    mockUseModels.mockReturnValue({
      data: { data: [{ model_name: 'gpt-4o', litellm_params: { model: 'openai/gpt-4o' }, model_info: { id: '1', mode: 'chat' } }] },
      isLoading: false,
      error: null,
    })
    renderPage()
    expect(screen.getByText('1 model configured')).toBeInTheDocument()
  })

  it('renders search input with placeholder text', () => {
    mockUseModels.mockReturnValue({
      data: { data: [{ model_name: 'gpt-4o', litellm_params: { model: 'openai/gpt-4o' }, model_info: { id: '1', mode: 'chat' } }] },
      isLoading: false,
      error: null,
    })
    renderPage()
    expect(screen.getByPlaceholderText('Search models...')).toBeInTheDocument()
  })
})
