import { useState } from 'react'
import { useMCPServers, useCreateMCPServer } from '../api/hooks'
import { PlusIcon, ServerIcon } from '@heroicons/react/24/outline'

export default function MCPServers() {
  const { data: servers, isLoading, error } = useMCPServers()
  const createServer = useCreateMCPServer()
  const [showForm, setShowForm] = useState(false)
  const [form, setForm] = useState({
    name: '',
    server_type: 'stdio',
    command: '',
    url: '',
    args: '',
    env: '',
  })

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-t-2 border-b-2 border-primary-600"></div>
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
    await createServer.mutateAsync({
      name: form.name,
      server_type: form.server_type,
      command: form.command || undefined,
      url: form.url || undefined,
      args: form.args ? form.args.split(' ') : [],
      env: form.env ? JSON.parse(form.env) : {},
    })
    setShowForm(false)
    setForm({
      name: '',
      server_type: 'stdio',
      command: '',
      url: '',
      args: '',
      env: '',
    })
  }

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">MCP Servers</h1>
          <p className="text-gray-600">
            Configure Model Context Protocol servers
          </p>
        </div>
        <button onClick={() => setShowForm(true)} className="btn btn-primary">
          <PlusIcon className="w-5 h-5 mr-2" />
          Add Server
        </button>
      </div>

      {showForm && (
        <div className="card">
          <h2 className="text-lg font-semibold mb-4">Add MCP Server</h2>
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
              <button type="submit" className="btn btn-primary">
                Add Server
              </button>
              <button
                type="button"
                onClick={() => setShowForm(false)}
                className="btn btn-secondary"
              >
                Cancel
              </button>
            </div>
          </form>
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {servers?.map((server: any) => (
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
              <span
                className={`px-2 py-1 rounded text-xs ${
                  server.is_active
                    ? 'bg-green-100 text-green-700'
                    : 'bg-gray-100 text-gray-700'
                }`}
              >
                {server.is_active ? 'Active' : 'Inactive'}
              </span>
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
              <div>
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
          </div>
        ))}
      </div>

      {(!servers || servers.length === 0) && (
        <div className="text-center py-12 text-gray-500">
          No MCP servers configured yet
        </div>
      )}
    </div>
  )
}
