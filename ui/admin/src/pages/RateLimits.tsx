import { useState } from 'react'
import {
  useRateLimitPolicies,
  useCreateRateLimitPolicy,
  useDeleteRateLimitPolicy,
  useRateLimitEvents,
} from '../api/hooks'
import type { RateLimitPolicyCreate } from '../types'
import { PlusIcon, TrashIcon, PencilSquareIcon } from '@heroicons/react/24/outline'
import { SkeletonCard } from '../components/Skeleton'
import { useToast } from '../components/Toast'
import { rateLimitsApi } from '../api/client'

const scopeLabels: Record<string, string> = {
  user: 'User',
  team: 'Team',
  model: 'Model',
  user_model: 'User + Model',
  team_model: 'Team + Model',
  global: 'Global',
}

export default function RateLimits() {
  const toast = useToast()
  const [showCreate, setShowCreate] = useState(false)
  const [showEvents, setShowEvents] = useState(false)
  const [editId, setEditId] = useState<string | null>(null)

  const { data: policies, isLoading, error } = useRateLimitPolicies()
  const { data: events } = useRateLimitEvents({ limit: 50 })
  const createMutation = useCreateRateLimitPolicy()
  const deleteMutation = useDeleteRateLimitPolicy()

  const [form, setForm] = useState<RateLimitPolicyCreate>({
    name: '',
    scope: 'user',
    scope_value: '',
    rpm_limit: undefined,
    tpm_limit: undefined,
    rpd_limit: undefined,
    tpd_limit: undefined,
    burst_multiplier: 1.5,
    burst_window_seconds: 10,
    priority: 0,
  })

  const handleCreate = async () => {
    try {
      const payload = { ...form }
      if (!payload.scope_value) delete (payload as Record<string, unknown>).scope_value
      await createMutation.mutateAsync(payload)
      toast('success', 'Rate limit policy created')
      setShowCreate(false)
      resetForm()
    } catch {
      toast('error', 'Failed to create rate limit policy')
    }
  }

  const handleUpdate = async () => {
    if (!editId) return
    try {
      await rateLimitsApi.update(editId, form)
      toast('success', 'Rate limit policy updated')
      setEditId(null)
      setShowCreate(false)
      resetForm()
      window.location.reload()
    } catch {
      toast('error', 'Failed to update rate limit policy')
    }
  }

  const handleDelete = async (id: string) => {
    if (!confirm('Delete this rate limit policy?')) return
    try {
      await deleteMutation.mutateAsync(id)
      toast('success', 'Policy deleted')
    } catch {
      toast('error', 'Failed to delete policy')
    }
  }

  const startEdit = (policy: { id: string; name: string; scope: string; scope_value: string | null; rpm_limit: number | null; tpm_limit: number | null; rpd_limit: number | null; tpd_limit: number | null; burst_multiplier: number; burst_window_seconds: number; priority: number }) => {
    setEditId(policy.id)
    setForm({
      name: policy.name,
      scope: policy.scope,
      scope_value: policy.scope_value || '',
      rpm_limit: policy.rpm_limit ?? undefined,
      tpm_limit: policy.tpm_limit ?? undefined,
      rpd_limit: policy.rpd_limit ?? undefined,
      tpd_limit: policy.tpd_limit ?? undefined,
      burst_multiplier: policy.burst_multiplier,
      burst_window_seconds: policy.burst_window_seconds,
      priority: policy.priority,
    })
    setShowCreate(true)
  }

  const resetForm = () => {
    setForm({
      name: '',
      scope: 'user',
      scope_value: '',
      rpm_limit: undefined,
      tpm_limit: undefined,
      rpd_limit: undefined,
      tpd_limit: undefined,
      burst_multiplier: 1.5,
      burst_window_seconds: 10,
      priority: 0,
    })
    setEditId(null)
  }

  const formatLimit = (val: number | null) => {
    if (val === null || val === undefined) return '--'
    return val.toLocaleString()
  }

  if (isLoading) {
    return (
      <div className="space-y-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Rate Limits</h1>
          <p className="text-gray-600">Granular rate limit policies</p>
        </div>
        <SkeletonCard />
      </div>
    )
  }

  if (error) {
    return <div className="bg-red-50 text-red-700 p-4 rounded-lg">Failed to load rate limit policies</div>
  }

  const policyList = Array.isArray(policies) ? policies : []
  const eventList = Array.isArray(events) ? events : []

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Rate Limits</h1>
          <p className="text-gray-600">
            {policyList.length} polic{policyList.length !== 1 ? 'ies' : 'y'}
          </p>
        </div>
        <div className="flex gap-2">
          <button onClick={() => setShowEvents(!showEvents)} className="btn btn-secondary">
            Events ({eventList.length})
          </button>
          <button onClick={() => { resetForm(); setShowCreate(true) }} className="btn btn-primary">
            <PlusIcon className="w-4 h-4 mr-1" />
            New Policy
          </button>
        </div>
      </div>

      {/* Create / Edit Modal */}
      {showCreate && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg p-6 w-full max-w-lg max-h-[90vh] overflow-y-auto">
            <h2 className="text-xl font-bold mb-4">{editId ? 'Edit' : 'Create'} Rate Limit Policy</h2>
            <div className="space-y-4">
              <div>
                <label className="label">Name</label>
                <input
                  type="text"
                  value={form.name}
                  onChange={(e) => setForm({ ...form, name: e.target.value })}
                  className="input"
                  placeholder="Policy name"
                />
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="label">Scope</label>
                  <select
                    value={form.scope}
                    onChange={(e) => setForm({ ...form, scope: e.target.value })}
                    className="input"
                  >
                    <option value="user">User</option>
                    <option value="team">Team</option>
                    <option value="model">Model</option>
                    <option value="user_model">User + Model</option>
                    <option value="team_model">Team + Model</option>
                    <option value="global">Global</option>
                  </select>
                </div>
                <div>
                  <label className="label">Scope Value</label>
                  <input
                    type="text"
                    value={form.scope_value || ''}
                    onChange={(e) => setForm({ ...form, scope_value: e.target.value })}
                    className="input"
                    placeholder="user-id or model-name"
                  />
                </div>
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="label">RPM (Requests/min)</label>
                  <input
                    type="number"
                    value={form.rpm_limit ?? ''}
                    onChange={(e) => setForm({ ...form, rpm_limit: e.target.value ? Number(e.target.value) : undefined })}
                    className="input"
                    placeholder="No limit"
                  />
                </div>
                <div>
                  <label className="label">TPM (Tokens/min)</label>
                  <input
                    type="number"
                    value={form.tpm_limit ?? ''}
                    onChange={(e) => setForm({ ...form, tpm_limit: e.target.value ? Number(e.target.value) : undefined })}
                    className="input"
                    placeholder="No limit"
                  />
                </div>
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="label">RPD (Requests/day)</label>
                  <input
                    type="number"
                    value={form.rpd_limit ?? ''}
                    onChange={(e) => setForm({ ...form, rpd_limit: e.target.value ? Number(e.target.value) : undefined })}
                    className="input"
                    placeholder="No limit"
                  />
                </div>
                <div>
                  <label className="label">TPD (Tokens/day)</label>
                  <input
                    type="number"
                    value={form.tpd_limit ?? ''}
                    onChange={(e) => setForm({ ...form, tpd_limit: e.target.value ? Number(e.target.value) : undefined })}
                    className="input"
                    placeholder="No limit"
                  />
                </div>
              </div>
              <div className="grid grid-cols-3 gap-4">
                <div>
                  <label className="label">Burst Multiplier</label>
                  <input
                    type="number"
                    step="0.1"
                    value={form.burst_multiplier ?? 1.5}
                    onChange={(e) => setForm({ ...form, burst_multiplier: Number(e.target.value) })}
                    className="input"
                  />
                </div>
                <div>
                  <label className="label">Burst Window (s)</label>
                  <input
                    type="number"
                    value={form.burst_window_seconds ?? 10}
                    onChange={(e) => setForm({ ...form, burst_window_seconds: Number(e.target.value) })}
                    className="input"
                  />
                </div>
                <div>
                  <label className="label">Priority</label>
                  <input
                    type="number"
                    value={form.priority ?? 0}
                    onChange={(e) => setForm({ ...form, priority: Number(e.target.value) })}
                    className="input"
                  />
                </div>
              </div>
              <div className="flex justify-end gap-2">
                <button onClick={() => { setShowCreate(false); resetForm() }} className="btn btn-secondary">Cancel</button>
                <button
                  onClick={editId ? handleUpdate : handleCreate}
                  className="btn btn-primary"
                  disabled={!form.name || !form.scope}
                >
                  {editId ? 'Update' : 'Create'}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Events Panel */}
      {showEvents && (
        <div className="card">
          <h3 className="text-lg font-semibold mb-3">Recent Rate Limit Events</h3>
          {eventList.length === 0 ? (
            <p className="text-gray-500 text-sm">No rate limit events recorded yet.</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-gray-200">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Time</th>
                    <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Scope</th>
                    <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Type</th>
                    <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Current / Limit</th>
                    <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Action</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-200">
                  {eventList.slice(0, 20).map((ev) => (
                    <tr key={ev.id} className="hover:bg-gray-50">
                      <td className="px-4 py-2 text-xs text-gray-500">
                        {ev.created_at ? new Date(ev.created_at).toLocaleString() : '--'}
                      </td>
                      <td className="px-4 py-2 text-xs">
                        <span className="font-medium">{ev.scope}</span>
                        {ev.scope_value && <span className="text-gray-500 ml-1">({ev.scope_value})</span>}
                      </td>
                      <td className="px-4 py-2 text-xs">{ev.limit_type}</td>
                      <td className="px-4 py-2 text-xs">
                        <span className="text-red-600 font-medium">{ev.current_value}</span>
                        <span className="text-gray-400"> / </span>
                        <span>{ev.limit_value}</span>
                      </td>
                      <td className="px-4 py-2 text-xs">
                        <span className={`px-2 py-0.5 rounded-full ${ev.action === 'blocked' ? 'bg-red-100 text-red-800' : 'bg-yellow-100 text-yellow-800'}`}>
                          {ev.action}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* Policies Table */}
      {policyList.length === 0 ? (
        <div className="card text-center text-gray-500 py-12">
          <p className="text-lg font-medium">No rate limit policies</p>
          <p className="text-sm mt-1">Create a policy to enforce granular rate limits.</p>
        </div>
      ) : (
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Name</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Scope</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">RPM</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">TPM</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">RPD</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">TPD</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Priority</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Active</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Actions</th>
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-200">
              {policyList.map((p) => (
                <tr key={p.id} className="hover:bg-gray-50">
                  <td className="px-6 py-4 whitespace-nowrap">
                    <div className="text-sm font-medium text-gray-900">{p.name}</div>
                    {p.description && <div className="text-xs text-gray-500 truncate max-w-xs">{p.description}</div>}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap">
                    <span className="text-sm">{scopeLabels[p.scope] || p.scope}</span>
                    {p.scope_value && (
                      <div className="text-xs text-gray-500">{p.scope_value}</div>
                    )}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm">{formatLimit(p.rpm_limit)}</td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm">{formatLimit(p.tpm_limit)}</td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm">{formatLimit(p.rpd_limit)}</td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm">{formatLimit(p.tpd_limit)}</td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-center">{p.priority}</td>
                  <td className="px-6 py-4 whitespace-nowrap">
                    <span className={`px-2 py-1 text-xs rounded-full ${p.is_active ? 'bg-green-100 text-green-800' : 'bg-gray-100 text-gray-800'}`}>
                      {p.is_active ? 'Active' : 'Inactive'}
                    </span>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap">
                    <div className="flex gap-1">
                      <button
                        onClick={() => startEdit(p)}
                        className="p-1 text-gray-500 hover:text-blue-600"
                        title="Edit"
                      >
                        <PencilSquareIcon className="w-4 h-4" />
                      </button>
                      <button
                        onClick={() => handleDelete(p.id)}
                        className="p-1 text-gray-500 hover:text-red-600"
                        title="Delete"
                      >
                        <TrashIcon className="w-4 h-4" />
                      </button>
                    </div>
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
