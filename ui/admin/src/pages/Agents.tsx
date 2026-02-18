import { useState } from 'react'
import { useAgents, useCreateAgent, useUpdateAgent, useDeleteAgent, useTestAgent, useSyncMCPToGateway, useGatewayConfigPreview } from '../api/hooks'
import { PlusIcon, CpuChipIcon, PencilIcon, TrashIcon, SignalIcon, RocketLaunchIcon, EyeIcon } from '@heroicons/react/24/outline'
import { SkeletonCard } from '../components/Skeleton'
import EmptyState from '../components/EmptyState'
import { useToast } from '../components/Toast'
import type { A2AAgentConfig } from '../types'

export default function Agents() {
  const { data: agents, isLoading, error } = useAgents()
  const createAgent = useCreateAgent()
  const updateAgent = useUpdateAgent()
  const deleteAgent = useDeleteAgent()
  const testAgent = useTestAgent()
  const syncToGateway = useSyncMCPToGateway()
  const { data: preview, refetch: fetchPreview, isFetching: isLoadingPreview } = useGatewayConfigPreview()
  const toast = useToast()

  const [showForm, setShowForm] = useState(false)
  const [editingAgent, setEditingAgent] = useState<A2AAgentConfig | null>(null)
  const [confirmDelete, setConfirmDelete] = useState<string | null>(null)
  const [testingId, setTestingId] = useState<string | null>(null)
  const [showPreview, setShowPreview] = useState(false)
  const [confirmDeploy, setConfirmDeploy] = useState(false)
  const [form, setForm] = useState({
    name: '',
    description: '',
    url: '',
    skills: '',
  })

  const resetForm = () => {
    setForm({ name: '', description: '', url: '', skills: '' })
    setEditingAgent(null)
    setShowForm(false)
  }

  const openEditForm = (agent: A2AAgentConfig) => {
    setEditingAgent(agent)
    setForm({
      name: agent.name,
      description: agent.description || '',
      url: agent.url,
      skills: agent.skills?.join(', ') || '',
    })
    setShowForm(true)
  }

  if (isLoading) {
    return (
      <div className="space-y-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">A2A Agents</h1>
          <p className="text-gray-600">Configure Agent-to-Agent protocol agents</p>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {Array.from({ length: 3 }).map((_, i) => <SkeletonCard key={i} />)}
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="bg-red-50 text-red-700 p-4 rounded-lg">
        Failed to load A2A agents
      </div>
    )
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    const payload = {
      name: form.name,
      description: form.description || undefined,
      url: form.url,
      skills: form.skills ? form.skills.split(',').map(s => s.trim()).filter(Boolean) : [],
    }

    try {
      if (editingAgent) {
        await updateAgent.mutateAsync({ id: editingAgent.id, data: payload })
        toast('success', 'A2A agent updated')
      } else {
        await createAgent.mutateAsync(payload)
        toast('success', 'A2A agent added')
      }
      resetForm()
    } catch {
      toast('error', editingAgent ? 'Failed to update A2A agent' : 'Failed to add A2A agent')
    }
  }

  const handleDelete = async (id: string) => {
    try {
      await deleteAgent.mutateAsync(id)
      setConfirmDelete(null)
      toast('success', 'A2A agent deleted')
    } catch {
      toast('error', 'Failed to delete A2A agent')
    }
  }

  const handleTest = async (id: string) => {
    setTestingId(id)
    try {
      const result = await testAgent.mutateAsync(id)
      if (result.status === 'ok') {
        toast('success', `Connection OK: ${result.message}`)
      } else {
        toast('error', `Connection failed: ${result.message}`)
      }
    } catch {
      toast('error', 'Failed to test A2A agent')
    } finally {
      setTestingId(null)
    }
  }

  const handleToggleActive = async (agent: A2AAgentConfig) => {
    try {
      await updateAgent.mutateAsync({
        id: agent.id,
        data: { is_active: !agent.is_active },
      })
      toast('success', `Agent ${agent.is_active ? 'deactivated' : 'activated'}`)
    } catch {
      toast('error', 'Failed to update agent status')
    }
  }

  const handleTogglePreview = () => {
    if (!showPreview) {
      fetchPreview()
    }
    setShowPreview(!showPreview)
  }

  const handleDeploy = async () => {
    setConfirmDeploy(false)
    try {
      const result = await syncToGateway.mutateAsync()
      if (result.status === 'ok') {
        toast('success', `Deployed ${result.servers_synced} server(s) to Agent Gateway`)
      } else if (result.status === 'partial') {
        toast('error', `ConfigMap updated but restart failed: ${result.restart.message}`)
      } else {
        toast('error', `Deploy failed: ${result.configmap.message}`)
      }
    } catch {
      toast('error', 'Failed to deploy to Agent Gateway')
    }
  }

  const activeCount = agents?.filter(a => a.is_active).length ?? 0

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">A2A Agents</h1>
          <p className="text-gray-600">
            Configure Agent-to-Agent protocol agents
          </p>
        </div>
        <div className="flex items-center gap-3">
          <button onClick={handleTogglePreview} className="btn btn-secondary">
            <EyeIcon className="w-5 h-5 mr-2" />
            {showPreview ? 'Hide Preview' : 'Preview Config'}
          </button>
          <button
            onClick={() => setConfirmDeploy(true)}
            className="btn bg-indigo-600 text-white hover:bg-indigo-700"
            disabled={syncToGateway.isPending}
          >
            <RocketLaunchIcon className="w-5 h-5 mr-2" />
            Deploy to Gateway
            {activeCount > 0 && (
              <span className="ml-2 inline-flex items-center justify-center px-2 py-0.5 rounded-full text-xs font-medium bg-indigo-400 text-white">
                {activeCount}
              </span>
            )}
          </button>
          <button onClick={() => { resetForm(); setShowForm(true) }} className="btn btn-primary">
            <PlusIcon className="w-5 h-5 mr-2" />
            Add Agent
          </button>
        </div>
      </div>

      {/* Deploy Confirmation Dialog */}
      {confirmDeploy && (
        <div className="card border-2 border-indigo-200 bg-indigo-50">
          <h3 className="font-semibold text-indigo-900 mb-2">Deploy to Agent Gateway</h3>
          <p className="text-sm text-indigo-800">
            This will push all active MCP servers and A2A agents to the Agent Gateway config
            and trigger a hot-reload. Existing connections will drain gracefully.
          </p>
          <div className="flex space-x-3 mt-3">
            <button
              onClick={handleDeploy}
              className="btn bg-indigo-600 text-white hover:bg-indigo-700"
              disabled={syncToGateway.isPending}
            >
              {syncToGateway.isPending ? 'Deploying...' : 'Deploy'}
            </button>
            <button onClick={() => setConfirmDeploy(false)} className="btn btn-secondary">
              Cancel
            </button>
          </div>
        </div>
      )}

      {/* Config Preview Panel */}
      {showPreview && (
        <div className="card">
          <h3 className="font-semibold mb-2">Agent Gateway Config Preview</h3>
          {isLoadingPreview ? (
            <p className="text-sm text-gray-500">Loading preview...</p>
          ) : preview ? (
            <>
              <p className="text-sm text-gray-600 mb-3">
                {preview.active_servers} MCP server(s) and {preview.active_agents ?? 0} A2A agent(s) will be deployed
              </p>
              <pre className="bg-gray-900 text-green-300 text-sm p-4 rounded-lg overflow-x-auto max-h-96 overflow-y-auto">
                <code>{preview.config_yaml}</code>
              </pre>
            </>
          ) : (
            <p className="text-sm text-gray-500">No preview available</p>
          )}
        </div>
      )}

      {showForm && (
        <div className="card">
          <h2 className="text-lg font-semibold mb-4">
            {editingAgent ? 'Edit A2A Agent' : 'Add A2A Agent'}
          </h2>
          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label htmlFor="agent-name" className="label">Name</label>
                <input
                  id="agent-name"
                  type="text"
                  value={form.name}
                  onChange={(e) => setForm({ ...form, name: e.target.value })}
                  className="input"
                  required
                  placeholder="e.g., code-reviewer"
                />
              </div>
              <div>
                <label htmlFor="agent-url" className="label">URL</label>
                <input
                  id="agent-url"
                  type="url"
                  value={form.url}
                  onChange={(e) => setForm({ ...form, url: e.target.value })}
                  className="input"
                  required
                  placeholder="http://localhost:8088"
                />
              </div>
              <div className="col-span-2">
                <label htmlFor="agent-description" className="label">Description</label>
                <input
                  id="agent-description"
                  type="text"
                  value={form.description}
                  onChange={(e) => setForm({ ...form, description: e.target.value })}
                  className="input"
                  placeholder="What does this agent do?"
                />
              </div>
              <div className="col-span-2">
                <label htmlFor="agent-skills" className="label">Skills (comma-separated)</label>
                <input
                  id="agent-skills"
                  type="text"
                  value={form.skills}
                  onChange={(e) => setForm({ ...form, skills: e.target.value })}
                  className="input"
                  placeholder="code-review, testing, documentation"
                />
              </div>
            </div>
            <div className="flex space-x-3">
              <button
                type="submit"
                className="btn btn-primary"
                disabled={createAgent.isPending || updateAgent.isPending}
              >
                {editingAgent ? 'Update Agent' : 'Add Agent'}
              </button>
              <button
                type="button"
                onClick={resetForm}
                className="btn btn-secondary"
              >
                Cancel
              </button>
            </div>
          </form>
        </div>
      )}

      {/* Confirm Delete */}
      {confirmDelete && (
        <div className="card border-2 border-red-200 bg-red-50">
          <p className="text-sm text-red-800">
            Are you sure you want to delete this A2A agent? This action cannot be undone.
          </p>
          <div className="flex space-x-3 mt-3">
            <button
              onClick={() => handleDelete(confirmDelete)}
              className="btn bg-red-600 text-white hover:bg-red-700"
              disabled={deleteAgent.isPending}
            >
              {deleteAgent.isPending ? 'Deleting...' : 'Delete Agent'}
            </button>
            <button onClick={() => setConfirmDelete(null)} className="btn btn-secondary">
              Cancel
            </button>
          </div>
        </div>
      )}

      {(!agents || agents.length === 0) ? (
        <EmptyState
          icon={CpuChipIcon}
          title="No A2A agents configured"
          description="Add A2A agents to enable agent-to-agent communication through your gateway."
          actionLabel="Add Agent"
          onAction={() => setShowForm(true)}
        />
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {agents.map((agent) => (
            <div key={agent.id} className="card">
              <div className="flex items-start justify-between mb-4">
                <div className="flex items-center">
                  <div className="p-2 bg-gray-100 rounded-lg mr-3">
                    <CpuChipIcon className="w-5 h-5 text-gray-600" />
                  </div>
                  <div>
                    <h3 className="font-semibold">{agent.name}</h3>
                    {agent.description && (
                      <p className="text-sm text-gray-500">{agent.description}</p>
                    )}
                  </div>
                </div>
                <button
                  onClick={() => handleToggleActive(agent)}
                  className={`px-2 py-1 rounded text-xs cursor-pointer transition-colors ${
                    agent.is_active
                      ? 'bg-green-100 text-green-700 hover:bg-green-200'
                      : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                  }`}
                >
                  {agent.is_active ? 'Active' : 'Inactive'}
                </button>
              </div>

              <div className="mb-3">
                <p className="text-xs text-gray-500 mb-1">URL:</p>
                <code className="text-xs bg-gray-100 p-2 rounded block">
                  {agent.url}
                </code>
              </div>

              {agent.skills && agent.skills.length > 0 && (
                <div className="mb-3">
                  <p className="text-xs text-gray-500 mb-1">Skills:</p>
                  <div className="flex flex-wrap gap-1">
                    {agent.skills.map((skill: string) => (
                      <span
                        key={skill}
                        className="px-2 py-1 bg-purple-100 text-purple-700 rounded text-xs"
                      >
                        {skill}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              <div className="flex gap-2 mt-4 pt-3 border-t border-gray-100">
                <button
                  onClick={() => handleTest(agent.id)}
                  disabled={testingId === agent.id}
                  className="btn btn-secondary text-xs flex-1"
                >
                  <SignalIcon className="w-3.5 h-3.5 mr-1" />
                  {testingId === agent.id ? 'Testing...' : 'Test'}
                </button>
                <button
                  onClick={() => openEditForm(agent)}
                  className="btn btn-secondary text-xs flex-1"
                >
                  <PencilIcon className="w-3.5 h-3.5 mr-1" />
                  Edit
                </button>
                <button
                  onClick={() => setConfirmDelete(agent.id)}
                  className="btn btn-secondary text-xs text-red-600 hover:text-red-800 flex-1"
                >
                  <TrashIcon className="w-3.5 h-3.5 mr-1" />
                  Delete
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
