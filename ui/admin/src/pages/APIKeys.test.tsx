import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import APIKeys from './APIKeys'

const mockUseAPIKeys = vi.fn()
const mockUseGenerateKey = vi.fn()
const mockUseDeleteKey = vi.fn()

vi.mock('../api/hooks', () => ({
  useAPIKeys: () => mockUseAPIKeys(),
  useGenerateKey: () => mockUseGenerateKey(),
  useDeleteKey: () => mockUseDeleteKey(),
}))

vi.mock('../components/Toast', () => ({
  useToast: () => vi.fn(),
}))

function renderPage() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter>
        <APIKeys />
      </MemoryRouter>
    </QueryClientProvider>
  )
}

describe('APIKeys', () => {
  beforeEach(() => {
    mockUseGenerateKey.mockReturnValue({ mutateAsync: vi.fn(), isPending: false })
    mockUseDeleteKey.mockReturnValue({ mutateAsync: vi.fn(), isPending: false })
  })

  it('shows loading state', () => {
    mockUseAPIKeys.mockReturnValue({ data: undefined, isLoading: true, error: null })
    renderPage()
    expect(screen.getByText('API Keys')).toBeInTheDocument()
    expect(screen.getByText('Manage API keys for LLM access')).toBeInTheDocument()
  })

  it('shows error state', () => {
    mockUseAPIKeys.mockReturnValue({ data: undefined, isLoading: false, error: new Error('fail') })
    renderPage()
    expect(screen.getByText('Failed to load API keys')).toBeInTheDocument()
  })

  it('shows Generate Key button', () => {
    mockUseAPIKeys.mockReturnValue({
      data: [{ token: 'test-token-placeholder-1', key_alias: 'test-key', spend: 1.5, max_budget: 100 }],
      isLoading: false,
      error: null,
    })
    renderPage()
    expect(screen.getByText('Generate Key')).toBeInTheDocument()
  })

  it('shows key list with data', () => {
    mockUseAPIKeys.mockReturnValue({
      data: [
        { token: 'test-token-placeholder-1', key_alias: 'my-app-key', spend: 5.1234, max_budget: 100, models: [], team_id: null, expires: null },
        { token: 'test-token-placeholder-2', key_alias: 'test-key', spend: 0, max_budget: null, models: ['gpt-4o'], team_id: null, expires: null },
      ],
      isLoading: false,
      error: null,
    })
    renderPage()
    expect(screen.getByText('my-app-key')).toBeInTheDocument()
    expect(screen.getByText('test-key')).toBeInTheDocument()
    expect(screen.getByText('2 keys active')).toBeInTheDocument()
  })

  it('shows empty state when no keys', () => {
    mockUseAPIKeys.mockReturnValue({ data: [], isLoading: false, error: null })
    renderPage()
    expect(screen.getByText('No API keys')).toBeInTheDocument()
    expect(screen.getByText('Generate API keys to authenticate LLM requests through the gateway.')).toBeInTheDocument()
  })

  it('opens Generate Key form when button clicked', async () => {
    mockUseAPIKeys.mockReturnValue({
      data: [{ token: 'test-token-placeholder-1', key_alias: 'test-key', spend: 1.5, max_budget: 100 }],
      isLoading: false,
      error: null,
    })
    renderPage()
    await userEvent.click(screen.getByText('Generate Key'))
    expect(screen.getByText('Generate API Key')).toBeInTheDocument()
  })

  it('form shows key_alias and max_budget fields', async () => {
    mockUseAPIKeys.mockReturnValue({
      data: [{ token: 'test-token-placeholder-1', key_alias: 'test-key', spend: 1.5, max_budget: 100 }],
      isLoading: false,
      error: null,
    })
    renderPage()
    await userEvent.click(screen.getByText('Generate Key'))
    expect(screen.getByLabelText('Key Alias')).toBeInTheDocument()
    expect(screen.getByLabelText('Max Budget ($)')).toBeInTheDocument()
  })

  it('shows key spend and budget values', () => {
    mockUseAPIKeys.mockReturnValue({
      data: [{ token: 'test-token-placeholder-1', key_alias: 'test-key', spend: 5.1234, max_budget: 100 }],
      isLoading: false,
      error: null,
    })
    renderPage()
    expect(screen.getByText('$5.1234')).toBeInTheDocument()
    expect(screen.getByText('$100.00')).toBeInTheDocument()
  })

  it('shows "1 key active" singular text', () => {
    mockUseAPIKeys.mockReturnValue({
      data: [{ token: 'test-token-placeholder-1', key_alias: 'solo-key', spend: 0, max_budget: null }],
      isLoading: false,
      error: null,
    })
    renderPage()
    expect(screen.getByText('1 key active')).toBeInTheDocument()
  })

  it('shows masked token format', () => {
    mockUseAPIKeys.mockReturnValue({
      data: [{ token: 'test-token-placeholder-1', key_alias: 'test-key', spend: 0, max_budget: null }],
      isLoading: false,
      error: null,
    })
    renderPage()
    expect(screen.getByText('sk-abc12...6ghi')).toBeInTheDocument()
  })

  it('shows Revoke button on key cards', () => {
    mockUseAPIKeys.mockReturnValue({
      data: [{ token: 'test-token-placeholder-1', key_alias: 'test-key', spend: 0, max_budget: null }],
      isLoading: false,
      error: null,
    })
    renderPage()
    expect(screen.getByText('Revoke')).toBeInTheDocument()
  })
})
