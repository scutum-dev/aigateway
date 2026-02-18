import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { describe, it, expect, vi, beforeEach } from 'vitest'

const mockUseReportsSummary = vi.fn()
const mockUseMCPServers = vi.fn()
const mockUseGuardrails = vi.fn()
const mockUseSettings = vi.fn()

vi.mock('../api/hooks', () => ({
  useReportsSummary: () => mockUseReportsSummary(),
  useMCPServers: () => mockUseMCPServers(),
  useGuardrails: () => mockUseGuardrails(),
  useSettings: () => mockUseSettings(),
}))

import Onboarding from './Onboarding'

function renderComponent() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter>
        <Onboarding />
      </MemoryRouter>
    </QueryClientProvider>
  )
}

describe('Onboarding', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    localStorage.clear()
    mockUseReportsSummary.mockReturnValue({ data: undefined })
    mockUseMCPServers.mockReturnValue({ data: undefined })
    mockUseGuardrails.mockReturnValue({ data: undefined })
    mockUseSettings.mockReturnValue({ data: undefined })
  })

  it('returns null when localStorage has onboarding_dismissed = "1"', () => {
    localStorage.setItem('onboarding_dismissed', '1')
    const { container } = renderComponent()
    expect(container.innerHTML).toBe('')
  })

  it('shows "Getting Started" heading', () => {
    renderComponent()
    expect(screen.getByText('Getting Started')).toBeInTheDocument()
  })

  it('shows "0 of 4 complete" and "0%" when all hooks return no data', () => {
    renderComponent()
    expect(screen.getByText('0 of 4 complete')).toBeInTheDocument()
    expect(screen.getByText('0%')).toBeInTheDocument()
  })

  it('shows partial complete count when some hooks have data', () => {
    mockUseReportsSummary.mockReturnValue({ data: { requests_today: 10 } })
    mockUseSettings.mockReturnValue({ data: { some_setting: true } })
    renderComponent()
    expect(screen.getByText('2 of 4 complete')).toBeInTheDocument()
    expect(screen.getByText('50%')).toBeInTheDocument()
  })

  it('shows "100%" when all 4 hooks have data', () => {
    mockUseReportsSummary.mockReturnValue({ data: { requests_today: 5 } })
    mockUseMCPServers.mockReturnValue({ data: [{ id: '1' }] })
    mockUseGuardrails.mockReturnValue({ data: [{ id: '1' }] })
    mockUseSettings.mockReturnValue({ data: { some_setting: true } })
    renderComponent()
    expect(screen.getByText('4 of 4 complete')).toBeInTheDocument()
    expect(screen.getByText('100%')).toBeInTheDocument()
  })

  it('shows all 4 step labels', () => {
    renderComponent()
    expect(screen.getByText('LiteLLM receiving traffic')).toBeInTheDocument()
    expect(screen.getByText('MCP server configured')).toBeInTheDocument()
    expect(screen.getByText('Guardrail profile created')).toBeInTheDocument()
    expect(screen.getByText('Settings reviewed')).toBeInTheDocument()
  })

  it('shows line-through class on completed steps', () => {
    mockUseReportsSummary.mockReturnValue({ data: { requests_today: 10 } })
    mockUseMCPServers.mockReturnValue({ data: [{ id: '1' }] })
    renderComponent()

    const trafficLabel = screen.getByText('LiteLLM receiving traffic')
    expect(trafficLabel.className).toContain('line-through')

    const mcpLabel = screen.getByText('MCP server configured')
    expect(mcpLabel.className).toContain('line-through')

    const guardrailLabel = screen.getByText('Guardrail profile created')
    expect(guardrailLabel.className).not.toContain('line-through')

    const settingsLabel = screen.getByText('Settings reviewed')
    expect(settingsLabel.className).not.toContain('line-through')
  })

  it('dismiss button sets localStorage and component disappears', async () => {
    renderComponent()
    expect(screen.getByText('Getting Started')).toBeInTheDocument()

    const dismissButton = screen.getByTitle('Dismiss')
    await userEvent.click(dismissButton)

    expect(localStorage.getItem('onboarding_dismissed')).toBe('1')
    expect(screen.queryByText('Getting Started')).not.toBeInTheDocument()
  })

  it('link hrefs are correct', () => {
    renderComponent()

    const trafficLink = screen.getByText('LiteLLM receiving traffic').closest('a')
    expect(trafficLink).toHaveAttribute('href', '/')

    const mcpLink = screen.getByText('MCP server configured').closest('a')
    expect(mcpLink).toHaveAttribute('href', '/mcp-servers')

    const guardrailLink = screen.getByText('Guardrail profile created').closest('a')
    expect(guardrailLink).toHaveAttribute('href', '/guardrails')

    const settingsLink = screen.getByText('Settings reviewed').closest('a')
    expect(settingsLink).toHaveAttribute('href', '/settings')
  })

  it('progress bar width matches percentage', () => {
    mockUseReportsSummary.mockReturnValue({ data: { requests_today: 5 } })
    mockUseMCPServers.mockReturnValue({ data: [{ id: '1' }] })
    renderComponent()

    // 2 of 4 = 50%
    const progressBar = document.querySelector('.bg-indigo-500')
    expect(progressBar).toHaveStyle({ width: '50%' })
  })
})
