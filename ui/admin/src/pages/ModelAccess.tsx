import { useState } from 'react'
import {
  useModelAccessTiers,
  useCreateModelAccessTier,
  useModelAccessRequests,
  useCreateModelAccessRequest,
  useMyModelAccess,
} from '../api/hooks'
import { modelAccessApi } from '../api/client'
import type { ModelAccessTierCreate, ModelAccessRequestCreate } from '../types'
import { PlusIcon, TrashIcon, CheckIcon, XMarkIcon } from '@heroicons/react/24/outline'
import { SkeletonCard } from '../components/Skeleton'
import { useToast } from '../components/Toast'

type TabId = 'tiers' | 'requests' | 'my-access'

const statusColors: Record<string, string> = {
  pending: 'bg-yellow-100 text-yellow-800',
  approved: 'bg-green-100 text-green-800',
  rejected: 'bg-red-100 text-red-800',
  expired: 'bg-gray-100 text-gray-800',
}

export default function ModelAccess() {
  const toast = useToast()
  const [activeTab, setActiveTab] = useState<TabId>('tiers')
  const [showCreateTier, setShowCreateTier] = useState(false)
  const [showCreateRequest, setShowCreateRequest] = useState(false)
  const [modelInput, setModelInput] = useState('')

  const { data: tiers, isLoading: tiersLoading } = useModelAccessTiers()
  const { data: requests, isLoading: requestsLoading } = useModelAccessRequests()
  const { data: myAccess, isLoading: myAccessLoading } = useMyModelAccess()
  const createTierMutation = useCreateModelAccessTier()
  const createRequestMutation = useCreateModelAccessRequest()

  const [tierForm, setTierForm] = useState<ModelAccessTierCreate>({
    name: '',
    description: '',
    requires_approval: false,
    requires_justification: false,
    max_grant_duration_days: undefined,
    models: [],
  })

  const [requestForm, setRequestForm] = useState<ModelAccessRequestCreate>({
    model_pattern: '',
    tier_id: '',
    justification: '',
  })

  const handleCreateTier = async () => {
    try {
      const payload = { ...tierForm }
      if (!payload.max_grant_duration_days) delete payload.max_grant_duration_days
      await createTierMutation.mutateAsync(payload)
      toast('success', 'Access tier created')
      setShowCreateTier(false)
      setTierForm({ name: '', description: '', requires_approval: false, requires_justification: false, models: [] })
      setModelInput('')
    } catch {
      toast('error', 'Failed to create tier')
    }
  }

  const handleDeleteTier = async (id: string) => {
    if (!confirm('Delete this access tier?')) return
    try {
      await modelAccessApi.deleteTier(id)
      toast('success', 'Tier deleted')
      window.location.reload()
    } catch {
      toast('error', 'Failed to delete tier')
    }
  }

  const handleCreateRequest = async () => {
    try {
      const payload = { ...requestForm }
      if (!payload.tier_id) delete payload.tier_id
      if (!payload.justification) delete payload.justification
      await createRequestMutation.mutateAsync(payload)
      toast('success', 'Access request submitted')
      setShowCreateRequest(false)
      setRequestForm({ model_pattern: '', tier_id: '', justification: '' })
    } catch {
      toast('error', 'Failed to submit access request')
    }
  }

  const handleApprove = async (id: string) => {
    try {
      await modelAccessApi.approveRequest(id)
      toast('success', 'Request approved')
      window.location.reload()
    } catch {
      toast('error', 'Failed to approve request')
    }
  }

  const handleReject = async (id: string) => {
    try {
      await modelAccessApi.rejectRequest(id)
      toast('success', 'Request rejected')
      window.location.reload()
    } catch {
      toast('error', 'Failed to reject request')
    }
  }

  const tierList = Array.isArray(tiers) ? tiers : []
  const requestList = Array.isArray(requests) ? requests : []
  const myAccessList = Array.isArray(myAccess) ? myAccess : []

  const tabs: { id: TabId; label: string; count: number }[] = [
    { id: 'tiers', label: 'Access Tiers', count: tierList.length },
    { id: 'requests', label: 'Requests', count: requestList.filter((r) => r.status === 'pending').length },
    { id: 'my-access', label: 'My Access', count: myAccessList.length },
  ]

  const isLoading = tiersLoading || requestsLoading || myAccessLoading

  if (isLoading) {
    return (
      <div className="space-y-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Model Access</h1>
          <p className="text-gray-600">Govern model access with tiered permissions</p>
        </div>
        <SkeletonCard />
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Model Access</h1>
          <p className="text-gray-600">Govern model access with tiered permissions</p>
        </div>
        <div className="flex gap-2">
          {activeTab === 'tiers' && (
            <button onClick={() => setShowCreateTier(true)} className="btn btn-primary">
              <PlusIcon className="w-4 h-4 mr-1" />
              New Tier
            </button>
          )}
          {(activeTab === 'requests' || activeTab === 'my-access') && (
            <button onClick={() => setShowCreateRequest(true)} className="btn btn-primary">
              <PlusIcon className="w-4 h-4 mr-1" />
              Request Access
            </button>
          )}
        </div>
      </div>

      {/* Tabs */}
      <div className="border-b border-gray-200">
        <nav className="flex space-x-8">
          {tabs.map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`pb-3 px-1 border-b-2 text-sm font-medium ${
                activeTab === tab.id
                  ? 'border-primary-600 text-primary-600'
                  : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
              }`}
            >
              {tab.label}
              {tab.count > 0 && (
                <span className={`ml-2 px-2 py-0.5 rounded-full text-xs ${
                  activeTab === tab.id ? 'bg-primary-100 text-primary-800' : 'bg-gray-100 text-gray-600'
                }`}>
                  {tab.count}
                </span>
              )}
            </button>
          ))}
        </nav>
      </div>

      {/* Create Tier Modal */}
      {showCreateTier && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg p-6 w-full max-w-lg max-h-[90vh] overflow-y-auto">
            <h2 className="text-xl font-bold mb-4">Create Access Tier</h2>
            <div className="space-y-4">
              <div>
                <label className="label">Name</label>
                <input
                  type="text"
                  value={tierForm.name}
                  onChange={(e) => setTierForm({ ...tierForm, name: e.target.value })}
                  className="input"
                  placeholder="e.g. standard, premium, experimental"
                />
              </div>
              <div>
                <label className="label">Description</label>
                <input
                  type="text"
                  value={tierForm.description || ''}
                  onChange={(e) => setTierForm({ ...tierForm, description: e.target.value })}
                  className="input"
                  placeholder="Describe this tier"
                />
              </div>
              <div className="grid grid-cols-2 gap-4">
                <label className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    checked={tierForm.requires_approval}
                    onChange={(e) => setTierForm({ ...tierForm, requires_approval: e.target.checked })}
                    className="rounded"
                  />
                  <span className="text-sm">Requires Approval</span>
                </label>
                <label className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    checked={tierForm.requires_justification}
                    onChange={(e) => setTierForm({ ...tierForm, requires_justification: e.target.checked })}
                    className="rounded"
                  />
                  <span className="text-sm">Requires Justification</span>
                </label>
              </div>
              <div>
                <label className="label">Max Grant Duration (days)</label>
                <input
                  type="number"
                  value={tierForm.max_grant_duration_days ?? ''}
                  onChange={(e) => setTierForm({ ...tierForm, max_grant_duration_days: e.target.value ? Number(e.target.value) : undefined })}
                  className="input"
                  placeholder="No expiry"
                />
              </div>
              <div>
                <label className="label">Models</label>
                <div className="flex gap-2">
                  <input
                    type="text"
                    value={modelInput}
                    onChange={(e) => setModelInput(e.target.value)}
                    className="input flex-1"
                    placeholder="Add model name"
                    onKeyDown={(e) => {
                      if (e.key === 'Enter' && modelInput.trim()) {
                        e.preventDefault()
                        setTierForm({ ...tierForm, models: [...(tierForm.models || []), modelInput.trim()] })
                        setModelInput('')
                      }
                    }}
                  />
                  <button
                    onClick={() => {
                      if (modelInput.trim()) {
                        setTierForm({ ...tierForm, models: [...(tierForm.models || []), modelInput.trim()] })
                        setModelInput('')
                      }
                    }}
                    className="btn btn-secondary"
                  >
                    Add
                  </button>
                </div>
                {tierForm.models && tierForm.models.length > 0 && (
                  <div className="flex flex-wrap gap-1 mt-2">
                    {tierForm.models.map((model, i) => (
                      <span key={i} className="bg-purple-100 text-purple-800 text-xs px-2 py-1 rounded-full flex items-center gap-1">
                        {model}
                        <button
                          onClick={() => setTierForm({ ...tierForm, models: tierForm.models?.filter((_, idx) => idx !== i) })}
                          className="hover:text-purple-600"
                        >
                          <XMarkIcon className="w-3 h-3" />
                        </button>
                      </span>
                    ))}
                  </div>
                )}
              </div>
              <div className="flex justify-end gap-2">
                <button onClick={() => setShowCreateTier(false)} className="btn btn-secondary">Cancel</button>
                <button
                  onClick={handleCreateTier}
                  className="btn btn-primary"
                  disabled={!tierForm.name}
                >
                  Create
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Create Request Modal */}
      {showCreateRequest && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg p-6 w-full max-w-lg">
            <h2 className="text-xl font-bold mb-4">Request Model Access</h2>
            <div className="space-y-4">
              <div>
                <label className="label">Model Pattern</label>
                <input
                  type="text"
                  value={requestForm.model_pattern}
                  onChange={(e) => setRequestForm({ ...requestForm, model_pattern: e.target.value })}
                  className="input"
                  placeholder="gpt-5, claude-sonnet-4.5, etc."
                />
              </div>
              <div>
                <label className="label">Access Tier</label>
                <select
                  value={requestForm.tier_id || ''}
                  onChange={(e) => setRequestForm({ ...requestForm, tier_id: e.target.value })}
                  className="input"
                >
                  <option value="">Select a tier (optional)</option>
                  {tierList.map((tier) => (
                    <option key={tier.id} value={tier.id}>{tier.name}</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="label">Justification</label>
                <textarea
                  value={requestForm.justification || ''}
                  onChange={(e) => setRequestForm({ ...requestForm, justification: e.target.value })}
                  className="input"
                  rows={3}
                  placeholder="Why do you need access to this model?"
                />
              </div>
              <div className="flex justify-end gap-2">
                <button onClick={() => setShowCreateRequest(false)} className="btn btn-secondary">Cancel</button>
                <button
                  onClick={handleCreateRequest}
                  className="btn btn-primary"
                  disabled={!requestForm.model_pattern}
                >
                  Submit Request
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Tiers Tab */}
      {activeTab === 'tiers' && (
        <>
          {tierList.length === 0 ? (
            <div className="card text-center text-gray-500 py-12">
              <p className="text-lg font-medium">No access tiers defined</p>
              <p className="text-sm mt-1">Create tiers to categorize model access levels.</p>
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {tierList.map((tier) => (
                <div key={tier.id} className="card">
                  <div className="flex justify-between items-start">
                    <div>
                      <h3 className="text-lg font-semibold capitalize">{tier.name}</h3>
                      {tier.description && <p className="text-sm text-gray-500 mt-1">{tier.description}</p>}
                    </div>
                    <button
                      onClick={() => handleDeleteTier(tier.id)}
                      className="p-1 text-gray-400 hover:text-red-600"
                      title="Delete tier"
                    >
                      <TrashIcon className="w-4 h-4" />
                    </button>
                  </div>
                  <div className="mt-4 space-y-2">
                    <div className="flex gap-2">
                      <span className={`px-2 py-0.5 text-xs rounded-full ${tier.requires_approval ? 'bg-yellow-100 text-yellow-800' : 'bg-green-100 text-green-800'}`}>
                        {tier.requires_approval ? 'Approval Required' : 'Auto-Approve'}
                      </span>
                      {tier.requires_justification && (
                        <span className="px-2 py-0.5 text-xs rounded-full bg-blue-100 text-blue-800">
                          Justification Required
                        </span>
                      )}
                    </div>
                    {tier.max_grant_duration_days && (
                      <p className="text-xs text-gray-500">Max duration: {tier.max_grant_duration_days} days</p>
                    )}
                    {tier.models.length > 0 && (
                      <div className="flex flex-wrap gap-1 mt-2">
                        {tier.models.map((model, i) => (
                          <span key={i} className="bg-purple-100 text-purple-800 text-xs px-2 py-0.5 rounded-full">
                            {model}
                          </span>
                        ))}
                      </div>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </>
      )}

      {/* Requests Tab */}
      {activeTab === 'requests' && (
        <>
          {requestList.length === 0 ? (
            <div className="card text-center text-gray-500 py-12">
              <p className="text-lg font-medium">No access requests</p>
              <p className="text-sm mt-1">Access requests will appear here.</p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-gray-200">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">User</th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Model</th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Justification</th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Status</th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Requested</th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Actions</th>
                  </tr>
                </thead>
                <tbody className="bg-white divide-y divide-gray-200">
                  {requestList.map((req) => (
                    <tr key={req.id} className="hover:bg-gray-50">
                      <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">{req.user_id}</td>
                      <td className="px-6 py-4 whitespace-nowrap">
                        <code className="text-sm bg-gray-100 px-2 py-0.5 rounded">{req.model_pattern}</code>
                      </td>
                      <td className="px-6 py-4 text-sm text-gray-600 max-w-xs truncate">
                        {req.justification || '--'}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap">
                        <span className={`px-2 py-1 text-xs font-medium rounded-full ${statusColors[req.status] || 'bg-gray-100 text-gray-800'}`}>
                          {req.status}
                        </span>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                        {req.created_at ? new Date(req.created_at).toLocaleString() : '--'}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap">
                        {req.status === 'pending' && (
                          <div className="flex gap-1">
                            <button
                              onClick={() => handleApprove(req.id)}
                              className="p-1 text-gray-500 hover:text-green-600"
                              title="Approve"
                            >
                              <CheckIcon className="w-4 h-4" />
                            </button>
                            <button
                              onClick={() => handleReject(req.id)}
                              className="p-1 text-gray-500 hover:text-red-600"
                              title="Reject"
                            >
                              <XMarkIcon className="w-4 h-4" />
                            </button>
                          </div>
                        )}
                        {req.status !== 'pending' && (
                          <span className="text-xs text-gray-400">
                            {req.reviewer ? `by ${req.reviewer}` : '--'}
                          </span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </>
      )}

      {/* My Access Tab */}
      {activeTab === 'my-access' && (
        <>
          {myAccessList.length === 0 ? (
            <div className="card text-center text-gray-500 py-12">
              <p className="text-lg font-medium">No active grants</p>
              <p className="text-sm mt-1">Request access to models to see your grants here.</p>
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {myAccessList.map((grant) => (
                <div key={grant.id} className="card">
                  <div className="flex justify-between items-start">
                    <div>
                      <code className="text-lg font-medium bg-gray-100 px-2 py-1 rounded">{grant.model_pattern}</code>
                      <span className={`ml-2 px-2 py-0.5 text-xs rounded-full ${statusColors[grant.status] || 'bg-gray-100 text-gray-800'}`}>
                        {grant.status}
                      </span>
                    </div>
                  </div>
                  <div className="mt-3 space-y-1 text-sm text-gray-600">
                    {grant.granted_at && (
                      <p>Granted: {new Date(grant.granted_at).toLocaleDateString()}</p>
                    )}
                    {grant.expires_at && (
                      <p className="text-orange-600">
                        Expires: {new Date(grant.expires_at).toLocaleDateString()}
                      </p>
                    )}
                    {!grant.expires_at && (
                      <p className="text-green-600">No expiration</p>
                    )}
                    {grant.reviewer && (
                      <p>Approved by: {grant.reviewer}</p>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </>
      )}
    </div>
  )
}
