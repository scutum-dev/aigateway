import { useState } from 'react'
import {
  useWorkflows,
  useCreateWorkflow,
  useExecuteWorkflow,
  useWorkflowExecutions,
  useWorkflowExecution,
} from '../api/hooks'
import { CircleStackIcon, PlayIcon, PlusIcon } from '@heroicons/react/24/outline'
import { SkeletonCard } from '../components/Skeleton'
import EmptyState from '../components/EmptyState'
import { useToast } from '../components/Toast'

const TEMPLATES = [
  {
    type: 'research',
    name: 'Research Agent',
    description:
      'Multi-source research with web search, database queries, and report generation',
    nodes: [
      'parse_query',
      'search_web',
      'search_database',
      'analyze_results',
      'generate_report',
    ],
  },
  {
    type: 'coding',
    name: 'Coding Agent',
    description: 'Iterative code generation with analysis and refinement',
    nodes: [
      'understand_task',
      'read_code',
      'generate_code',
      'analyze_code',
      'finalize_code',
    ],
  },
  {
    type: 'data_analysis',
    name: 'Data Analysis Agent',
    description:
      'SQL query generation, data analysis, and visualization recommendations',
    nodes: [
      'parse_question',
      'query_data',
      'analyze_data',
      'generate_visualization',
      'summarize',
    ],
  },
]

const statusColors: Record<string, string> = {
  running: 'bg-blue-100 text-blue-700',
  completed: 'bg-green-100 text-green-700',
  failed: 'bg-red-100 text-red-700',
  pending: 'bg-yellow-100 text-yellow-700',
}

export default function Workflows() {
  const { data: workflows, isLoading, error } = useWorkflows()
  const createWorkflow = useCreateWorkflow()
  const executeWorkflow = useExecuteWorkflow()
  const { data: executions } = useWorkflowExecutions()
  const toast = useToast()

  const [executeModal, setExecuteModal] = useState<{ type: string; name: string } | null>(null)
  const [executeInput, setExecuteInput] = useState('')
  const [selectedExecId, setSelectedExecId] = useState<string | null>(null)
  const { data: execDetail } = useWorkflowExecution(selectedExecId)
  const [showCreateForm, setShowCreateForm] = useState(false)
  const [createForm, setCreateForm] = useState({
    name: '',
    template_type: 'research',
    description: '',
  })

  const handleExecute = async () => {
    if (!executeModal || !executeInput.trim()) return
    try {
      await executeWorkflow.mutateAsync({
        template_type: executeModal.type,
        input_text: executeInput,
        workflow_name: executeModal.name,
      })
      toast('success', 'Workflow execution started')
      setExecuteModal(null)
      setExecuteInput('')
    } catch {
      toast('error', 'Failed to execute workflow')
    }
  }

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault()
    try {
      await createWorkflow.mutateAsync({
        name: createForm.name,
        template_type: createForm.template_type,
        description: createForm.description || undefined,
      })
      toast('success', 'Workflow created')
      setShowCreateForm(false)
      setCreateForm({ name: '', template_type: 'research', description: '' })
    } catch {
      toast('error', 'Failed to create workflow')
    }
  }

  const formatDuration = (started: string | null, completed: string | null) => {
    if (!started) return '—'
    const start = new Date(started).getTime()
    const end = completed ? new Date(completed).getTime() : Date.now()
    const seconds = Math.round((end - start) / 1000)
    if (seconds < 60) return `${seconds}s`
    return `${Math.floor(seconds / 60)}m ${seconds % 60}s`
  }

  if (isLoading) {
    return (
      <div className="space-y-8">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Workflows</h1>
          <p className="text-gray-600">Pre-built and custom workflow templates</p>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {Array.from({ length: 3 }).map((_, i) => <SkeletonCard key={i} />)}
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="bg-red-50 text-red-700 p-4 rounded-lg">
        Failed to load workflows
      </div>
    )
  }

  return (
    <div className="space-y-8">
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Workflows</h1>
          <p className="text-gray-600">
            Pre-built and custom workflow templates
          </p>
        </div>
        <button onClick={() => setShowCreateForm(true)} className="btn btn-primary">
          <PlusIcon className="w-5 h-5 mr-2" />
          Create Workflow
        </button>
      </div>

      {/* Execute Modal */}
      {executeModal && (
        <div className="card border-2 border-primary-200 bg-primary-50/50">
          <h3 className="font-semibold text-gray-900 mb-1">
            Test: {executeModal.name}
          </h3>
          <p className="text-sm text-gray-600 mb-3">
            Enter a prompt to test the <code className="text-xs bg-gray-100 px-1 rounded">{executeModal.type}</code> workflow.
          </p>
          <textarea
            value={executeInput}
            onChange={(e) => setExecuteInput(e.target.value)}
            className="input font-mono text-sm mb-3"
            rows={3}
            placeholder="Enter your prompt..."
            autoFocus
          />
          <div className="flex space-x-3">
            <button
              onClick={handleExecute}
              className="btn btn-primary"
              disabled={executeWorkflow.isPending || !executeInput.trim()}
            >
              <PlayIcon className="w-4 h-4 mr-2" />
              {executeWorkflow.isPending ? 'Executing...' : 'Execute'}
            </button>
            <button
              onClick={() => { setExecuteModal(null); setExecuteInput('') }}
              className="btn btn-secondary"
            >
              Cancel
            </button>
          </div>
        </div>
      )}

      {/* Create Workflow Form */}
      {showCreateForm && (
        <div className="card">
          <h2 className="text-lg font-semibold mb-4">Create Workflow</h2>
          <form onSubmit={handleCreate} className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="label">Name</label>
                <input
                  type="text"
                  value={createForm.name}
                  onChange={(e) => setCreateForm({ ...createForm, name: e.target.value })}
                  className="input"
                  required
                  placeholder="e.g., My Research Pipeline"
                />
              </div>
              <div>
                <label className="label">Template Type</label>
                <select
                  value={createForm.template_type}
                  onChange={(e) => setCreateForm({ ...createForm, template_type: e.target.value })}
                  className="input"
                >
                  {TEMPLATES.map((t) => (
                    <option key={t.type} value={t.type}>{t.name}</option>
                  ))}
                </select>
              </div>
              <div className="col-span-2">
                <label className="label">Description</label>
                <textarea
                  value={createForm.description}
                  onChange={(e) => setCreateForm({ ...createForm, description: e.target.value })}
                  className="input"
                  rows={2}
                  placeholder="Describe what this workflow does..."
                />
              </div>
            </div>
            <div className="flex space-x-3">
              <button type="submit" className="btn btn-primary" disabled={createWorkflow.isPending}>
                {createWorkflow.isPending ? 'Creating...' : 'Create Workflow'}
              </button>
              <button
                type="button"
                onClick={() => setShowCreateForm(false)}
                className="btn btn-secondary"
              >
                Cancel
              </button>
            </div>
          </form>
        </div>
      )}

      {/* Pre-built Templates */}
      <div>
        <h2 className="text-lg font-semibold mb-4">Pre-built Templates</h2>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {TEMPLATES.map((template) => (
            <div key={template.type} className="card">
              <div className="flex items-center mb-4">
                <div className="p-2 bg-primary-100 rounded-lg mr-3">
                  <CircleStackIcon className="w-5 h-5 text-primary-600" />
                </div>
                <div>
                  <h3 className="font-semibold">{template.name}</h3>
                  <span className="text-xs text-gray-500 font-mono">
                    {template.type}
                  </span>
                </div>
              </div>

              <p className="text-sm text-gray-600 mb-4">
                {template.description}
              </p>

              <div className="mb-4">
                <p className="text-xs text-gray-500 mb-2">Workflow Steps:</p>
                <div className="flex flex-wrap gap-1">
                  {template.nodes.map((node, idx) => (
                    <span key={node} className="flex items-center">
                      <span className="px-2 py-1 bg-gray-100 rounded text-xs font-mono">
                        {node}
                      </span>
                      {idx < template.nodes.length - 1 && (
                        <span className="mx-1 text-gray-400">&rarr;</span>
                      )}
                    </span>
                  ))}
                </div>
              </div>

              <button
                onClick={() => setExecuteModal({ type: template.type, name: template.name })}
                className="btn btn-secondary w-full text-sm"
              >
                <PlayIcon className="w-4 h-4 mr-2" />
                Test Workflow
              </button>
            </div>
          ))}
        </div>
      </div>

      {/* Custom Workflows */}
      <div>
        <h2 className="text-lg font-semibold mb-4">Custom Workflows</h2>

        {workflows && workflows.length > 0 ? (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {workflows.map((workflow) => (
              <div key={workflow.id} className="card">
                <div className="flex items-start justify-between mb-4">
                  <div>
                    <h3 className="font-semibold">{workflow.name}</h3>
                    {workflow.template_type && (
                      <span className="text-xs text-gray-500 font-mono">
                        Based on: {workflow.template_type}
                      </span>
                    )}
                  </div>
                  <span
                    className={`px-2 py-1 rounded text-xs ${
                      workflow.is_active
                        ? 'bg-green-100 text-green-700'
                        : 'bg-gray-100 text-gray-700'
                    }`}
                  >
                    {workflow.is_active ? 'Active' : 'Inactive'}
                  </span>
                </div>

                {workflow.description && (
                  <p className="text-sm text-gray-600 mb-4">
                    {workflow.description}
                  </p>
                )}

                <div className="flex items-center justify-between">
                  <p className="text-xs text-gray-500">
                    Created:{' '}
                    {workflow.created_at
                      ? new Date(workflow.created_at).toLocaleDateString()
                      : 'Unknown'}
                  </p>
                  {workflow.template_type && (
                    <button
                      onClick={() =>
                        setExecuteModal({
                          type: workflow.template_type!,
                          name: workflow.name,
                        })
                      }
                      className="btn btn-secondary text-xs"
                    >
                      <PlayIcon className="w-3.5 h-3.5 mr-1" />
                      Run
                    </button>
                  )}
                </div>
              </div>
            ))}
          </div>
        ) : (
          <EmptyState
            icon={CircleStackIcon}
            title="No custom workflows"
            description="Create custom workflows based on the templates above."
            actionLabel="Create Workflow"
            onAction={() => setShowCreateForm(true)}
          />
        )}
      </div>

      {/* Execution History */}
      <div>
        <h2 className="text-lg font-semibold mb-4">Execution History</h2>

        {executions && executions.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">ID</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Workflow</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Status</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Cost</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Started</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Duration</th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-200">
                {executions.map((exec) => (
                  <tr
                    key={exec.id}
                    className={`hover:bg-gray-50 cursor-pointer ${selectedExecId === exec.id ? 'bg-primary-50' : ''}`}
                    onClick={() => setSelectedExecId(selectedExecId === exec.id ? null : exec.id)}
                  >
                    <td className="px-4 py-3">
                      <code className="text-xs bg-gray-100 px-2 py-1 rounded font-mono">
                        {exec.id.slice(0, 8)}
                      </code>
                    </td>
                    <td className="px-4 py-3 text-sm text-gray-900">
                      {exec.workflow_name || '—'}
                    </td>
                    <td className="px-4 py-3">
                      <span className={`px-2 py-1 rounded text-xs ${statusColors[exec.status] || 'bg-gray-100 text-gray-700'}`}>
                        {exec.status}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-sm text-gray-600">
                      {exec.total_cost != null ? `$${exec.total_cost.toFixed(4)}` : '—'}
                    </td>
                    <td className="px-4 py-3 text-sm text-gray-600">
                      {exec.started_at
                        ? new Date(exec.started_at).toLocaleString()
                        : '—'}
                    </td>
                    <td className="px-4 py-3 text-sm text-gray-600">
                      {formatDuration(exec.started_at, exec.completed_at)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="text-center py-8 text-gray-500 text-sm">
            No executions yet. Test a workflow above to see execution history.
          </div>
        )}

        {/* Execution Detail Panel */}
        {selectedExecId && execDetail && (
          <div className="card mt-4 border border-gray-200">
            <div className="flex items-center justify-between mb-4">
              <h3 className="font-semibold text-gray-900">
                Execution Detail
                <code className="ml-2 text-xs bg-gray-100 px-2 py-1 rounded font-mono">
                  {execDetail.id.slice(0, 8)}
                </code>
                <span className={`ml-2 px-2 py-1 rounded text-xs ${statusColors[execDetail.status] || 'bg-gray-100 text-gray-700'}`}>
                  {execDetail.status}
                </span>
              </h3>
              <button onClick={() => setSelectedExecId(null)} className="btn btn-secondary text-xs">
                Close
              </button>
            </div>

            {execDetail.error && (
              <div className="bg-red-50 text-red-700 text-sm p-3 rounded-lg mb-4">
                <strong>Error:</strong> {execDetail.error}
              </div>
            )}

            {/* Steps */}
            {execDetail.steps && execDetail.steps.length > 0 && (
              <div className="mb-4">
                <p className="text-xs text-gray-500 mb-2 font-medium">Steps:</p>
                <div className="space-y-2">
                  {execDetail.steps
                    .sort((a, b) => a.step_order - b.step_order)
                    .map((step) => (
                      <div key={step.node_name} className="flex items-center gap-3 text-sm">
                        <span className={`w-2 h-2 rounded-full flex-shrink-0 ${
                          step.status === 'completed' ? 'bg-green-500' :
                          step.status === 'running' ? 'bg-blue-500 animate-pulse' :
                          step.status === 'failed' ? 'bg-red-500' : 'bg-gray-300'
                        }`} />
                        <code className="text-xs font-mono bg-gray-100 px-2 py-0.5 rounded">{step.node_name}</code>
                        <span className="text-gray-400 text-xs">{step.duration_ms}ms</span>
                        {step.cost > 0 && <span className="text-gray-400 text-xs">${step.cost.toFixed(4)}</span>}
                        {step.error && <span className="text-red-500 text-xs">{step.error}</span>}
                      </div>
                    ))}
                </div>
              </div>
            )}

            {/* Output */}
            {execDetail.output && (
              <div>
                <p className="text-xs text-gray-500 mb-2 font-medium">Output:</p>
                <pre className="bg-gray-900 text-green-300 text-sm p-4 rounded-lg overflow-x-auto max-h-96 overflow-y-auto whitespace-pre-wrap">
                  <code>{typeof execDetail.output === 'string' ? execDetail.output : JSON.stringify(execDetail.output, null, 2)}</code>
                </pre>
              </div>
            )}

            {/* Summary */}
            <div className="flex gap-6 mt-4 pt-3 border-t border-gray-100 text-xs text-gray-500">
              <span>Tokens: {execDetail.total_tokens.toLocaleString()}</span>
              <span>Cost: ${execDetail.total_cost.toFixed(4)}</span>
              <span>Duration: {execDetail.duration_ms}ms</span>
              {execDetail.current_node && <span>Current: <code className="font-mono">{execDetail.current_node}</code></span>}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
