import { useState } from 'react'
import { useMCPServers, useCreateMCPServer, useUpdateMCPServer, useDeleteMCPServer, useTestMCPServer, useSyncMCPToGateway, useGatewayConfigPreview } from '../api/hooks'
import { PlusIcon, ServerIcon, PencilIcon, TrashIcon, SignalIcon, RocketLaunchIcon, EyeIcon } from '@heroicons/react/24/outline'
import { SkeletonCard } from '../components/Skeleton'
import EmptyState from '../components/EmptyState'
import { useToast } from '../components/Toast'
import type { MCPServerConfig } from '../types'

export default function MCPServers() {
  const { data: servers, isLoading, error } = useMCPServers()
  const createServer = useCreateMCPServer()
  const updateServer = useUpdateMCPServer()
  const deleteServer = useDeleteMCPServer()
  const testServer = useTestMCPServer()
  const syncToGateway = useSyncMCPToGateway()
  const { data: preview, refetch: fetchPreview, isFetching: isLoadingPreview } = useGatewayConfigPreview()
  const toast = useToast()

  const [showForm, setShowForm] = useState(false)
  const [editingServer, setEditingServer] = useState<MCPServerConfig | null>(null)
  const [confirmDelete, setConfirmDelete] = useState<string | null>(null)
  const [testingId, setTestingId] = useState<string | null>(null)
  const [showPreview, setShowPreview] = useState(false)
  const [confirmDeploy, setConfirmDeploy] = useState(false)
  const [form, setForm] = useState({
    name: '',
    server_type: 'stdio',
    command: '',
    url: '',
    args: '',
    env: '',
  })

  const resetForm = () => {
    setForm({ name: '', server_type: 'stdio', command: '', url: '', args: '', env: '' })
    setEditingServer(null)
    setShowForm(false)
  }

  const openEditForm = (server: MCPServerConfig) => {
    setEditingServer(server)
    setForm({
      name: server.name,
      server_type: server.server_type,
      command: server.command || '',
      url: server.url || '',
      args: server.args?.join(' ') || '',
      env: Object.keys(server.env || {}).length > 0 ? JSON.stringify(server.env) : '',
    })
    setShowForm(true)
  }

  if (isLoading) {
    return (
      <div className="space-y-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">MCP Servers</h1>
          <p className="text-gray-600">Configure Model Context Protocol servers</p>
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
        Failed to load MCP servers
      </div>
    )
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    const payload = {
      name: form.name,
      server_type: form.server_type,
      command: form.command || undefined,
      url: form.url || undefined,
      args: form.args ? form.args.split(' ') : [],
      env: form.env ? JSON.parse(form.env) : {},
    }

    try {
      if (editingServer) {
        await updateServer.mutateAsync({ id: editingServer.id, data: payload })
        toast('success', 'MCP server updated')
      } else {
        await createServer.mutateAsync(payload)
        toast('success', 'MCP server added')
      }
      resetForm()
    } catch {
      toast('error', editingServer ? 'Failed to update MCP server' : 'Failed to add MCP server')
    }
  }

  const handleDelete = async (id: string) => {
    try {
      await deleteServer.mutateAsync(id)
      setConfirmDelete(null)
      toast('success', 'MCP server deleted')
    } catch {
      toast('error', 'Failed to delete MCP server')
    }
  }

  const handleTest = async (id: string) => {
    setTestingId(id)
    try {
      const result = await testServer.mutateAsync(id)
      if (result.status === 'ok') {
        toast('success', `Connection OK: ${result.message}`)
      } else {
        toast('error', `Connection failed: ${result.message}`)
      }
    } catch {
      toast('error', 'Failed to test MCP server')
    } finally {
      setTestingId(null)
    }
  }

  const handleToggleActive = async (server: MCPServerConfig) => {
    try {
      await updateServer.mutateAsync({
        id: server.id,
        data: { is_active: !server.is_active },
      })
      toast('success', `Server ${server.is_active ? 'deactivated' : 'activated'}`)
    } catch {
      toast('error', 'Failed to update server status')
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

  const activeCount = servers?.filter(s => s.is_active).length ?? 0

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">MCP Servers</h1>
          <p className="text-gray-600">
            Configure Model Context Protocol servers
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
            disabled={syncToGateway.isPending || activeCount === 0}
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
            Add Server
          </button>
        </div>
      </div>

      {/* Deploy Confirmation Dialog */}
      {confirmDeploy && (
        <div className="card border-2 border-indigo-200 bg-indigo-50">
          <h3 className="font-semibold text-indigo-900 mb-2">Deploy to Agent Gateway</h3>
          <p className="text-sm text-indigo-800">
            This will push <strong>{activeCount} active server(s)</strong> to the Agent Gateway ConfigMap
            and trigger a rolling restart. Existing connections will drain gracefully.
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
                {preview.active_servers} active server(s) will be deployed
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
            {editingServer ? 'Edit MCP Server' : 'Add MCP Server'}
          </h2>
          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="label">Name</label>
                <input
                  type="text"
                  value={form.name}
                  onChange={(e) => setForm({ ...form, name: e.target.value })}
                  className="input"
                  required
                  placeholder="e.g., filesystem"
                />
              </div>
              <div>
                <label className="label">Server Type</label>
                <select
                  value={form.server_type}
                  onChange={(e) =>
                    setForm({ ...form, server_type: e.target.value })
                  }
                  className="input"
                >
                  <option value="stdio">stdio</option>
                  <option value="http">http</option>
                </select>
              </div>
              {form.server_type === 'stdio' && (
                <>
                  <div className="col-span-2">
                    <label className="label">Command</label>
                    <input
                      type="text"
                      value={form.command}
                      onChange={(e) =>
                        setForm({ ...form, command: e.target.value })
                      }
                      className="input"
                      placeholder="e.g., npx -y @modelcontextprotocol/server-filesystem"
                    />
                  </div>
                  <div className="col-span-2">
                    <label className="label">Arguments (space separated)</label>
                    <input
                      type="text"
                      value={form.args}
                      onChange={(e) =>
                        setForm({ ...form, args: e.target.value })
                      }
                      className="input"
                      placeholder="e.g., /workspace"
                    />
                  </div>
                </>
              )}
              {form.server_type === 'http' && (
                <div className="col-span-2">
                  <label className="label">URL</label>
                  <input
                    type="url"
                    value={form.url}
                    onChange={(e) => setForm({ ...form, url: e.target.value })}
                    className="input"
                    placeholder="http://localhost:3001"
                  />
                </div>
              )}
              <div className="col-span-2">
                <label className="label">Environment Variables (JSON)</label>
                <textarea
                  value={form.env}
                  onChange={(e) => setForm({ ...form, env: e.target.value })}
                  className="input font-mono text-sm"
                  rows={3}
                  placeholder='{"API_KEY": "..."}'
                />
              </div>
            </div>
            <div className="flex space-x-3">
              <button
                type="submit"
                className="btn btn-primary"
                disabled={createServer.isPending || updateServer.isPending}
              >
                {editingServer ? 'Update Server' : 'Add Server'}
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
            Are you sure you want to delete this MCP server? This action cannot be undone.
          </p>
          <div className="flex space-x-3 mt-3">
            <button
              onClick={() => handleDelete(confirmDelete)}
              className="btn bg-red-600 text-white hover:bg-red-700"
              disabled={deleteServer.isPending}
            >
              {deleteServer.isPending ? 'Deleting...' : 'Delete Server'}
            </button>
            <button onClick={() => setConfirmDelete(null)} className="btn btn-secondary">
              Cancel
            </button>
          </div>
        </div>
      )}

      {(!servers || servers.length === 0) ? (
        <EmptyState
          icon={ServerIcon}
          title="No MCP servers configured"
          description="Add MCP servers to extend your gateway with tools and context."
          actionLabel="Add Server"
          onAction={() => setShowForm(true)}
        />
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {servers.map((server) => (
            <div key={server.id} className="card">
              <div className="flex items-start justify-between mb-4">
                <div className="flex items-center">
                  <div className="p-2 bg-gray-100 rounded-lg mr-3">
                    <ServerIcon className="w-5 h-5 text-gray-600" />
                  </div>
                  <div>
                    <h3 className="font-semibold">{server.name}</h3>
                    <p className="text-sm text-gray-500">{server.server_type}</p>
                  </div>
                </div>
                <button
                  onClick={() => handleToggleActive(server)}
                  className={`px-2 py-1 rounded text-xs cursor-pointer transition-colors ${
                    server.is_active
                      ? 'bg-green-100 text-green-700 hover:bg-green-200'
                      : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                  }`}
                >
                  {server.is_active ? 'Active' : 'Inactive'}
                </button>
              </div>

              {server.command && (
                <div className="mb-3">
                  <p className="text-xs text-gray-500 mb-1">Command:</p>
                  <code className="text-xs bg-gray-100 p-2 rounded block overflow-x-auto">
                    {server.command}
                  </code>
                </div>
              )}

              {server.url && (
                <div className="mb-3">
                  <p className="text-xs text-gray-500 mb-1">URL:</p>
                  <code className="text-xs bg-gray-100 p-2 rounded block">
                    {server.url}
                  </code>
                </div>
              )}

              {server.args && server.args.length > 0 && (
                <div className="mb-3">
                  <p className="text-xs text-gray-500 mb-1">Arguments:</p>
                  <code className="text-xs bg-gray-100 p-2 rounded block">
                    {server.args.join(' ')}
                  </code>
                </div>
              )}

              {server.tools && server.tools.length > 0 && (
                <div className="mb-3">
                  <p className="text-xs text-gray-500 mb-1">Tools:</p>
                  <div className="flex flex-wrap gap-1">
                    {server.tools.map((tool: string) => (
                      <span
                        key={tool}
                        className="px-2 py-1 bg-blue-100 text-blue-700 rounded text-xs"
                      >
                        {tool}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              <div className="flex gap-2 mt-4 pt-3 border-t border-gray-100">
                <button
                  onClick={() => handleTest(server.id)}
                  disabled={testingId === server.id}
                  className="btn btn-secondary text-xs flex-1"
                >
                  <SignalIcon className="w-3.5 h-3.5 mr-1" />
                  {testingId === server.id ? 'Testing...' : 'Test'}
                </button>
                <button
                  onClick={() => openEditForm(server)}
                  className="btn btn-secondary text-xs flex-1"
                >
                  <PencilIcon className="w-3.5 h-3.5 mr-1" />
                  Edit
                </button>
                <button
                  onClick={() => setConfirmDelete(server.id)}
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
