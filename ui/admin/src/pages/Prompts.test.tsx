import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { describe, it, expect, vi, beforeEach } from 'vitest'

const mockUsePromptTemplates = vi.fn()
const mockUseCreatePromptTemplate = vi.fn()
const mockUseDeletePromptTemplate = vi.fn()
const mockUsePromptApprovals = vi.fn()

vi.mock('../api/hooks', () => ({
  usePromptTemplates: (p?: unknown) => mockUsePromptTemplates(p),
  useCreatePromptTemplate: () => mockUseCreatePromptTemplate(),
  useDeletePromptTemplate: () => mockUseDeletePromptTemplate(),
  usePromptApprovals: () => mockUsePromptApprovals(),
}))

vi.mock('../api/client', () => ({
  promptsApi: {
    submitReview: vi.fn(),
    getVersions: vi.fn(),
    render: vi.fn(),
    approve: vi.fn(),
    reject: vi.fn(),
  },
}))

vi.mock('../components/Toast', () => ({
  useToast: () => vi.fn(),
}))

import Prompts from './Prompts'

function renderPage() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter>
        <Prompts />
      </MemoryRouter>
    </QueryClientProvider>
  )
}

describe('Prompts', () => {
  beforeEach(() => {
    mockUseCreatePromptTemplate.mockReturnValue({ mutateAsync: vi.fn(), isPending: false })
    mockUseDeletePromptTemplate.mockReturnValue({ mutateAsync: vi.fn() })
    mockUsePromptApprovals.mockReturnValue({ data: [] })
  })

  it('renders loading state', () => {
    mockUsePromptTemplates.mockReturnValue({ data: undefined, isLoading: true, error: null })
    renderPage()
    expect(screen.getByText('Prompt Registry')).toBeInTheDocument()
    expect(screen.getByText('Manage versioned prompt templates')).toBeInTheDocument()
  })

  it('renders error state', () => {
    mockUsePromptTemplates.mockReturnValue({ data: undefined, isLoading: false, error: new Error('fail') })
    renderPage()
    expect(screen.getByText('Failed to load prompt templates')).toBeInTheDocument()
  })

  it('renders empty state when no templates', () => {
    mockUsePromptTemplates.mockReturnValue({ data: [], isLoading: false, error: null })
    renderPage()
    expect(screen.getByText('No prompt templates found')).toBeInTheDocument()
  })

  it('renders template list with data', () => {
    mockUsePromptTemplates.mockReturnValue({
      data: [
        {
          id: '1',
          name: 'Code Review',
          slug: 'code-review',
          category: 'coding',
          status: 'approved',
          version: 2,
          tags: ['dev', 'review'],
          description: 'Review code changes',
          template_text: 'Review this {{code}}',
          variables: [{ name: 'code' }],
          is_current: true,
          created_at: '2025-01-01T00:00:00Z',
        },
      ],
      isLoading: false,
      error: null,
    })
    renderPage()
    expect(screen.getByText('1 template')).toBeInTheDocument()
    expect(screen.getByText('Code Review')).toBeInTheDocument()
    expect(screen.getByText('code-review')).toBeInTheDocument()
    expect(screen.getByText('approved')).toBeInTheDocument()
  })

  it('opens create modal when New Template button is clicked', async () => {
    mockUsePromptTemplates.mockReturnValue({ data: [], isLoading: false, error: null })
    renderPage()
    await userEvent.click(screen.getByText('New Template'))
    expect(screen.getByText('Create Prompt Template')).toBeInTheDocument()
  })

  it('shows version link per template', () => {
    mockUsePromptTemplates.mockReturnValue({
      data: [
        {
          id: '1',
          name: 'Code Review',
          slug: 'code-review',
          category: 'coding',
          status: 'approved',
          version: 2,
          tags: [],
          description: 'Review code changes',
          template_text: 'Review this {{code}}',
          variables: [{ name: 'code' }],
          is_current: true,
          created_at: '2025-01-01T00:00:00Z',
        },
      ],
      isLoading: false,
      error: null,
    })
    renderPage()
    expect(screen.getByText('v2')).toBeInTheDocument()
  })

  it('shows category in template table', () => {
    mockUsePromptTemplates.mockReturnValue({
      data: [
        {
          id: '1',
          name: 'Code Review',
          slug: 'code-review',
          category: 'coding',
          status: 'approved',
          version: 1,
          tags: [],
          template_text: 'Review this',
          variables: [],
          is_current: true,
          created_at: '2025-01-01T00:00:00Z',
        },
      ],
      isLoading: false,
      error: null,
    })
    renderPage()
    expect(screen.getByText('coding')).toBeInTheDocument()
  })

  it('shows tag chips in template table', () => {
    mockUsePromptTemplates.mockReturnValue({
      data: [
        {
          id: '1',
          name: 'Code Review',
          slug: 'code-review',
          category: 'coding',
          status: 'approved',
          version: 1,
          tags: ['dev', 'review', 'quality'],
          template_text: 'Review this',
          variables: [],
          is_current: true,
          created_at: '2025-01-01T00:00:00Z',
        },
      ],
      isLoading: false,
      error: null,
    })
    renderPage()
    expect(screen.getByText('dev')).toBeInTheDocument()
    expect(screen.getByText('review')).toBeInTheDocument()
    expect(screen.getByText('quality')).toBeInTheDocument()
  })

  it('shows template description in table', () => {
    mockUsePromptTemplates.mockReturnValue({
      data: [
        {
          id: '1',
          name: 'Code Review',
          slug: 'code-review',
          category: 'coding',
          status: 'draft',
          version: 1,
          tags: [],
          description: 'Review code changes',
          template_text: 'Review this',
          variables: [],
          is_current: true,
          created_at: '2025-01-01T00:00:00Z',
        },
      ],
      isLoading: false,
      error: null,
    })
    renderPage()
    expect(screen.getByText('Review code changes')).toBeInTheDocument()
  })
})
