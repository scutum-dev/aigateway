import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { describe, it, expect, vi, beforeEach } from 'vitest'

const mockGet = vi.fn()
const mockPost = vi.fn()
const mockPut = vi.fn()
const mockDelete = vi.fn()

vi.mock('../../api/client', () => ({
  default: {
    get: (...args: any[]) => mockGet(...args),
    post: (...args: any[]) => mockPost(...args),
    put: (...args: any[]) => mockPut(...args),
    delete: (...args: any[]) => mockDelete(...args),
  },
}))

vi.mock('../Toast', () => ({
  useToast: () => vi.fn(),
}))

vi.mock('../ConfirmDialog', () => ({
  default: ({ isOpen, title, message }: any) =>
    isOpen ? <div data-testid="confirm-dialog">{title}: {message}</div> : null,
}))

import { PolicyEditor } from './PolicyEditor'

const samplePolicies = [
  {
    id: 'p1',
    name: 'Budget Guard',
    description: 'Deny when budget low',
    priority: 80,
    condition: { type: 'and', children: [] },
    action: 'deny',
    targetModels: ['gpt-4o'],
    isActive: true,
  },
  {
    id: 'p2',
    name: 'Latency Route',
    description: 'Permit low-latency models',
    priority: 50,
    condition: { type: 'and', children: [] },
    action: 'permit',
    targetModels: [],
    isActive: false,
  },
]

const sampleModels = [
  { model_id: 'gpt-4o', provider: 'openai', tier: 'tier-1' },
  { model_id: 'claude-sonnet-4', provider: 'anthropic', tier: 'tier-1' },
]

function renderComponent() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter>
        <PolicyEditor />
      </MemoryRouter>
    </QueryClientProvider>
  )
}

describe('PolicyEditor', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockGet.mockImplementation((url: string) => {
      if (url.includes('routing-policies')) {
        return Promise.resolve({ data: samplePolicies })
      }
      if (url.includes('models')) {
        return Promise.resolve({ data: sampleModels })
      }
      return Promise.resolve({ data: [] })
    })
    mockPost.mockResolvedValue({ data: { id: 'new-1' } })
    mockPut.mockResolvedValue({ data: {} })
    mockDelete.mockResolvedValue({ data: {} })
  })

  it('shows loading text when data is being fetched', () => {
    mockGet.mockReturnValue(new Promise(() => {})) // never resolves
    renderComponent()
    expect(screen.getByText('Loading policies...')).toBeInTheDocument()
  })

  it('shows sidebar heading Routing Policies', async () => {
    renderComponent()
    await waitFor(() => {
      expect(screen.getByText('Routing Policies')).toBeInTheDocument()
    })
  })

  it('shows + New button', async () => {
    renderComponent()
    await waitFor(() => {
      expect(screen.getByText('+ New')).toBeInTheDocument()
    })
  })

  it('shows empty state when no policy is selected', async () => {
    renderComponent()
    await waitFor(() => {
      expect(screen.getByText('Select a policy to edit')).toBeInTheDocument()
      expect(screen.getByText('or create a new one')).toBeInTheDocument()
    })
  })

  it('shows create form when New button is clicked', async () => {
    renderComponent()
    await waitFor(() => {
      expect(screen.getByText('+ New')).toBeInTheDocument()
    })
    await userEvent.click(screen.getByText('+ New'))
    expect(screen.getByText('Create Policy')).toBeInTheDocument()
  })

  it('shows form fields when editing', async () => {
    renderComponent()
    await waitFor(() => {
      expect(screen.getByText('+ New')).toBeInTheDocument()
    })
    await userEvent.click(screen.getByText('+ New'))
    expect(screen.getByText('Policy Name')).toBeInTheDocument()
    expect(screen.getByText('Priority (0-100)')).toBeInTheDocument()
    expect(screen.getByText('Description')).toBeInTheDocument()
    expect(screen.getByText('Action')).toBeInTheDocument()
    expect(screen.getByText('Status')).toBeInTheDocument()
  })

  it('shows policy list items when data is loaded', async () => {
    renderComponent()
    await waitFor(() => {
      expect(screen.getByText('Budget Guard')).toBeInTheDocument()
      expect(screen.getByText('Latency Route')).toBeInTheDocument()
    })
  })

  it('shows edit form when a policy is clicked', async () => {
    renderComponent()
    await waitFor(() => {
      expect(screen.getByText('Budget Guard')).toBeInTheDocument()
    })
    await userEvent.click(screen.getByText('Budget Guard'))
    expect(screen.getByText('Edit Policy')).toBeInTheDocument()
  })

  it('shows Delete button in edit mode', async () => {
    renderComponent()
    await waitFor(() => {
      expect(screen.getByText('Budget Guard')).toBeInTheDocument()
    })
    await userEvent.click(screen.getByText('Budget Guard'))
    expect(screen.getByText('Delete')).toBeInTheDocument()
  })

  it('shows Cancel button in form', async () => {
    renderComponent()
    await waitFor(() => {
      expect(screen.getByText('Budget Guard')).toBeInTheDocument()
    })
    await userEvent.click(screen.getByText('Budget Guard'))
    expect(screen.getByText('Cancel')).toBeInTheDocument()
  })

  it('clears selection when Cancel is clicked', async () => {
    renderComponent()
    await waitFor(() => {
      expect(screen.getByText('Budget Guard')).toBeInTheDocument()
    })
    await userEvent.click(screen.getByText('Budget Guard'))
    expect(screen.getByText('Edit Policy')).toBeInTheDocument()
    await userEvent.click(screen.getByText('Cancel'))
    expect(screen.getByText('Select a policy to edit')).toBeInTheDocument()
  })

  it('shows Save Policy button in form', async () => {
    renderComponent()
    await waitFor(() => {
      expect(screen.getByText('+ New')).toBeInTheDocument()
    })
    await userEvent.click(screen.getByText('+ New'))
    expect(screen.getByText('Save Policy')).toBeInTheDocument()
  })

  it('shows Generated Cedar Policy section', async () => {
    renderComponent()
    await waitFor(() => {
      expect(screen.getByText('Budget Guard')).toBeInTheDocument()
    })
    await userEvent.click(screen.getByText('Budget Guard'))
    expect(screen.getByText('Generated Cedar Policy')).toBeInTheDocument()
    expect(screen.getByText('Cedar Policy Preview')).toBeInTheDocument()
  })

  it('shows Target Models section', async () => {
    renderComponent()
    await waitFor(() => {
      expect(screen.getByText('Budget Guard')).toBeInTheDocument()
    })
    await userEvent.click(screen.getByText('Budget Guard'))
    expect(screen.getByText('Target Models')).toBeInTheDocument()
    expect(screen.getByText(/Select which models this policy applies to/)).toBeInTheDocument()
  })

  it('shows Conditions section', async () => {
    renderComponent()
    await waitFor(() => {
      expect(screen.getByText('Budget Guard')).toBeInTheDocument()
    })
    await userEvent.click(screen.getByText('Budget Guard'))
    expect(screen.getByText('Conditions')).toBeInTheDocument()
    expect(screen.getByText(/Define when this policy should be applied/)).toBeInTheDocument()
  })
})
