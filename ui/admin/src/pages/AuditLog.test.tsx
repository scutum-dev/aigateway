import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { describe, it, expect, vi, beforeEach } from 'vitest'

const mockUseAuditLogs = vi.fn()

vi.mock('../api/hooks', () => ({
  useAuditLogs: () => mockUseAuditLogs(),
}))

vi.mock('../api/client', () => ({
  auditApi: { export: vi.fn() },
}))

vi.mock('../components/Toast', () => ({
  useToast: () => vi.fn(),
}))

import AuditLog from './AuditLog'

function renderPage() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter>
        <AuditLog />
      </MemoryRouter>
    </QueryClientProvider>
  )
}

describe('AuditLog', () => {
  it('renders loading state', () => {
    mockUseAuditLogs.mockReturnValue({ data: undefined, isLoading: true, error: null })
    renderPage()
    expect(screen.getByText('Audit Log')).toBeInTheDocument()
    expect(screen.getByText('Track all administrative actions')).toBeInTheDocument()
  })

  it('renders error state', () => {
    mockUseAuditLogs.mockReturnValue({ data: undefined, isLoading: false, error: new Error('fail') })
    renderPage()
    expect(screen.getByText('Failed to load audit logs')).toBeInTheDocument()
  })

  it('renders empty state when no events', () => {
    mockUseAuditLogs.mockReturnValue({ data: [], isLoading: false, error: null })
    renderPage()
    expect(screen.getByText('No audit events found')).toBeInTheDocument()
  })

  it('renders audit log entries in a table', () => {
    mockUseAuditLogs.mockReturnValue({
      data: [
        {
          id: '1',
          timestamp: '2025-01-15T10:00:00Z',
          actor_id: 'admin@test.com',
          actor_email: 'admin@test.com',
          actor_ip: '192.168.1.1',
          action: 'create',
          resource_type: 'organization',
          resource_name: 'Acme Corp',
          resource_id: 'org-123',
          changes: { name: 'Acme Corp' },
        },
      ],
      isLoading: false,
      error: null,
    })
    renderPage()
    expect(screen.getByText('1 event')).toBeInTheDocument()
    expect(screen.getAllByText('admin@test.com').length).toBeGreaterThanOrEqual(1)
    expect(screen.getByText('create')).toBeInTheDocument()
    expect(screen.getByText('organization')).toBeInTheDocument()
    expect(screen.getByText('Acme Corp')).toBeInTheDocument()
  })

  it('shows export buttons (CSV and JSON)', () => {
    mockUseAuditLogs.mockReturnValue({ data: [], isLoading: false, error: null })
    renderPage()
    expect(screen.getByText('CSV')).toBeInTheDocument()
    expect(screen.getByText('JSON')).toBeInTheDocument()
  })

  it('toggles filter panel when Filters button is clicked', async () => {
    mockUseAuditLogs.mockReturnValue({ data: [], isLoading: false, error: null })
    renderPage()
    await userEvent.click(screen.getByText('Filters'))
    expect(screen.getByLabelText('Resource Type')).toBeInTheDocument()
    expect(screen.getByLabelText('Action')).toBeInTheDocument()
    expect(screen.getByText('Apply')).toBeInTheDocument()
  })
})
