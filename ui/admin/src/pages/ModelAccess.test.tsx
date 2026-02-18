import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { describe, it, expect, vi, beforeEach } from 'vitest'

const mockUseModelAccessTiers = vi.fn()
const mockUseCreateModelAccessTier = vi.fn()
const mockUseModelAccessRequests = vi.fn()
const mockUseCreateModelAccessRequest = vi.fn()
const mockUseMyModelAccess = vi.fn()

vi.mock('../api/hooks', () => ({
  useModelAccessTiers: () => mockUseModelAccessTiers(),
  useCreateModelAccessTier: () => mockUseCreateModelAccessTier(),
  useModelAccessRequests: () => mockUseModelAccessRequests(),
  useCreateModelAccessRequest: () => mockUseCreateModelAccessRequest(),
  useMyModelAccess: () => mockUseMyModelAccess(),
}))

vi.mock('../api/client', () => ({
  modelAccessApi: {
    deleteTier: vi.fn(),
    approveRequest: vi.fn(),
    rejectRequest: vi.fn(),
  },
}))

vi.mock('../components/Toast', () => ({
  useToast: () => vi.fn(),
}))

import ModelAccess from './ModelAccess'

function renderPage() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter>
        <ModelAccess />
      </MemoryRouter>
    </QueryClientProvider>
  )
}

describe('ModelAccess', () => {
  beforeEach(() => {
    mockUseCreateModelAccessTier.mockReturnValue({ mutateAsync: vi.fn(), isPending: false })
    mockUseCreateModelAccessRequest.mockReturnValue({ mutateAsync: vi.fn(), isPending: false })
  })

  it('renders loading state', () => {
    mockUseModelAccessTiers.mockReturnValue({ data: undefined, isLoading: true })
    mockUseModelAccessRequests.mockReturnValue({ data: undefined, isLoading: true })
    mockUseMyModelAccess.mockReturnValue({ data: undefined, isLoading: true })
    renderPage()
    expect(screen.getByText('Model Access')).toBeInTheDocument()
    expect(screen.getByText('Govern model access with tiered permissions')).toBeInTheDocument()
  })

  it('renders tabs for tiers, requests, and my-access', () => {
    mockUseModelAccessTiers.mockReturnValue({ data: [], isLoading: false })
    mockUseModelAccessRequests.mockReturnValue({ data: [], isLoading: false })
    mockUseMyModelAccess.mockReturnValue({ data: [], isLoading: false })
    renderPage()
    expect(screen.getByText('Access Tiers')).toBeInTheDocument()
    expect(screen.getByText('Requests')).toBeInTheDocument()
    expect(screen.getByText('My Access')).toBeInTheDocument()
  })

  it('renders empty tiers tab', () => {
    mockUseModelAccessTiers.mockReturnValue({ data: [], isLoading: false })
    mockUseModelAccessRequests.mockReturnValue({ data: [], isLoading: false })
    mockUseMyModelAccess.mockReturnValue({ data: [], isLoading: false })
    renderPage()
    expect(screen.getByText('No access tiers defined')).toBeInTheDocument()
  })

  it('renders tier data', () => {
    mockUseModelAccessTiers.mockReturnValue({
      data: [
        { id: '1', name: 'standard', description: 'Standard access', requires_approval: false, requires_justification: false, max_grant_duration_days: null, models: ['gpt-4o'] },
      ],
      isLoading: false,
    })
    mockUseModelAccessRequests.mockReturnValue({ data: [], isLoading: false })
    mockUseMyModelAccess.mockReturnValue({ data: [], isLoading: false })
    renderPage()
    expect(screen.getByText('standard')).toBeInTheDocument()
    expect(screen.getByText('Auto-Approve')).toBeInTheDocument()
    expect(screen.getByText('gpt-4o')).toBeInTheDocument()
  })

  it('shows New Tier button on tiers tab', () => {
    mockUseModelAccessTiers.mockReturnValue({ data: [], isLoading: false })
    mockUseModelAccessRequests.mockReturnValue({ data: [], isLoading: false })
    mockUseMyModelAccess.mockReturnValue({ data: [], isLoading: false })
    renderPage()
    expect(screen.getByText('New Tier')).toBeInTheDocument()
  })

  it('renders tier with approval required and justification badges', () => {
    mockUseModelAccessTiers.mockReturnValue({
      data: [
        { id: '1', name: 'premium', description: 'Premium tier', requires_approval: true, requires_justification: true, max_grant_duration_days: 90, models: ['gpt-4o', 'claude-3'] },
      ],
      isLoading: false,
    })
    mockUseModelAccessRequests.mockReturnValue({ data: [], isLoading: false })
    mockUseMyModelAccess.mockReturnValue({ data: [], isLoading: false })
    renderPage()
    expect(screen.getByText('premium')).toBeInTheDocument()
    expect(screen.getByText('Premium tier')).toBeInTheDocument()
    expect(screen.getByText('Approval Required')).toBeInTheDocument()
    expect(screen.getByText('Justification Required')).toBeInTheDocument()
    expect(screen.getByText('Max duration: 90 days')).toBeInTheDocument()
    expect(screen.getByText('gpt-4o')).toBeInTheDocument()
    expect(screen.getByText('claude-3')).toBeInTheDocument()
  })

  it('opens and closes create tier modal', async () => {
    mockUseModelAccessTiers.mockReturnValue({ data: [], isLoading: false })
    mockUseModelAccessRequests.mockReturnValue({ data: [], isLoading: false })
    mockUseMyModelAccess.mockReturnValue({ data: [], isLoading: false })
    renderPage()
    await userEvent.click(screen.getByText('New Tier'))
    expect(screen.getByText('Create Access Tier')).toBeInTheDocument()
    expect(screen.getByPlaceholderText('e.g. standard, premium, experimental')).toBeInTheDocument()
    expect(screen.getByPlaceholderText('Describe this tier')).toBeInTheDocument()
    expect(screen.getByText('Requires Approval')).toBeInTheDocument()
    expect(screen.getByText('Requires Justification')).toBeInTheDocument()
    await userEvent.click(screen.getByText('Cancel'))
    expect(screen.queryByText('Create Access Tier')).not.toBeInTheDocument()
  })

  it('submits create tier form', async () => {
    const mockMutateAsync = vi.fn().mockResolvedValue({})
    mockUseCreateModelAccessTier.mockReturnValue({ mutateAsync: mockMutateAsync, isPending: false })
    mockUseModelAccessTiers.mockReturnValue({ data: [], isLoading: false })
    mockUseModelAccessRequests.mockReturnValue({ data: [], isLoading: false })
    mockUseMyModelAccess.mockReturnValue({ data: [], isLoading: false })
    renderPage()
    await userEvent.click(screen.getByText('New Tier'))
    await userEvent.type(screen.getByPlaceholderText('e.g. standard, premium, experimental'), 'experimental')
    await userEvent.click(screen.getByRole('button', { name: 'Create' }))
    expect(mockMutateAsync).toHaveBeenCalled()
  })

  it('create tier form disables Create button when name is empty', async () => {
    mockUseModelAccessTiers.mockReturnValue({ data: [], isLoading: false })
    mockUseModelAccessRequests.mockReturnValue({ data: [], isLoading: false })
    mockUseMyModelAccess.mockReturnValue({ data: [], isLoading: false })
    renderPage()
    await userEvent.click(screen.getByText('New Tier'))
    const createBtn = screen.getByRole('button', { name: 'Create' })
    expect(createBtn).toBeDisabled()
  })

  it('adds a model to the tier form using Add button', async () => {
    mockUseModelAccessTiers.mockReturnValue({ data: [], isLoading: false })
    mockUseModelAccessRequests.mockReturnValue({ data: [], isLoading: false })
    mockUseMyModelAccess.mockReturnValue({ data: [], isLoading: false })
    renderPage()
    await userEvent.click(screen.getByText('New Tier'))
    await userEvent.type(screen.getByPlaceholderText('Add model name'), 'gpt-4o')
    await userEvent.click(screen.getByRole('button', { name: 'Add' }))
    expect(screen.getByText('gpt-4o')).toBeInTheDocument()
  })

  it('switches to Requests tab and shows empty state', async () => {
    mockUseModelAccessTiers.mockReturnValue({ data: [], isLoading: false })
    mockUseModelAccessRequests.mockReturnValue({ data: [], isLoading: false })
    mockUseMyModelAccess.mockReturnValue({ data: [], isLoading: false })
    renderPage()
    await userEvent.click(screen.getByText('Requests'))
    expect(screen.getByText('No access requests')).toBeInTheDocument()
    expect(screen.getByText('Access requests will appear here.')).toBeInTheDocument()
  })

  it('shows Request Access button on requests tab', async () => {
    mockUseModelAccessTiers.mockReturnValue({ data: [], isLoading: false })
    mockUseModelAccessRequests.mockReturnValue({ data: [], isLoading: false })
    mockUseMyModelAccess.mockReturnValue({ data: [], isLoading: false })
    renderPage()
    await userEvent.click(screen.getByText('Requests'))
    expect(screen.getByText('Request Access')).toBeInTheDocument()
  })

  it('opens and closes create request modal', async () => {
    mockUseModelAccessTiers.mockReturnValue({ data: [], isLoading: false })
    mockUseModelAccessRequests.mockReturnValue({ data: [], isLoading: false })
    mockUseMyModelAccess.mockReturnValue({ data: [], isLoading: false })
    renderPage()
    await userEvent.click(screen.getByText('Requests'))
    await userEvent.click(screen.getByText('Request Access'))
    expect(screen.getByText('Request Model Access')).toBeInTheDocument()
    expect(screen.getByPlaceholderText('gpt-5, claude-sonnet-4.5, etc.')).toBeInTheDocument()
    expect(screen.getByText('Select a tier (optional)')).toBeInTheDocument()
    await userEvent.click(screen.getByText('Cancel'))
    expect(screen.queryByText('Request Model Access')).not.toBeInTheDocument()
  })

  it('submits create access request form', async () => {
    const mockMutateAsync = vi.fn().mockResolvedValue({})
    mockUseCreateModelAccessRequest.mockReturnValue({ mutateAsync: mockMutateAsync, isPending: false })
    mockUseModelAccessTiers.mockReturnValue({ data: [], isLoading: false })
    mockUseModelAccessRequests.mockReturnValue({ data: [], isLoading: false })
    mockUseMyModelAccess.mockReturnValue({ data: [], isLoading: false })
    renderPage()
    await userEvent.click(screen.getByText('Requests'))
    await userEvent.click(screen.getByText('Request Access'))
    await userEvent.type(screen.getByPlaceholderText('gpt-5, claude-sonnet-4.5, etc.'), 'gpt-5')
    await userEvent.click(screen.getByRole('button', { name: 'Submit Request' }))
    expect(mockMutateAsync).toHaveBeenCalled()
  })

  it('create request form disables Submit button when model_pattern is empty', async () => {
    mockUseModelAccessTiers.mockReturnValue({ data: [], isLoading: false })
    mockUseModelAccessRequests.mockReturnValue({ data: [], isLoading: false })
    mockUseMyModelAccess.mockReturnValue({ data: [], isLoading: false })
    renderPage()
    await userEvent.click(screen.getByText('Requests'))
    await userEvent.click(screen.getByText('Request Access'))
    const submitBtn = screen.getByRole('button', { name: 'Submit Request' })
    expect(submitBtn).toBeDisabled()
  })

  it('renders request data with pending status and action buttons', async () => {
    mockUseModelAccessTiers.mockReturnValue({ data: [], isLoading: false })
    mockUseModelAccessRequests.mockReturnValue({
      data: [
        {
          id: 'r1',
          user_id: 'user-123',
          model_pattern: 'gpt-5',
          justification: 'Need for project',
          status: 'pending',
          created_at: '2025-06-01T12:00:00Z',
          reviewer: null,
        },
      ],
      isLoading: false,
    })
    mockUseMyModelAccess.mockReturnValue({ data: [], isLoading: false })
    renderPage()
    await userEvent.click(screen.getByText('Requests'))
    expect(screen.getByText('user-123')).toBeInTheDocument()
    expect(screen.getByText('gpt-5')).toBeInTheDocument()
    expect(screen.getByText('Need for project')).toBeInTheDocument()
    expect(screen.getByText('pending')).toBeInTheDocument()
    expect(screen.getByTitle('Approve')).toBeInTheDocument()
    expect(screen.getByTitle('Reject')).toBeInTheDocument()
  })

  it('renders approved request without action buttons and shows reviewer', async () => {
    mockUseModelAccessTiers.mockReturnValue({ data: [], isLoading: false })
    mockUseModelAccessRequests.mockReturnValue({
      data: [
        {
          id: 'r2',
          user_id: 'user-456',
          model_pattern: 'claude-3',
          justification: '',
          status: 'approved',
          created_at: '2025-06-01T12:00:00Z',
          reviewer: 'admin@co.com',
        },
      ],
      isLoading: false,
    })
    mockUseMyModelAccess.mockReturnValue({ data: [], isLoading: false })
    renderPage()
    await userEvent.click(screen.getByText('Requests'))
    expect(screen.getByText('approved')).toBeInTheDocument()
    expect(screen.queryByTitle('Approve')).not.toBeInTheDocument()
    expect(screen.getByText('by admin@co.com')).toBeInTheDocument()
  })

  it('renders request with no justification as dashes', async () => {
    mockUseModelAccessTiers.mockReturnValue({ data: [], isLoading: false })
    mockUseModelAccessRequests.mockReturnValue({
      data: [
        {
          id: 'r3',
          user_id: 'user-789',
          model_pattern: 'gpt-4o',
          justification: '',
          status: 'pending',
          created_at: null,
          reviewer: null,
        },
      ],
      isLoading: false,
    })
    mockUseMyModelAccess.mockReturnValue({ data: [], isLoading: false })
    renderPage()
    await userEvent.click(screen.getByText('Requests'))
    const dashes = screen.getAllByText('--')
    expect(dashes.length).toBeGreaterThanOrEqual(1)
  })

  it('switches to My Access tab and shows empty state', async () => {
    mockUseModelAccessTiers.mockReturnValue({ data: [], isLoading: false })
    mockUseModelAccessRequests.mockReturnValue({ data: [], isLoading: false })
    mockUseMyModelAccess.mockReturnValue({ data: [], isLoading: false })
    renderPage()
    await userEvent.click(screen.getByText('My Access'))
    expect(screen.getByText('No active grants')).toBeInTheDocument()
    expect(screen.getByText('Request access to models to see your grants here.')).toBeInTheDocument()
  })

  it('renders my access grants with status and dates', async () => {
    mockUseModelAccessTiers.mockReturnValue({ data: [], isLoading: false })
    mockUseModelAccessRequests.mockReturnValue({ data: [], isLoading: false })
    mockUseMyModelAccess.mockReturnValue({
      data: [
        {
          id: 'g1',
          model_pattern: 'gpt-4o',
          status: 'approved',
          granted_at: '2025-06-01T12:00:00Z',
          expires_at: '2025-09-01T12:00:00Z',
          reviewer: 'admin@co.com',
        },
      ],
      isLoading: false,
    })
    renderPage()
    await userEvent.click(screen.getByText('My Access'))
    expect(screen.getByText('gpt-4o')).toBeInTheDocument()
    expect(screen.getByText('approved')).toBeInTheDocument()
    expect(screen.getByText(/Granted:/)).toBeInTheDocument()
    expect(screen.getByText(/Expires:/)).toBeInTheDocument()
    expect(screen.getByText('Approved by: admin@co.com')).toBeInTheDocument()
  })

  it('renders grant with no expiration', async () => {
    mockUseModelAccessTiers.mockReturnValue({ data: [], isLoading: false })
    mockUseModelAccessRequests.mockReturnValue({ data: [], isLoading: false })
    mockUseMyModelAccess.mockReturnValue({
      data: [
        {
          id: 'g2',
          model_pattern: 'claude-3',
          status: 'approved',
          granted_at: '2025-06-01T12:00:00Z',
          expires_at: null,
          reviewer: null,
        },
      ],
      isLoading: false,
    })
    renderPage()
    await userEvent.click(screen.getByText('My Access'))
    expect(screen.getByText('No expiration')).toBeInTheDocument()
  })

  it('displays tab counts for pending requests', () => {
    mockUseModelAccessTiers.mockReturnValue({
      data: [
        { id: '1', name: 'standard', description: '', requires_approval: false, requires_justification: false, max_grant_duration_days: null, models: [] },
      ],
      isLoading: false,
    })
    mockUseModelAccessRequests.mockReturnValue({
      data: [
        { id: 'r1', user_id: 'u1', model_pattern: 'gpt-4', justification: '', status: 'pending', created_at: null, reviewer: null },
        { id: 'r2', user_id: 'u2', model_pattern: 'gpt-5', justification: '', status: 'approved', created_at: null, reviewer: null },
      ],
      isLoading: false,
    })
    mockUseMyModelAccess.mockReturnValue({ data: [], isLoading: false })
    renderPage()
    // Count badge shows pending count — may appear multiple times
    const badges = screen.getAllByText('1')
    expect(badges.length).toBeGreaterThanOrEqual(1)
  })

  it('shows Request Access button on my-access tab', async () => {
    mockUseModelAccessTiers.mockReturnValue({ data: [], isLoading: false })
    mockUseModelAccessRequests.mockReturnValue({ data: [], isLoading: false })
    mockUseMyModelAccess.mockReturnValue({ data: [], isLoading: false })
    renderPage()
    await userEvent.click(screen.getByText('My Access'))
    expect(screen.getByText('Request Access')).toBeInTheDocument()
  })

  it('shows delete button on tier cards', () => {
    mockUseModelAccessTiers.mockReturnValue({
      data: [
        { id: '1', name: 'basic', description: '', requires_approval: false, requires_justification: false, max_grant_duration_days: null, models: [] },
      ],
      isLoading: false,
    })
    mockUseModelAccessRequests.mockReturnValue({ data: [], isLoading: false })
    mockUseMyModelAccess.mockReturnValue({ data: [], isLoading: false })
    renderPage()
    expect(screen.getByTitle('Delete tier')).toBeInTheDocument()
  })
})
