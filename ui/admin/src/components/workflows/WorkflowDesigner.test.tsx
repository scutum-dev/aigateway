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

import { WorkflowDesigner } from './WorkflowDesigner'

const sampleTemplates = [
  { name: 'research', description: 'Research workflow', nodes: ['search', 'summarize'] },
  { name: 'coding', description: 'Coding workflow', nodes: ['generate', 'review'] },
]

function renderComponent() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter>
        <WorkflowDesigner />
      </MemoryRouter>
    </QueryClientProvider>
  )
}

describe('WorkflowDesigner', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockGet.mockImplementation((url: string) => {
      if (url.includes('templates')) {
        return Promise.resolve({ data: sampleTemplates })
      }
      if (url.includes('workflows')) {
        return Promise.resolve({ data: [] })
      }
      return Promise.resolve({ data: [] })
    })
    mockPost.mockResolvedValue({ data: { id: 'wf-1' } })
    mockPut.mockResolvedValue({ data: {} })
  })

  it('shows Add Nodes heading', () => {
    renderComponent()
    expect(screen.getByText('Add Nodes')).toBeInTheDocument()
  })

  it('shows node type buttons for non-Start/End types', () => {
    renderComponent()
    expect(screen.getByText('LLM Call')).toBeInTheDocument()
    expect(screen.getByText('Tool/MCP')).toBeInTheDocument()
    expect(screen.getByText('Condition')).toBeInTheDocument()
    expect(screen.getByText('Parallel')).toBeInTheDocument()
    expect(screen.getByText('Human Input')).toBeInTheDocument()
  })

  it('shows Load Template section', () => {
    renderComponent()
    expect(screen.getByText('Load Template')).toBeInTheDocument()
    expect(screen.getByText('Select template...')).toBeInTheDocument()
  })

  it('shows Workflow Info inputs', () => {
    renderComponent()
    expect(screen.getByText('Workflow Info')).toBeInTheDocument()
    expect(screen.getByText('Name')).toBeInTheDocument()
    expect(screen.getByText('Description')).toBeInTheDocument()
  })

  it('shows Save Workflow button', () => {
    renderComponent()
    expect(screen.getByText('Save Workflow')).toBeInTheDocument()
  })

  it('shows default Start and End nodes on canvas', () => {
    renderComponent()
    // The node component renders the label from NODE_TYPES plus the node label
    // Start node shows 'Start' in header and 'Start' as label
    const startTexts = screen.getAllByText('Start')
    expect(startTexts.length).toBeGreaterThanOrEqual(2) // header + label
    const endTexts = screen.getAllByText('End')
    expect(endTexts.length).toBeGreaterThanOrEqual(2) // header + label
  })

  it('shows Properties heading', () => {
    renderComponent()
    expect(screen.getByText('Properties')).toBeInTheDocument()
  })

  it('shows empty selection text when no node is selected', () => {
    renderComponent()
    expect(screen.getByText('Select a node or edge to edit its properties')).toBeInTheDocument()
  })

  it('adds a node when an add node button is clicked', async () => {
    renderComponent()
    // Before clicking, only Start and End nodes exist in the palette area (not "LLM Call" on canvas)
    const llmButtons = screen.getAllByText('LLM Call')
    const initialCount = llmButtons.length

    await userEvent.click(llmButtons[0])

    // After clicking, an LLM Call node is added to the canvas with both header and label
    await waitFor(() => {
      const updatedLlmTexts = screen.getAllByText('LLM Call')
      expect(updatedLlmTexts.length).toBeGreaterThan(initialCount)
    })
  })

  it('shows template options in dropdown when templates are loaded', async () => {
    renderComponent()
    await waitFor(() => {
      expect(screen.getByText('research')).toBeInTheDocument()
      expect(screen.getByText('coding')).toBeInTheDocument()
    })
  })

  it('Save button triggers save mutation', async () => {
    renderComponent()
    await userEvent.click(screen.getByText('Save Workflow'))
    await waitFor(() => {
      expect(mockPost).toHaveBeenCalledWith(
        '/api/v1/workflows',
        expect.objectContaining({ name: 'New Workflow' })
      )
    })
  })

  it('workflow name is editable', async () => {
    renderComponent()
    const nameInput = screen.getByDisplayValue('New Workflow')
    expect(nameInput).toBeInTheDocument()
    await userEvent.clear(nameInput)
    await userEvent.type(nameInput, 'My Custom Workflow')
    expect(screen.getByDisplayValue('My Custom Workflow')).toBeInTheDocument()
  })
})
