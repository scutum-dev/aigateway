import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import Guardrails from './Guardrails'

const mockUseGuardrails = vi.fn()
const mockUseCreateGuardrail = vi.fn()
const mockUseUpdateGuardrail = vi.fn()
const mockUseDeleteGuardrail = vi.fn()
const mockUseGuardrailEvents = vi.fn()
const mockUseGuardrailAssignments = vi.fn()

vi.mock('../api/hooks', () => ({
  useGuardrails: () => mockUseGuardrails(),
  useCreateGuardrail: () => mockUseCreateGuardrail(),
  useUpdateGuardrail: () => mockUseUpdateGuardrail(),
  useDeleteGuardrail: () => mockUseDeleteGuardrail(),
  useGuardrailEvents: () => mockUseGuardrailEvents(),
  useGuardrailAssignments: () => mockUseGuardrailAssignments(),
}))

vi.mock('../components/Toast', () => ({
  useToast: () => vi.fn(),
}))

function renderPage() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter>
        <Guardrails />
      </MemoryRouter>
    </QueryClientProvider>
  )
}

describe('Guardrails', () => {
  beforeEach(() => {
    mockUseCreateGuardrail.mockReturnValue({ mutateAsync: vi.fn(), isPending: false })
    mockUseUpdateGuardrail.mockReturnValue({ mutateAsync: vi.fn(), isPending: false })
    mockUseDeleteGuardrail.mockReturnValue({ mutateAsync: vi.fn(), isPending: false })
    mockUseGuardrailEvents.mockReturnValue({ data: [] })
    mockUseGuardrailAssignments.mockReturnValue({ data: [] })
  })

  it('shows loading state', () => {
    mockUseGuardrails.mockReturnValue({ data: undefined, isLoading: true, error: null })
    renderPage()
    expect(screen.getByText('Guardrails')).toBeInTheDocument()
    expect(screen.getByText('Content safety scanning and PII protection')).toBeInTheDocument()
  })

  it('shows error state', () => {
    mockUseGuardrails.mockReturnValue({ data: undefined, isLoading: false, error: new Error('fail') })
    renderPage()
    expect(screen.getByText('Failed to load guardrails')).toBeInTheDocument()
  })

  it('shows guardrail profiles table with data', () => {
    mockUseGuardrails.mockReturnValue({
      data: [
        {
          id: 'g1',
          name: 'Default Safety',
          description: 'Standard safety checks',
          enable_prompt_injection: true,
          enable_pii_detection: true,
          enable_toxicity: true,
          enable_secrets_detection: true,
          enable_invisible_text: false,
          enable_malicious_urls: true,
          enable_sensitive_output: false,
          on_fail: 'block',
          is_active: true,
          prompt_injection_threshold: 0.9,
          pii_action: 'anonymize',
          pii_entities: [],
          toxicity_threshold: 0.7,
          banned_topics: [],
          mode: 'block',
        },
      ],
      isLoading: false,
      error: null,
    })
    renderPage()
    expect(screen.getByText('Default Safety')).toBeInTheDocument()
    expect(screen.getByText('Standard safety checks')).toBeInTheDocument()
    expect(screen.getByText('Active')).toBeInTheDocument()
  })

  it('shows New Profile button', () => {
    mockUseGuardrails.mockReturnValue({ data: [], isLoading: false, error: null })
    renderPage()
    expect(screen.getByText('New Profile')).toBeInTheDocument()
  })

  it('shows empty message when no guardrail profiles', () => {
    mockUseGuardrails.mockReturnValue({ data: [], isLoading: false, error: null })
    renderPage()
    expect(screen.getByText('No guardrail profiles configured')).toBeInTheDocument()
  })

  it('shows profiles and events tabs', () => {
    mockUseGuardrails.mockReturnValue({ data: [], isLoading: false, error: null })
    renderPage()
    expect(screen.getByText('profiles')).toBeInTheDocument()
    expect(screen.getByText('events')).toBeInTheDocument()
  })

  it('opens New Profile form when clicked', async () => {
    mockUseGuardrails.mockReturnValue({ data: [], isLoading: false, error: null })
    renderPage()
    await userEvent.click(screen.getByText('New Profile'))
    expect(screen.getByText('New Guardrail Profile')).toBeInTheDocument()
    expect(screen.getByLabelText('Name')).toBeInTheDocument()
  })

  it('form shows scanner toggles', async () => {
    mockUseGuardrails.mockReturnValue({ data: [], isLoading: false, error: null })
    renderPage()
    await userEvent.click(screen.getByText('New Profile'))
    expect(screen.getByText('Prompt Injection Detection')).toBeInTheDocument()
    expect(screen.getByText('PII Detection')).toBeInTheDocument()
    expect(screen.getByText('Toxicity Detection')).toBeInTheDocument()
    expect(screen.getByText('Secrets Detection')).toBeInTheDocument()
    expect(screen.getByText('Invisible Text Detection')).toBeInTheDocument()
  })

  it('shows scanner badges in table', () => {
    mockUseGuardrails.mockReturnValue({
      data: [
        {
          id: 'g1',
          name: 'Default Safety',
          description: 'Standard safety checks',
          enable_prompt_injection: true,
          enable_pii_detection: true,
          enable_toxicity: false,
          enable_secrets_detection: false,
          enable_invisible_text: false,
          enable_malicious_urls: false,
          enable_sensitive_output: false,
          on_fail: 'block',
          is_active: true,
          prompt_injection_threshold: 0.9,
          pii_action: 'anonymize',
          pii_entities: [],
          toxicity_threshold: 0.7,
          banned_topics: [],
          mode: 'block',
        },
      ],
      isLoading: false,
      error: null,
    })
    renderPage()
    expect(screen.getByText('Injection')).toBeInTheDocument()
    expect(screen.getByText('PII')).toBeInTheDocument()
  })

  it('events tab shows empty message when no events', async () => {
    mockUseGuardrails.mockReturnValue({ data: [], isLoading: false, error: null })
    mockUseGuardrailEvents.mockReturnValue({ data: [] })
    renderPage()
    await userEvent.click(screen.getByText('events'))
    expect(screen.getByText('No guardrail events recorded yet')).toBeInTheDocument()
  })

  it('events tab renders event rows when data exists', async () => {
    mockUseGuardrails.mockReturnValue({ data: [], isLoading: false, error: null })
    mockUseGuardrailEvents.mockReturnValue({
      data: [
        {
          id: 'e1',
          event_type: 'input_blocked',
          scanner_name: 'prompt_injection',
          model: 'gpt-4o',
          risk_score: 0.95,
          action_taken: 'blocked',
          created_at: '2025-01-15T10:00:00Z',
        },
      ],
    })
    renderPage()
    await userEvent.click(screen.getByText('events'))
    expect(screen.getByText('input_blocked')).toBeInTheDocument()
    expect(screen.getByText('prompt_injection')).toBeInTheDocument()
    expect(screen.getByText('gpt-4o')).toBeInTheDocument()
  })

  it('shows "block" on_fail text in profile table', () => {
    mockUseGuardrails.mockReturnValue({
      data: [
        {
          id: 'g1',
          name: 'Default Safety',
          enable_prompt_injection: true,
          enable_pii_detection: false,
          enable_toxicity: false,
          enable_secrets_detection: false,
          enable_invisible_text: false,
          enable_malicious_urls: false,
          enable_sensitive_output: false,
          on_fail: 'block',
          is_active: true,
          prompt_injection_threshold: 0.9,
          pii_action: 'anonymize',
          pii_entities: [],
          toxicity_threshold: 0.7,
          banned_topics: [],
          mode: 'block',
        },
      ],
      isLoading: false,
      error: null,
    })
    renderPage()
    expect(screen.getByText('block')).toBeInTheDocument()
  })

  it('shows Edit and Delete buttons per row', () => {
    mockUseGuardrails.mockReturnValue({
      data: [
        {
          id: 'g1',
          name: 'Default Safety',
          enable_prompt_injection: true,
          enable_pii_detection: false,
          enable_toxicity: false,
          enable_secrets_detection: false,
          enable_invisible_text: false,
          enable_malicious_urls: false,
          enable_sensitive_output: false,
          on_fail: 'block',
          is_active: true,
          prompt_injection_threshold: 0.9,
          pii_action: 'anonymize',
          pii_entities: [],
          toxicity_threshold: 0.7,
          banned_topics: [],
          mode: 'block',
        },
      ],
      isLoading: false,
      error: null,
    })
    renderPage()
    expect(screen.getByText('Edit')).toBeInTheDocument()
    expect(screen.getByText('Delete')).toBeInTheDocument()
  })
})
