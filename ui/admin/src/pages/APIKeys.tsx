import { useState } from 'react'
import { useAPIKeys, useGenerateKey, useDeleteKey } from '../api/hooks'
import { PlusIcon, KeyIcon, TrashIcon, ClipboardDocumentIcon } from '@heroicons/react/24/outline'
import { SkeletonCard } from '../components/Skeleton'
import EmptyState from '../components/EmptyState'
import ConfirmDialog from '../components/ConfirmDialog'
import { useToast } from '../components/Toast'

function maskToken(token: string): string {
  if (!token || token.length < 12) return token
  return token.slice(0, 8) + '...' + token.slice(-4)
}

export default function APIKeys() {
  const { data: keys, isLoading, error } = useAPIKeys()
  const generateKey = useGenerateKey()
  const deleteKey = useDeleteKey()
  const toast = useToast()

  const [showForm, setShowForm] = useState(false)
  const [revokeToken, setRevokeToken] = useState<string | null>(null)
  const [newKey, setNewKey] = useState<string | null>(null)
  const [form, setForm] = useState({
    key_alias: '',
    max_budget: '',
    models: '',
    team_id: '',
    duration: '',
  })

  const resetForm = () => {
    setForm({ key_alias: '', max_budget: '', models: '', team_id: '', duration: '' })
    setShowForm(false)
  }

  if (isLoading) {
    return (
      <div className="space-y-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">API Keys</h1>
          <p className="text-gray-600">Manage API keys for LLM access</p>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {Array.from({ length: 3 }).map((_, i) => <SkeletonCard key={i} />)}
        </div>
      </div>
    )
  }

  if (error) {
    return <div className="bg-red-50 text-red-700 p-4 rounded-lg">Failed to load API keys</div>
  }

  const handleGenerate = async (e: React.FormEvent) => {
    e.preventDefault()
    try {
      const payload: Record<string, unknown> = {}
      if (form.key_alias) payload.key_alias = form.key_alias
      if (form.max_budget) payload.max_budget = parseFloat(form.max_budget)
      if (form.models) payload.models = form.models.split(',').map((m) => m.trim())
      if (form.team_id) payload.team_id = form.team_id
      if (form.duration) payload.duration = form.duration
      const result = await generateKey.mutateAsync(payload)
      setNewKey(result.key)
      toast('success', 'API key generated')
      resetForm()
    } catch {
      toast('error', 'Failed to generate API key')
    }
  }

  const handleRevoke = async () => {
    if (!revokeToken) return
    try {
      await deleteKey.mutateAsync([revokeToken])
      toast('success', 'API key revoked')
    } catch {
      toast('error', 'Failed to revoke API key')
    }
    setRevokeToken(null)
  }

  const handleCopy = async (text: string) => {
    try {
      await navigator.clipboard.writeText(text)
      toast('success', 'Copied to clipboard')
    } catch {
      toast('error', 'Failed to copy')
    }
  }

  const keyList = Array.isArray(keys) ? keys : []

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">API Keys</h1>
          <p className="text-gray-600">
            {keyList.length} key{keyList.length !== 1 ? 's' : ''} active
          </p>
        </div>
        <button onClick={() => setShowForm(true)} className="btn btn-primary">
          <PlusIcon className="w-5 h-5 mr-2" />
          Generate Key
        </button>
      </div>

      <ConfirmDialog
        isOpen={!!revokeToken}
        onClose={() => setRevokeToken(null)}
        onConfirm={handleRevoke}
        title="Revoke API Key?"
        message="This key will immediately stop working. This action cannot be undone."
        confirmLabel="Revoke Key"
        confirmVariant="danger"
      />

      {/* New key alert */}
      {newKey && (
        <div className="card border-2 border-green-200 bg-green-50">
          <h3 className="font-semibold text-green-900 mb-2">New API Key Generated</h3>
          <p className="text-sm text-green-800 mb-3">
            Copy this key now — it will not be shown again.
          </p>
          <div className="flex items-center gap-2">
            <code className="flex-1 bg-white border border-green-300 rounded px-3 py-2 text-sm font-mono break-all">
              {newKey}
            </code>
            <button
              onClick={() => handleCopy(newKey)}
              className="btn btn-secondary"
              title="Copy to clipboard"
            >
              <ClipboardDocumentIcon className="w-5 h-5" />
            </button>
          </div>
          <button
            onClick={() => setNewKey(null)}
            className="mt-3 text-sm text-green-700 hover:text-green-900"
          >
            Dismiss
          </button>
        </div>
      )}

      {showForm && (
        <div className="card">
          <h2 className="text-lg font-semibold mb-4">Generate API Key</h2>
          <form onSubmit={handleGenerate} className="space-y-4">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label htmlFor="key-alias" className="label">Key Alias</label>
                <input
                  id="key-alias"
                  type="text"
                  value={form.key_alias}
                  onChange={(e) => setForm({ ...form, key_alias: e.target.value })}
                  className="input"
                  placeholder="e.g., my-app-key"
                />
              </div>
              <div>
                <label htmlFor="key-budget" className="label">Max Budget ($)</label>
                <input
                  id="key-budget"
                  type="number"
                  step="0.01"
                  min="0"
                  value={form.max_budget}
                  onChange={(e) => setForm({ ...form, max_budget: e.target.value })}
                  className="input"
                  placeholder="e.g., 100"
                />
              </div>
              <div>
                <label htmlFor="key-models" className="label">Allowed Models (comma-separated)</label>
                <input
                  id="key-models"
                  type="text"
                  value={form.models}
                  onChange={(e) => setForm({ ...form, models: e.target.value })}
                  className="input"
                  placeholder="e.g., gpt-4o, claude-3.5-sonnet"
                />
              </div>
              <div>
                <label htmlFor="key-team" className="label">Team ID</label>
                <input
                  id="key-team"
                  type="text"
                  value={form.team_id}
                  onChange={(e) => setForm({ ...form, team_id: e.target.value })}
                  className="input"
                  placeholder="Optional team ID"
                />
              </div>
              <div>
                <label htmlFor="key-duration" className="label">Duration</label>
                <input
                  id="key-duration"
                  type="text"
                  value={form.duration}
                  onChange={(e) => setForm({ ...form, duration: e.target.value })}
                  className="input"
                  placeholder="e.g., 30d, 24h"
                />
              </div>
            </div>
            <div className="flex space-x-3">
              <button type="submit" className="btn btn-primary" disabled={generateKey.isPending}>
                {generateKey.isPending ? 'Generating...' : 'Generate Key'}
              </button>
              <button type="button" onClick={resetForm} className="btn btn-secondary">
                Cancel
              </button>
            </div>
          </form>
        </div>
      )}

      {keyList.length === 0 ? (
        <EmptyState
          icon={KeyIcon}
          title="No API keys"
          description="Generate API keys to authenticate LLM requests through the gateway."
          actionLabel="Generate Key"
          onAction={() => setShowForm(true)}
        />
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {keyList.map((key) => (
            <div key={key.token} className="card">
              <div className="flex items-start justify-between mb-3">
                <div className="flex items-center">
                  <div className="p-2 bg-amber-100 rounded-lg mr-3">
                    <KeyIcon className="w-5 h-5 text-amber-600" />
                  </div>
                  <div>
                    <h3 className="font-semibold">{key.key_alias || key.key_name || 'Unnamed key'}</h3>
                    <code className="text-xs text-gray-500">{maskToken(key.token)}</code>
                  </div>
                </div>
              </div>

              <div className="space-y-2 text-sm">
                <div className="flex justify-between">
                  <span className="text-gray-500">Spend</span>
                  <span className="font-medium">${(key.spend || 0).toFixed(4)}</span>
                </div>
                {key.max_budget !== null && key.max_budget !== undefined && (
                  <div className="flex justify-between">
                    <span className="text-gray-500">Budget</span>
                    <span className="font-medium">${key.max_budget.toFixed(2)}</span>
                  </div>
                )}
                {key.models && key.models.length > 0 && (
                  <div>
                    <span className="text-gray-500 text-xs">Models:</span>
                    <div className="flex flex-wrap gap-1 mt-1">
                      {key.models.map((m) => (
                        <span key={m} className="px-2 py-0.5 bg-blue-100 text-blue-700 rounded text-xs">{m}</span>
                      ))}
                    </div>
                  </div>
                )}
                {key.team_id && (
                  <div className="flex justify-between">
                    <span className="text-gray-500">Team</span>
                    <span className="text-xs">{key.team_id}</span>
                  </div>
                )}
                {key.expires && (
                  <div className="flex justify-between">
                    <span className="text-gray-500">Expires</span>
                    <span className="text-xs">{new Date(key.expires).toLocaleDateString()}</span>
                  </div>
                )}
              </div>

              <div className="mt-4 pt-3 border-t border-gray-100">
                <button
                  onClick={() => setRevokeToken(key.token)}
                  className="btn btn-secondary text-xs text-red-600 hover:text-red-800 w-full"
                >
                  <TrashIcon className="w-3.5 h-3.5 mr-1" />
                  Revoke
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
