import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { describe, it, expect, vi, beforeEach } from 'vitest'

const mockUseOrganizations = vi.fn()
const mockUseCreateOrganization = vi.fn()
const mockUseDeleteOrganization = vi.fn()

vi.mock('../api/hooks', () => ({
  useOrganizations: () => mockUseOrganizations(),
  useCreateOrganization: () => mockUseCreateOrganization(),
  useDeleteOrganization: () => mockUseDeleteOrganization(),
}))

vi.mock('../components/Toast', () => ({
  useToast: () => vi.fn(),
}))

import Organizations from './Organizations'

function renderPage() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter>
        <Organizations />
      </MemoryRouter>
    </QueryClientProvider>
  )
}

describe('Organizations', () => {
  beforeEach(() => {
    mockUseCreateOrganization.mockReturnValue({ mutateAsync: vi.fn(), isPending: false })
    mockUseDeleteOrganization.mockReturnValue({ mutateAsync: vi.fn() })
  })

  it('renders loading state with skeleton cards', () => {
    mockUseOrganizations.mockReturnValue({ data: undefined, isLoading: true, error: null })
    renderPage()
    expect(screen.getByText('Organizations')).toBeInTheDocument()
    expect(screen.getByText('Manage organizations and multi-tenancy')).toBeInTheDocument()
  })

  it('renders error state', () => {
    mockUseOrganizations.mockReturnValue({ data: undefined, isLoading: false, error: new Error('fail') })
    renderPage()
    expect(screen.getByText('Failed to load organizations')).toBeInTheDocument()
  })

  it('renders empty state when no organizations', () => {
    mockUseOrganizations.mockReturnValue({ data: [], isLoading: false, error: null })
    renderPage()
    expect(screen.getByText('No organizations')).toBeInTheDocument()
    expect(screen.getAllByText('Create Organization').length).toBeGreaterThanOrEqual(1)
  })

  it('renders organization data in a table', () => {
    mockUseOrganizations.mockReturnValue({
      data: [
        { id: '1', name: 'Acme Corp', slug: 'acme-corp', bu_count: 3, team_count: 5, member_count: 20, max_budget: 500.0, is_active: true },
        { id: '2', name: 'Beta Inc', slug: 'beta-inc', bu_count: 1, team_count: 2, member_count: 8, max_budget: null, is_active: false },
      ],
      isLoading: false,
      error: null,
    })
    renderPage()
    expect(screen.getByText('2 organizations')).toBeInTheDocument()
    expect(screen.getByText('Acme Corp')).toBeInTheDocument()
    expect(screen.getByText('acme-corp')).toBeInTheDocument()
    expect(screen.getByText('$500.00')).toBeInTheDocument()
    expect(screen.getByText('Active')).toBeInTheDocument()
    expect(screen.getByText('Inactive')).toBeInTheDocument()
  })

  it('shows create form when Create Organization is clicked', async () => {
    mockUseOrganizations.mockReturnValue({ data: [], isLoading: false, error: null })
    renderPage()
    const buttons = screen.getAllByText('Create Organization')
    await userEvent.click(buttons[0])
    expect(screen.getByLabelText('Name')).toBeInTheDocument()
    expect(screen.getByLabelText('Slug')).toBeInTheDocument()
  })

  it('shows BU count display in table', () => {
    mockUseOrganizations.mockReturnValue({
      data: [
        { id: '1', name: 'Acme Corp', slug: 'acme-corp', bu_count: 3, team_count: 5, member_count: 20, max_budget: 500.0, is_active: true },
      ],
      isLoading: false,
      error: null,
    })
    renderPage()
    expect(screen.getByText('3')).toBeInTheDocument()
    expect(screen.getByText('5')).toBeInTheDocument()
    expect(screen.getByText('20')).toBeInTheDocument()
  })

  it('shows Active and Inactive badges', () => {
    mockUseOrganizations.mockReturnValue({
      data: [
        { id: '1', name: 'Acme Corp', slug: 'acme-corp', bu_count: 0, team_count: 0, member_count: 0, max_budget: null, is_active: true },
        { id: '2', name: 'Beta Inc', slug: 'beta-inc', bu_count: 0, team_count: 0, member_count: 0, max_budget: null, is_active: false },
      ],
      isLoading: false,
      error: null,
    })
    renderPage()
    expect(screen.getByText('Active')).toBeInTheDocument()
    expect(screen.getByText('Inactive')).toBeInTheDocument()
  })

  it('shows create form fields including max_budget and description', async () => {
    mockUseOrganizations.mockReturnValue({ data: [], isLoading: false, error: null })
    renderPage()
    const buttons = screen.getAllByText('Create Organization')
    await userEvent.click(buttons[0])
    expect(screen.getByLabelText('Max Budget ($)')).toBeInTheDocument()
    expect(screen.getByLabelText('Description')).toBeInTheDocument()
    expect(screen.getByLabelText('Allowed Models (comma-separated)')).toBeInTheDocument()
  })

  it('shows singular "1 organization" text', () => {
    mockUseOrganizations.mockReturnValue({
      data: [
        { id: '1', name: 'Acme Corp', slug: 'acme-corp', bu_count: 0, team_count: 0, member_count: 0, max_budget: null, is_active: true },
      ],
      isLoading: false,
      error: null,
    })
    renderPage()
    expect(screen.getByText('1 organization')).toBeInTheDocument()
  })
})
