import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { describe, it, expect, vi, beforeEach } from 'vitest'

const mockUseOrganization = vi.fn()
const mockUseUpdateOrganization = vi.fn()
const mockUseBusinessUnits = vi.fn()
const mockUseCreateBusinessUnit = vi.fn()
const mockUseOrgMembers = vi.fn()

vi.mock('../api/hooks', () => ({
  useOrganization: (...args: unknown[]) => mockUseOrganization(...args),
  useUpdateOrganization: () => mockUseUpdateOrganization(),
  useBusinessUnits: (...args: unknown[]) => mockUseBusinessUnits(...args),
  useCreateBusinessUnit: () => mockUseCreateBusinessUnit(),
  useOrgMembers: (...args: unknown[]) => mockUseOrgMembers(...args),
}))

const mockListTeams = vi.fn()
const mockGetSSO = vi.fn()

vi.mock('../api/client', () => ({
  organizationsApi: {
    listTeams: (...args: unknown[]) => mockListTeams(...args),
    getSSO: (...args: unknown[]) => mockGetSSO(...args),
    deleteBU: vi.fn(),
    assignTeam: vi.fn(),
    removeTeam: vi.fn(),
    addMember: vi.fn(),
    removeMember: vi.fn(),
    updateSSO: vi.fn(),
    deleteSSO: vi.fn(),
  },
}))

vi.mock('../components/Toast', () => ({
  useToast: () => vi.fn(),
}))

const mockNavigate = vi.fn()

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom')
  return {
    ...actual,
    useParams: () => ({ orgId: 'org1' }),
    useNavigate: () => mockNavigate,
  }
})

import OrganizationDetail from './OrganizationDetail'

function renderPage() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter>
        <OrganizationDetail />
      </MemoryRouter>
    </QueryClientProvider>
  )
}

const baseOrg = {
  id: 'org1',
  name: 'Acme Corp',
  slug: 'acme-corp',
  description: 'A test organization',
  max_budget: 1000.0,
  allowed_models: ['gpt-4o', 'claude-3.5-sonnet'],
  metadata: {},
  is_active: true,
  created_at: '2025-01-01T00:00:00Z',
  updated_at: '2025-01-01T00:00:00Z',
  bu_count: 3,
  team_count: 5,
  member_count: 20,
}

describe('OrganizationDetail', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockUseUpdateOrganization.mockReturnValue({ mutateAsync: vi.fn(), isPending: false })
    mockUseCreateBusinessUnit.mockReturnValue({ mutateAsync: vi.fn(), isPending: false })
    mockUseBusinessUnits.mockReturnValue({ data: undefined })
    mockUseOrgMembers.mockReturnValue({ data: undefined })
    mockListTeams.mockResolvedValue([])
    mockGetSSO.mockRejectedValue(new Error('No SSO'))
  })

  it('renders loading skeleton when isLoading is true', () => {
    mockUseOrganization.mockReturnValue({ data: undefined, isLoading: true, error: null })
    const { container } = renderPage()
    const pulseElements = container.querySelectorAll('.animate-pulse')
    expect(pulseElements.length).toBeGreaterThan(0)
  })

  it('shows "Organization not found" on error', () => {
    mockUseOrganization.mockReturnValue({ data: undefined, isLoading: false, error: new Error('fail') })
    renderPage()
    expect(screen.getByText('Organization not found')).toBeInTheDocument()
  })

  it('shows org name in header', () => {
    mockUseOrganization.mockReturnValue({ data: baseOrg, isLoading: false, error: null })
    renderPage()
    expect(screen.getByText('Acme Corp')).toBeInTheDocument()
  })

  it('shows org slug in header', () => {
    mockUseOrganization.mockReturnValue({ data: baseOrg, isLoading: false, error: null })
    renderPage()
    expect(screen.getByText('acme-corp')).toBeInTheDocument()
  })

  it('shows overview stats: BU count, team count, member count', () => {
    mockUseOrganization.mockReturnValue({ data: baseOrg, isLoading: false, error: null })
    renderPage()
    expect(screen.getAllByText('Business Units').length).toBeGreaterThanOrEqual(1)
    expect(screen.getByText('3')).toBeInTheDocument()
    expect(screen.getAllByText('Teams').length).toBeGreaterThanOrEqual(1)
    expect(screen.getByText('5')).toBeInTheDocument()
    expect(screen.getAllByText('Members').length).toBeGreaterThanOrEqual(1)
    expect(screen.getByText('20')).toBeInTheDocument()
  })

  it('shows max budget in overview', () => {
    mockUseOrganization.mockReturnValue({ data: baseOrg, isLoading: false, error: null })
    renderPage()
    expect(screen.getByText('Max Budget')).toBeInTheDocument()
    expect(screen.getByText('$1000.00')).toBeInTheDocument()
  })

  it('shows description text in overview', () => {
    mockUseOrganization.mockReturnValue({ data: baseOrg, isLoading: false, error: null })
    renderPage()
    expect(screen.getByText('A test organization')).toBeInTheDocument()
  })

  it('shows allowed models as tags', () => {
    mockUseOrganization.mockReturnValue({ data: baseOrg, isLoading: false, error: null })
    renderPage()
    expect(screen.getByText('Allowed Models:')).toBeInTheDocument()
    expect(screen.getByText('gpt-4o')).toBeInTheDocument()
    expect(screen.getByText('claude-3.5-sonnet')).toBeInTheDocument()
  })

  it('shows Edit Organization button in overview', () => {
    mockUseOrganization.mockReturnValue({ data: baseOrg, isLoading: false, error: null })
    renderPage()
    expect(screen.getByText('Edit Organization')).toBeInTheDocument()
  })

  it('renders all 5 tab buttons', () => {
    mockUseOrganization.mockReturnValue({ data: baseOrg, isLoading: false, error: null })
    renderPage()
    expect(screen.getByText('Overview')).toBeInTheDocument()
    expect(screen.getAllByText('Business Units').length).toBeGreaterThanOrEqual(1)
    expect(screen.getAllByText('Teams').length).toBeGreaterThanOrEqual(2) // stat label + tab
    expect(screen.getAllByText('Members').length).toBeGreaterThanOrEqual(2) // stat label + tab
    expect(screen.getByText('SSO')).toBeInTheDocument()
  })

  it('Business Units tab shows empty state', async () => {
    mockUseOrganization.mockReturnValue({ data: baseOrg, isLoading: false, error: null })
    mockUseBusinessUnits.mockReturnValue({ data: [] })
    renderPage()

    // Click Business Units tab - need to find the tab button specifically
    const buTab = screen.getAllByText('Business Units').find(el => el.closest('button[class*="border-b-2"]'))
    await userEvent.click(buTab!)

    expect(screen.getByText('No business units yet')).toBeInTheDocument()
  })

  it('Business Units tab shows BU cards with data', async () => {
    mockUseOrganization.mockReturnValue({ data: baseOrg, isLoading: false, error: null })
    mockUseBusinessUnits.mockReturnValue({
      data: [
        { id: 'bu1', org_id: 'org1', name: 'Engineering', slug: 'engineering', description: 'Eng team', max_budget: 500.0, is_active: true, created_at: '2025-01-01' },
        { id: 'bu2', org_id: 'org1', name: 'Marketing', slug: 'marketing', description: null, max_budget: null, is_active: true, created_at: '2025-01-01' },
      ],
    })
    renderPage()

    const buTab = screen.getAllByText('Business Units').find(el => el.closest('button[class*="border-b-2"]'))
    await userEvent.click(buTab!)

    expect(screen.getByText('Engineering')).toBeInTheDocument()
    expect(screen.getByText('engineering')).toBeInTheDocument()
    expect(screen.getByText('Eng team')).toBeInTheDocument()
    expect(screen.getByText('Budget: $500.00')).toBeInTheDocument()
    expect(screen.getByText('Marketing')).toBeInTheDocument()
    expect(screen.getByText('marketing')).toBeInTheDocument()
  })

  it('Business Units tab shows Add BU button', async () => {
    mockUseOrganization.mockReturnValue({ data: baseOrg, isLoading: false, error: null })
    mockUseBusinessUnits.mockReturnValue({ data: [] })
    renderPage()

    const buTab = screen.getAllByText('Business Units').find(el => el.closest('button[class*="border-b-2"]'))
    await userEvent.click(buTab!)

    expect(screen.getByText('Add BU')).toBeInTheDocument()
  })

  it('Teams tab shows empty state', async () => {
    mockUseOrganization.mockReturnValue({ data: baseOrg, isLoading: false, error: null })
    mockListTeams.mockResolvedValue([])
    renderPage()

    // Click the Teams tab
    const teamsTab = screen.getAllByText('Teams').find(el => el.closest('button[class*="border-b-2"]'))
    await userEvent.click(teamsTab!)

    expect(screen.getByText('No teams assigned')).toBeInTheDocument()
  })

  it('Teams tab shows team data', async () => {
    mockUseOrganization.mockReturnValue({ data: baseOrg, isLoading: false, error: null })
    mockListTeams.mockResolvedValue([
      { team_id: 'team-alpha', org_id: 'org1', bu_id: 'bu1' },
      { team_id: 'team-beta', org_id: 'org1', bu_id: null },
    ])
    renderPage()

    const teamsTab = screen.getAllByText('Teams').find(el => el.closest('button[class*="border-b-2"]'))
    await userEvent.click(teamsTab!)

    // The teams data comes from a real useQuery so we need to wait for it
    const teamAlpha = await screen.findByText('team-alpha')
    expect(teamAlpha).toBeInTheDocument()
    expect(screen.getByText('team-beta')).toBeInTheDocument()
    expect(screen.getByText('Assigned Teams')).toBeInTheDocument()
  })

  it('Members tab shows empty state', async () => {
    mockUseOrganization.mockReturnValue({ data: baseOrg, isLoading: false, error: null })
    mockUseOrgMembers.mockReturnValue({ data: [] })
    renderPage()

    const membersTab = screen.getAllByText('Members').find(el => el.closest('button[class*="border-b-2"]'))
    await userEvent.click(membersTab!)

    expect(screen.getByText('No members yet')).toBeInTheDocument()
  })

  it('Members tab shows member data with roles', async () => {
    mockUseOrganization.mockReturnValue({ data: baseOrg, isLoading: false, error: null })
    mockUseOrgMembers.mockReturnValue({
      data: [
        { id: 'm1', user_id: 'u1', email: 'alice@acme.com', display_name: 'Alice', org_id: 'org1', role: 'admin', bu_id: null, created_at: '2025-01-15T00:00:00Z' },
        { id: 'm2', user_id: 'u2', email: 'bob@acme.com', display_name: 'Bob', org_id: 'org1', role: 'member', bu_id: null, created_at: '2025-02-01T00:00:00Z' },
      ],
    })
    renderPage()

    const membersTab = screen.getAllByText('Members').find(el => el.closest('button[class*="border-b-2"]'))
    await userEvent.click(membersTab!)

    expect(screen.getByText('Alice')).toBeInTheDocument()
    expect(screen.getByText('alice@acme.com')).toBeInTheDocument()
    expect(screen.getByText('admin')).toBeInTheDocument()
    expect(screen.getByText('Bob')).toBeInTheDocument()
    expect(screen.getByText('bob@acme.com')).toBeInTheDocument()
    expect(screen.getByText('member')).toBeInTheDocument()
  })

  it('SSO tab shows "No SSO" state when no config', async () => {
    mockUseOrganization.mockReturnValue({ data: baseOrg, isLoading: false, error: null })
    mockGetSSO.mockRejectedValue(new Error('Not found'))
    renderPage()

    await userEvent.click(screen.getByText('SSO'))

    expect(screen.getByText('Single Sign-On (SSO)')).toBeInTheDocument()
    expect(screen.getByText('No SSO configured. Set up an OIDC or SAML provider below.')).toBeInTheDocument()
    expect(screen.getByText('Save SSO Configuration')).toBeInTheDocument()
  })

  it('SSO tab shows SSO details when configured', async () => {
    mockUseOrganization.mockReturnValue({ data: baseOrg, isLoading: false, error: null })
    mockGetSSO.mockResolvedValue({
      id: 'sso1',
      org_id: 'org1',
      provider_type: 'oidc',
      provider_name: 'Corporate Okta',
      client_id: 'client-abc-123',
      issuer_url: 'https://okta.acme.com',
      is_active: true,
      created_at: '2025-01-01',
    })
    renderPage()

    await userEvent.click(screen.getByText('SSO'))

    const providerName = await screen.findByText('Corporate Okta')
    expect(providerName).toBeInTheDocument()
    expect(screen.getByText('oidc')).toBeInTheDocument()
    expect(screen.getByText('client-abc-123')).toBeInTheDocument()
    expect(screen.getByText('Active')).toBeInTheDocument()
    expect(screen.getByText('https://okta.acme.com')).toBeInTheDocument()
    expect(screen.getByText('Disable SSO')).toBeInTheDocument()
  })

  it('back button navigates to /organizations', async () => {
    mockUseOrganization.mockReturnValue({ data: baseOrg, isLoading: false, error: null })
    renderPage()

    // The back button is the ArrowLeftIcon button
    const backButton = screen.getByText('Acme Corp').closest('.flex')?.querySelector('button')
    await userEvent.click(backButton!)

    expect(mockNavigate).toHaveBeenCalledWith('/organizations')
  })
})
