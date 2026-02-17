import { useState } from 'react'
import { useAPIKeys, useGenerateKey, useDeleteKey } from '../api/hooks'
import { KeyIcon, PlusIcon, ClipboardDocumentIcon, TrashIcon } from '@heroicons/react/24/outline'
import { SkeletonCard } from '../components/Skeleton'
import EmptyState from '../components/EmptyState'
import { useToast } from '../components/Toast'

interface KeyRow {
  token: string
  key_alias: string | null
  key_name: string | null
  spend: number
  max_budget: number | null
  models: string[] | null
  team_id: string | null
  expires: string | null
  created_at: string | null
}

export default function APIKeys() {
  const { data: keysData, isLoading, error } = useAPIKeys()
  const generateKey = useGenerateKey()
  const deleteKey = useDeleteKey()
  const toast = useToast()

  const [showGenerate, setShowGenerate] = useState(false)
  const [generatedKey, setGeneratedKey] = useState<string | null>(null)
  const [confirmRevoke, setConfirmRevoke] = useState<string | null>(null)
  const [form, setForm] = useState({
    key_alias: '',
    max_budget: '',
    models: '',
    team_id: '',
    duration: '',
  })

  // LiteLLM /key/list returns { keys: [...] } or just an array
  const keys: KeyRow[] = Array.isArray(keysData)
    ? keysData
    : (keysData as { keys?: KeyRow[] })?.keys || []

  const handleGenerate = async (e: React.FormEvent) => {
    e.preventDefault()
    try {
      const result = await generateKey.mutateAsync({
        key_alias: form.key_alias || undefined,
        max_budget: form.max_budget ? parseFloat(form.max_budget) : undefined,
        models: form.models ? form.models.split(',').map((m) => m.trim()).filter(Boolean) : undefined,
        team_id: form.team_id || undefined,
        duration: form.duration || undefined,
      })
      setGeneratedKey(result.key)
      setShowGenerate(false)
      setForm({ key_alias: '', max_budget: '', models: '', team_id: '', duration: '' })
      toast('success', 'API key generated')
    } catch {
      toast('error', 'Failed to generate API key')
    }
  }

  const handleRevoke = async (token: string) => {
    try {
      await deleteKey.mutateAsync({ keys: [token] })
      setConfirmRevoke(null)
      toast('success', 'API key revoked')
    } catch {
      toast('error', 'Failed to revoke API key')
    }
  }

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text)
    toast('success', 'Copied to clipboard')
  }

  const maskKey = (token: string) => {
    if (!token) return '—'
    if (token.length <= 8) return token
    return token.slice(0, 6) + '...' + token.slice(-4)
  }

  if (isLoading) {
    return (
      <div className="space-y-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">API Keys</h1>
          <p className="text-gray-600">Manage API keys for LLM access</p>
        </div>
        <div className="grid grid-cols-1 gap-4">
          {Array.from({ length: 3 }).map((_, i) => <SkeletonCard key={i} />)}
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="space-y-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">API Keys</h1>
          <p className="text-gray-600">Manage API keys for LLM access</p>
        </div>
        <div className="bg-red-50 text-red-700 p-4 rounded-lg">
          Failed to load API keys. Ensure LiteLLM is running.
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">API Keys</h1>
          <p className="text-gray-600">Manage API keys for LLM access</p>
        </div>
        <button onClick={() => setShowGenerate(true)} className="btn btn-primary">
          <PlusIcon className="w-5 h-5 mr-2" />
          Generate Key
        </button>
      </div>

      {/* Generated Key Display */}
      {generatedKey && (
        <div className="card border-2 border-green-200 bg-green-50">
          <div className="flex items-start justify-between">
            <div>
              <h3 className="font-semibold text-green-800">New API Key Generated</h3>
              <p className="text-sm text-green-700 mt-1">
                Copy this key now. You won't be able to see it again.
              </p>
            </div>
            <button onClick={() => setGeneratedKey(null)} className="text-green-600 hover:text-green-800 text-sm">
              Dismiss
            </button>
          </div>
          <div className="mt-3 flex items-center gap-2">
            <code className="flex-1 bg-white px-3 py-2 rounded border border-green-200 text-sm font-mono break-all">
              {generatedKey}
            </code>
            <button
              onClick={() => copyToClipboard(generatedKey)}
              className="btn btn-secondary flex-shrink-0"
            >
              <ClipboardDocumentIcon className="w-4 h-4 mr-1" />
              Copy
            </button>
          </div>
        </div>
      )}

      {/* Generate Key Form */}
      {showGenerate && (
        <div className="card">
          <h2 className="text-lg font-semibold mb-4">Generate New API Key</h2>
          <form onSubmit={handleGenerate} className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label htmlFor="key-alias" className="label">Key Alias</label>
                <input
                  id="key-alias"
                  type="text"
                  value={form.key_alias}
                  onChange={(e) => setForm({ ...form, key_alias: e.target.value })}
                  className="input"
                  placeholder="e.g., production-backend"
                />
              </div>
              <div>
                <label htmlFor="key-max-budget" className="label">Max Budget ($)</label>
                <input
                  id="key-max-budget"
                  type="number"
                  step="0.01"
                  min="0"
                  value={form.max_budget}
                  onChange={(e) => setForm({ ...form, max_budget: e.target.value })}
                  className="input"
                  placeholder="e.g., 100.00"
                />
              </div>
              <div>
                <label htmlFor="key-models" className="label">Models (comma-separated)</label>
                <input
                  id="key-models"
                  type="text"
                  value={form.models}
                  onChange={(e) => setForm({ ...form, models: e.target.value })}
                  className="input"
                  placeholder="e.g., gpt-4o, claude-sonnet-4-5-20250929"
                />
              </div>
              <div>
                <label htmlFor="key-team-id" className="label">Team ID</label>
                <input
                  id="key-team-id"
                  type="text"
                  value={form.team_id}
                  onChange={(e) => setForm({ ...form, team_id: e.target.value })}
                  className="input"
                  placeholder="Optional team ID"
                />
              </div>
              <div className="col-span-2">
                <label htmlFor="key-duration" className="label">Duration</label>
                <input
                  id="key-duration"
                  type="text"
                  value={form.duration}
                  onChange={(e) => setForm({ ...form, duration: e.target.value })}
                  className="input"
                  placeholder="e.g., 30d, 1h, 365d (leave empty for no expiry)"
                />
              </div>
            </div>
            <div className="flex space-x-3">
              <button type="submit" className="btn btn-primary" disabled={generateKey.isPending}>
                {generateKey.isPending ? 'Generating...' : 'Generate Key'}
              </button>
              <button type="button" onClick={() => setShowGenerate(false)} className="btn btn-secondary">
                Cancel
              </button>
            </div>
          </form>
        </div>
      )}

      {/* Confirm Revoke Dialog */}
      {confirmRevoke && (
        <div className="card border-2 border-red-200 bg-red-50">
          <p className="text-sm text-red-800">
            Are you sure you want to revoke this key? This action cannot be undone.
          </p>
          <div className="flex space-x-3 mt-3">
            <button
              onClick={() => handleRevoke(confirmRevoke)}
              className="btn bg-red-600 text-white hover:bg-red-700"
              disabled={deleteKey.isPending}
            >
              {deleteKey.isPending ? 'Revoking...' : 'Revoke Key'}
            </button>
            <button onClick={() => setConfirmRevoke(null)} className="btn btn-secondary">
              Cancel
            </button>
          </div>
        </div>
      )}

      {/* Keys Table */}
      {keys.length === 0 ? (
        <EmptyState
          icon={KeyIcon}
          title="No API keys"
          description="Generate an API key to start making requests through the gateway."
          actionLabel="Generate Key"
          onAction={() => setShowGenerate(true)}
        />
      ) : (
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Alias</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Key</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Spend / Budget</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Models</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Team</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Expires</th>
                <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">Actions</th>
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-200">
              {keys.map((key, idx) => (
                <tr key={key.token || idx} className="hover:bg-gray-50">
                  <td className="px-4 py-3 text-sm font-medium text-gray-900">
                    {key.key_alias || key.key_name || '—'}
                  </td>
                  <td className="px-4 py-3">
                    <code className="text-xs bg-gray-100 px-2 py-1 rounded font-mono">
                      {maskKey(key.token)}
                    </code>
                  </td>
                  <td className="px-4 py-3 text-sm text-gray-600">
                    ${(key.spend || 0).toFixed(2)}
                    {key.max_budget != null && (
                      <span className="text-gray-400"> / ${key.max_budget.toFixed(2)}</span>
                    )}
                  </td>
                  <td className="px-4 py-3">
                    {key.models && key.models.length > 0 ? (
                      <div className="flex flex-wrap gap-1">
                        {key.models.slice(0, 3).map((m) => (
                          <span key={m} className="px-1.5 py-0.5 bg-blue-100 text-blue-700 rounded text-xs">
                            {m}
                          </span>
                        ))}
                        {key.models.length > 3 && (
                          <span className="text-xs text-gray-500">+{key.models.length - 3}</span>
                        )}
                      </div>
                    ) : (
                      <span className="text-xs text-gray-400">All models</span>
                    )}
                  </td>
                  <td className="px-4 py-3 text-sm text-gray-600">
                    {key.team_id || '—'}
                  </td>
                  <td className="px-4 py-3 text-sm text-gray-600">
                    {key.expires
                      ? new Date(key.expires).toLocaleDateString()
                      : 'Never'}
                  </td>
                  <td className="px-4 py-3 text-right">
                    <button
                      onClick={() => setConfirmRevoke(key.token)}
                      className="text-red-600 hover:text-red-800 p-1"
                      aria-label={`Revoke key ${key.key_alias || key.key_name || ''}`}
                    >
                      <TrashIcon className="w-4 h-4" />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
