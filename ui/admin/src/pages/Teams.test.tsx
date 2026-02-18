import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import Teams from './Teams'

const mockUseTeams = vi.fn()
const mockUseCreateTeam = vi.fn()
const mockUseUpdateTeam = vi.fn()
const mockUseDeleteTeam = vi.fn()
const mockUseAddTeamMember = vi.fn()
const mockUseDeleteTeamMember = vi.fn()
const mockUseGuardrailAssignments = vi.fn()
const mockUseGuardrails = vi.fn()
const mockUseAssignGuardrail = vi.fn()
const mockUseUnassignGuardrail = vi.fn()

vi.mock('../api/hooks', () => ({
  useTeams: () => mockUseTeams(),
  useCreateTeam: () => mockUseCreateTeam(),
  useUpdateTeam: () => mockUseUpdateTeam(),
  useDeleteTeam: () => mockUseDeleteTeam(),
  useAddTeamMember: () => mockUseAddTeamMember(),
  useDeleteTeamMember: () => mockUseDeleteTeamMember(),
  useGuardrailAssignments: () => mockUseGuardrailAssignments(),
  useGuardrails: () => mockUseGuardrails(),
  useAssignGuardrail: () => mockUseAssignGuardrail(),
  useUnassignGuardrail: () => mockUseUnassignGuardrail(),
}))

vi.mock('../components/Toast', () => ({
  useToast: () => vi.fn(),
}))

function renderPage() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter>
        <Teams />
      </MemoryRouter>
    </QueryClientProvider>
  )
}

describe('Teams', () => {
  beforeEach(() => {
    mockUseCreateTeam.mockReturnValue({ mutateAsync: vi.fn(), isPending: false })
    mockUseUpdateTeam.mockReturnValue({ mutateAsync: vi.fn(), isPending: false })
    mockUseDeleteTeam.mockReturnValue({ mutateAsync: vi.fn(), isPending: false })
    mockUseAddTeamMember.mockReturnValue({ mutateAsync: vi.fn(), isPending: false })
    mockUseDeleteTeamMember.mockReturnValue({ mutateAsync: vi.fn(), isPending: false })
    mockUseGuardrailAssignments.mockReturnValue({ data: [] })
    mockUseGuardrails.mockReturnValue({ data: [] })
    mockUseAssignGuardrail.mockReturnValue({ mutateAsync: vi.fn(), isPending: false })
    mockUseUnassignGuardrail.mockReturnValue({ mutateAsync: vi.fn(), isPending: false })
  })

  it('shows loading state', () => {
    mockUseTeams.mockReturnValue({ data: undefined, isLoading: true, error: null })
    renderPage()
    expect(screen.getByText('Teams')).toBeInTheDocument()
    expect(screen.getByText('Manage teams and member access')).toBeInTheDocument()
  })

  it('shows error state', () => {
    mockUseTeams.mockReturnValue({ data: undefined, isLoading: false, error: new Error('fail') })
    renderPage()
    expect(screen.getByText('Failed to load teams')).toBeInTheDocument()
  })

  it('shows Create Team button', () => {
    mockUseTeams.mockReturnValue({
      data: [{ team_id: 't1', team_alias: 'Engineering', spend: 10, max_budget: 500, models: [], members_with_roles: [] }],
      isLoading: false,
      error: null,
    })
    renderPage()
    expect(screen.getByText('Create Team')).toBeInTheDocument()
  })

  it('shows team list with data', () => {
    mockUseTeams.mockReturnValue({
      data: [
        { team_id: 't1', team_alias: 'Engineering', spend: 10, max_budget: 500, models: [], members_with_roles: [] },
        { team_id: 't2', team_alias: 'Marketing', spend: 5, max_budget: 200, models: [], members_with_roles: [] },
      ],
      isLoading: false,
      error: null,
    })
    renderPage()
    expect(screen.getByText('Engineering')).toBeInTheDocument()
    expect(screen.getByText('Marketing')).toBeInTheDocument()
    expect(screen.getByText('2 teams')).toBeInTheDocument()
  })

  it('shows empty state when no teams', () => {
    mockUseTeams.mockReturnValue({ data: [], isLoading: false, error: null })
    renderPage()
    expect(screen.getByText('No teams')).toBeInTheDocument()
    expect(screen.getByText('Create teams to organize users and manage access.')).toBeInTheDocument()
  })

  it('opens create form when Create Team clicked', async () => {
    mockUseTeams.mockReturnValue({
      data: [{ team_id: 't1', team_alias: 'Engineering', spend: 10, max_budget: 500, models: [], members_with_roles: [] }],
      isLoading: false,
      error: null,
    })
    renderPage()
    await userEvent.click(screen.getByText('Create Team'))
    expect(screen.getByLabelText('Team Name')).toBeInTheDocument()
  })

  it('form shows team_alias and max_budget fields', async () => {
    mockUseTeams.mockReturnValue({
      data: [{ team_id: 't1', team_alias: 'Engineering', spend: 10, max_budget: 500, models: [], members_with_roles: [] }],
      isLoading: false,
      error: null,
    })
    renderPage()
    await userEvent.click(screen.getByText('Create Team'))
    expect(screen.getByLabelText('Team Name')).toBeInTheDocument()
    expect(screen.getByLabelText('Max Budget ($)')).toBeInTheDocument()
  })

  it('shows team card details with spend and budget values', () => {
    mockUseTeams.mockReturnValue({
      data: [{ team_id: 't1', team_alias: 'Engineering', spend: 10.5, max_budget: 500, models: [], members_with_roles: [] }],
      isLoading: false,
      error: null,
    })
    renderPage()
    expect(screen.getByText('$10.5000')).toBeInTheDocument()
    expect(screen.getByText('$500.00')).toBeInTheDocument()
  })

  it('shows member list when members_with_roles populated', () => {
    mockUseTeams.mockReturnValue({
      data: [{
        team_id: 't1',
        team_alias: 'Engineering',
        spend: 0,
        max_budget: null,
        models: [],
        members_with_roles: [
          { user_id: 'alice@example.com', role: 'admin' },
          { user_id: 'bob@example.com', role: 'user' },
        ],
      }],
      isLoading: false,
      error: null,
    })
    renderPage()
    expect(screen.getByText('Members:')).toBeInTheDocument()
    expect(screen.getByText('alice@example.com')).toBeInTheDocument()
    expect(screen.getByText('bob@example.com')).toBeInTheDocument()
  })

  it('shows "1 team" singular text', () => {
    mockUseTeams.mockReturnValue({
      data: [{ team_id: 't1', team_alias: 'Engineering', spend: 0, max_budget: null, models: [], members_with_roles: [] }],
      isLoading: false,
      error: null,
    })
    renderPage()
    expect(screen.getByText('1 team')).toBeInTheDocument()
  })

  it('shows action buttons per card', () => {
    mockUseTeams.mockReturnValue({
      data: [{ team_id: 't1', team_alias: 'Engineering', spend: 0, max_budget: null, models: [], members_with_roles: [] }],
      isLoading: false,
      error: null,
    })
    renderPage()
    expect(screen.getByText('Add Member')).toBeInTheDocument()
    expect(screen.getByText('Edit')).toBeInTheDocument()
    expect(screen.getByText('Delete')).toBeInTheDocument()
  })
})
