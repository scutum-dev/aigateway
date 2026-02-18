import { useState } from 'react'
import {
  useRoutingPolicies,
  useCreateRoutingPolicy,
  useUpdateRoutingPolicy,
  useDeleteRoutingPolicy,
  useSyncRoutingPolicies,
  useLiteLLMRouterStatus,
} from '../api/hooks'
import type { RoutingPolicyCreate } from '../types'
import {
  PlusIcon,
  TrashIcon,
  ArrowPathIcon,
  PencilIcon,
  SignalIcon,
  ArrowsRightLeftIcon,
} from '@heroicons/react/24/outline'
import { SkeletonCard } from '../components/Skeleton'
import { useToast } from '../components/Toast'

const POLICY_TYPES = [
  { value: 'fallback', label: 'Fallback Chain', description: 'Define fallback models when primary model fails' },
  { value: 'model_group', label: 'Model Group', description: 'Group models under an alias (e.g. "fast", "smart")' },
  { value: 'routing_strategy', label: 'Routing Strategy', description: 'Set the global routing algorithm' },
  { value: 'conditional', label: 'Conditional', description: 'Route based on conditions (budget, token count)' },
]

const ROUTING_STRATEGIES = [
  { value: 'usage-based-routing', label: 'Usage-Based' },
  { value: 'least-busy', label: 'Least Busy' },
  { value: 'latency-based-routing', label: 'Latency-Based' },
  { value: 'cost-based-routing', label: 'Cost-Based' },
  { value: 'simple-shuffle', label: 'Simple Shuffle' },
]

const typeBadge: Record<string, string> = {
  fallback: 'bg-orange-100 text-orange-800',
  model_group: 'bg-blue-100 text-blue-800',
  routing_strategy: 'bg-purple-100 text-purple-800',
  conditional: 'bg-green-100 text-green-800',
}

export default function RoutingPolicies() {
  const { data: policies, isLoading, error } = useRoutingPolicies()
  const { data: routerStatus } = useLiteLLMRouterStatus()
  const createPolicy = useCreateRoutingPolicy()
  const updatePolicy = useUpdateRoutingPolicy()
  const deletePolicy = useDeleteRoutingPolicy()
  const syncAll = useSyncRoutingPolicies()
  const toast = useToast()

  const [showForm, setShowForm] = useState(false)
  const [editingId, setEditingId] = useState<string | null>(null)
  const [filterType, setFilterType] = useState<string>('')

  // Form state
  const [formName, setFormName] = useState('')
  const [formDescription, setFormDescription] = useState('')
  const [formType, setFormType] = useState('fallback')
  const [formPriority, setFormPriority] = useState(0)
  const [formActive, setFormActive] = useState(true)
  // Fallback config
  const [fbModel, setFbModel] = useState('')
  const [fbFallbacks, setFbFallbacks] = useState('')
  // Model group config
  const [mgAlias, setMgAlias] = useState('')
  const [mgModels, setMgModels] = useState('')
  // Routing strategy config
  const [rsStrategy, setRsStrategy] = useState('usage-based-routing')
  const [rsTtl, setRsTtl] = useState(60)
  const [rsRpmCheck, setRsRpmCheck] = useState(true)
  const [rsTpmCheck, setRsTpmCheck] = useState(true)
  // Conditional config
  const [condCondition, setCondCondition] = useState('')
  const [condSource, setCondSource] = useState('')
  const [condRedirect, setCondRedirect] = useState('')

  const resetForm = () => {
    setFormName('')
    setFormDescription('')
    setFormType('fallback')
    setFormPriority(0)
    setFormActive(true)
    setFbModel('')
    setFbFallbacks('')
    setMgAlias('')
    setMgModels('')
    setRsStrategy('usage-based-routing')
    setRsTtl(60)
    setRsRpmCheck(true)
    setRsTpmCheck(true)
    setCondCondition('')
    setCondSource('')
    setCondRedirect('')
    setEditingId(null)
    setShowForm(false)
  }

  const buildConfig = (): Record<string, unknown> => {
    switch (formType) {
      case 'fallback':
        return {
          model: fbModel.trim(),
          fallbacks: fbFallbacks.split(',').map(s => s.trim()).filter(Boolean),
        }
      case 'model_group':
        return {
          alias: mgAlias.trim(),
          models: mgModels.split(',').map(s => s.trim()).filter(Boolean),
        }
      case 'routing_strategy':
        return {
          strategy: rsStrategy,
          args: { ttl: rsTtl, rpm_limit_check: rsRpmCheck, tpm_limit_check: rsTpmCheck },
        }
      case 'conditional':
        return {
          condition: condCondition.trim(),
          source_model: condSource.trim(),
          redirect_to: condRedirect.trim(),
        }
      default:
        return {}
    }
  }

  const loadFormFromPolicy = (policy: { name: string; description: string | null; policy_type: string; config: Record<string, unknown>; priority: number; is_active: boolean }) => {
    setFormName(policy.name)
    setFormDescription((policy.description as string) || '')
    setFormType(policy.policy_type)
    setFormPriority(policy.priority)
    setFormActive(policy.is_active)
    const cfg = policy.config
    switch (policy.policy_type) {
      case 'fallback':
        setFbModel((cfg.model as string) || '')
        setFbFallbacks(((cfg.fallbacks as string[]) || []).join(', '))
        break
      case 'model_group':
        setMgAlias((cfg.alias as string) || '')
        setMgModels(((cfg.models as string[]) || []).join(', '))
        break
      case 'routing_strategy':
        setRsStrategy((cfg.strategy as string) || 'usage-based-routing')
        { const args = (cfg.args || {}) as Record<string, unknown>
          setRsTtl((args.ttl as number) || 60)
          setRsRpmCheck(args.rpm_limit_check !== false)
          setRsTpmCheck(args.tpm_limit_check !== false)
        }
        break
      case 'conditional':
        setCondCondition((cfg.condition as string) || '')
        setCondSource((cfg.source_model as string) || '')
        setCondRedirect((cfg.redirect_to as string) || '')
        break
    }
  }

  const handleSubmit = async () => {
    const data: RoutingPolicyCreate = {
      name: formName,
      description: formDescription || undefined,
      policy_type: formType,
      config: buildConfig(),
      priority: formPriority,
      is_active: formActive,
    }

    try {
      if (editingId) {
        await updatePolicy.mutateAsync({ id: editingId, data })
        toast('success', 'Policy updated and synced to LiteLLM')
      } else {
        await createPolicy.mutateAsync(data)
        toast('success', 'Policy created and synced to LiteLLM')
      }
      resetForm()
    } catch {
      toast('error', 'Failed to save policy')
    }
  }

  const handleDelete = async (id: string) => {
    try {
      await deletePolicy.mutateAsync(id)
      toast('success', 'Policy deleted')
    } catch {
      toast('error', 'Failed to delete policy')
    }
  }

  const handleSyncAll = async () => {
    try {
      const result = await syncAll.mutateAsync()
      toast('success', `Synced ${result.synced} policy types to LiteLLM`)
    } catch {
      toast('error', 'Sync failed')
    }
  }

  const filtered = policies?.filter(p => !filterType || p.policy_type === filterType) || []

  if (error) {
    return <div className="p-6 text-red-600">Error loading routing policies: {(error as Error).message}</div>
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-gray-900">Routing Policies</h2>
          <p className="mt-1 text-sm text-gray-500">
            Configure model routing rules synced to LiteLLM
          </p>
        </div>
        <div className="flex gap-2">
          <button
            onClick={handleSyncAll}
            disabled={syncAll.isPending}
            className="inline-flex items-center gap-1.5 rounded-md bg-white px-3 py-2 text-sm font-semibold text-gray-900 shadow-sm ring-1 ring-inset ring-gray-300 hover:bg-gray-50"
          >
            <ArrowPathIcon className={`h-4 w-4 ${syncAll.isPending ? 'animate-spin' : ''}`} />
            Sync All
          </button>
          <button
            onClick={() => { resetForm(); setShowForm(true) }}
            className="inline-flex items-center gap-1.5 rounded-md bg-indigo-600 px-3 py-2 text-sm font-semibold text-white shadow-sm hover:bg-indigo-500"
          >
            <PlusIcon className="h-4 w-4" />
            Add Policy
          </button>
        </div>
      </div>

      {/* LiteLLM Router Status */}
      {routerStatus && (
        <div className="rounded-lg bg-gray-50 p-4">
          <h3 className="text-sm font-medium text-gray-700 flex items-center gap-1.5">
            <SignalIcon className="h-4 w-4" />
            LiteLLM Router Status
          </h3>
          <div className="mt-2 grid grid-cols-1 sm:grid-cols-3 gap-4 text-sm">
            <div>
              <span className="text-gray-500">Strategy:</span>{' '}
              <span className="font-medium">{routerStatus.routing_strategy || 'default'}</span>
            </div>
            <div>
              <span className="text-gray-500">Fallback chains:</span>{' '}
              <span className="font-medium">{routerStatus.fallbacks?.length || 0}</span>
            </div>
            <div>
              <span className="text-gray-500">Model groups:</span>{' '}
              <span className="font-medium">{Object.keys(routerStatus.model_group_aliases || {}).length}</span>
            </div>
          </div>
        </div>
      )}

      {/* Filters */}
      <div className="flex gap-2">
        <button
          onClick={() => setFilterType('')}
          className={`rounded-md px-3 py-1.5 text-sm font-medium ${!filterType ? 'bg-indigo-100 text-indigo-700' : 'bg-white text-gray-700 ring-1 ring-gray-300'}`}
        >
          All
        </button>
        {POLICY_TYPES.map(t => (
          <button
            key={t.value}
            onClick={() => setFilterType(t.value)}
            className={`rounded-md px-3 py-1.5 text-sm font-medium ${filterType === t.value ? 'bg-indigo-100 text-indigo-700' : 'bg-white text-gray-700 ring-1 ring-gray-300'}`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {/* Create/Edit Form */}
      {showForm && (
        <div className="rounded-lg border border-gray-200 bg-white p-6 shadow-sm">
          <h3 className="text-lg font-semibold text-gray-900 mb-4">
            {editingId ? 'Edit Policy' : 'New Routing Policy'}
          </h3>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700">Name</label>
              <input
                type="text"
                value={formName}
                onChange={(e) => setFormName(e.target.value)}
                placeholder="e.g. OpenAI Fallback Chain"
                className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700">Policy Type</label>
              <select
                value={formType}
                onChange={(e) => setFormType(e.target.value)}
                disabled={!!editingId}
                className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm"
              >
                {POLICY_TYPES.map(t => (
                  <option key={t.value} value={t.value}>{t.label}</option>
                ))}
              </select>
            </div>
            <div className="md:col-span-2">
              <label className="block text-sm font-medium text-gray-700">Description</label>
              <input
                type="text"
                value={formDescription}
                onChange={(e) => setFormDescription(e.target.value)}
                className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm"
              />
            </div>

            {/* Type-specific config */}
            {formType === 'fallback' && (
              <>
                <div>
                  <label className="block text-sm font-medium text-gray-700">Primary Model</label>
                  <input
                    type="text"
                    value={fbModel}
                    onChange={(e) => setFbModel(e.target.value)}
                    placeholder="e.g. gpt-5"
                    className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700">Fallback Models (comma-separated)</label>
                  <input
                    type="text"
                    value={fbFallbacks}
                    onChange={(e) => setFbFallbacks(e.target.value)}
                    placeholder="e.g. gpt-5.2, claude-opus-4.5, grok-4"
                    className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm"
                  />
                </div>
              </>
            )}

            {formType === 'model_group' && (
              <>
                <div>
                  <label className="block text-sm font-medium text-gray-700">Group Alias</label>
                  <input
                    type="text"
                    value={mgAlias}
                    onChange={(e) => setMgAlias(e.target.value)}
                    placeholder='e.g. "fast" or "smart"'
                    className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700">Models (comma-separated)</label>
                  <input
                    type="text"
                    value={mgModels}
                    onChange={(e) => setMgModels(e.target.value)}
                    placeholder="e.g. gpt-5-mini, claude-haiku-4.5, gemini-3-flash"
                    className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm"
                  />
                </div>
              </>
            )}

            {formType === 'routing_strategy' && (
              <>
                <div>
                  <label className="block text-sm font-medium text-gray-700">Strategy</label>
                  <select
                    value={rsStrategy}
                    onChange={(e) => setRsStrategy(e.target.value)}
                    className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm"
                  >
                    {ROUTING_STRATEGIES.map(s => (
                      <option key={s.value} value={s.value}>{s.label}</option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700">Cache TTL (seconds)</label>
                  <input
                    type="number"
                    value={rsTtl}
                    onChange={(e) => setRsTtl(Number(e.target.value))}
                    className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm"
                  />
                </div>
                <div className="flex items-center gap-4">
                  <label className="flex items-center gap-2 text-sm">
                    <input type="checkbox" checked={rsRpmCheck} onChange={(e) => setRsRpmCheck(e.target.checked)} className="rounded border-gray-300" />
                    RPM Limit Check
                  </label>
                  <label className="flex items-center gap-2 text-sm">
                    <input type="checkbox" checked={rsTpmCheck} onChange={(e) => setRsTpmCheck(e.target.checked)} className="rounded border-gray-300" />
                    TPM Limit Check
                  </label>
                </div>
              </>
            )}

            {formType === 'conditional' && (
              <>
                <div className="md:col-span-2">
                  <label className="block text-sm font-medium text-gray-700">Condition</label>
                  <input
                    type="text"
                    value={condCondition}
                    onChange={(e) => setCondCondition(e.target.value)}
                    placeholder='e.g. budget_usage > 80%'
                    className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700">Source Model</label>
                  <input
                    type="text"
                    value={condSource}
                    onChange={(e) => setCondSource(e.target.value)}
                    placeholder="e.g. gpt-5"
                    className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700">Redirect To</label>
                  <input
                    type="text"
                    value={condRedirect}
                    onChange={(e) => setCondRedirect(e.target.value)}
                    placeholder="e.g. gpt-5-mini"
                    className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm"
                  />
                </div>
              </>
            )}

            <div className="flex items-center gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700">Priority</label>
                <input
                  type="number"
                  value={formPriority}
                  onChange={(e) => setFormPriority(Number(e.target.value))}
                  className="mt-1 block w-24 rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm"
                />
              </div>
              <label className="flex items-center gap-2 text-sm mt-6">
                <input type="checkbox" checked={formActive} onChange={(e) => setFormActive(e.target.checked)} className="rounded border-gray-300" />
                Active
              </label>
            </div>
          </div>

          <div className="mt-4 flex gap-2">
            <button
              onClick={handleSubmit}
              disabled={!formName || createPolicy.isPending || updatePolicy.isPending}
              className="rounded-md bg-indigo-600 px-4 py-2 text-sm font-semibold text-white shadow-sm hover:bg-indigo-500 disabled:opacity-50"
            >
              {editingId ? 'Update' : 'Create'} Policy
            </button>
            <button
              onClick={resetForm}
              className="rounded-md bg-white px-4 py-2 text-sm font-semibold text-gray-700 shadow-sm ring-1 ring-gray-300 hover:bg-gray-50"
            >
              Cancel
            </button>
          </div>
        </div>
      )}

      {/* Policy List */}
      {isLoading ? (
        <div className="grid grid-cols-1 gap-4">
          {[1, 2, 3].map(i => <SkeletonCard key={i} />)}
        </div>
      ) : filtered.length === 0 ? (
        <div className="text-center py-12">
          <ArrowsRightLeftIcon className="mx-auto h-12 w-12 text-gray-400" />
          <h3 className="mt-2 text-sm font-semibold text-gray-900">No routing policies</h3>
          <p className="mt-1 text-sm text-gray-500">Create a policy to configure model routing.</p>
        </div>
      ) : (
        <div className="space-y-3">
          {filtered.map(policy => (
            <div key={policy.id} className="rounded-lg border border-gray-200 bg-white p-4 shadow-sm">
              <div className="flex items-start justify-between">
                <div className="flex-1">
                  <div className="flex items-center gap-2">
                    <h3 className="text-sm font-semibold text-gray-900">{policy.name}</h3>
                    <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${typeBadge[policy.policy_type] || 'bg-gray-100 text-gray-800'}`}>
                      {POLICY_TYPES.find(t => t.value === policy.policy_type)?.label || policy.policy_type}
                    </span>
                    {!policy.is_active && (
                      <span className="inline-flex items-center rounded-full bg-gray-100 px-2 py-0.5 text-xs font-medium text-gray-600">
                        Inactive
                      </span>
                    )}
                    {policy.synced_at && (
                      <span className="inline-flex items-center rounded-full bg-green-50 px-2 py-0.5 text-xs font-medium text-green-700">
                        Synced
                      </span>
                    )}
                  </div>
                  {policy.description && (
                    <p className="mt-1 text-sm text-gray-500">{policy.description}</p>
                  )}
                  {/* Config summary */}
                  <div className="mt-2 text-xs text-gray-500 font-mono">
                    {policy.policy_type === 'fallback' && (
                      <span>{(policy.config.model as string)} → {((policy.config.fallbacks as string[]) || []).join(' → ')}</span>
                    )}
                    {policy.policy_type === 'model_group' && (
                      <span>"{(policy.config.alias as string)}" = [{((policy.config.models as string[]) || []).join(', ')}]</span>
                    )}
                    {policy.policy_type === 'routing_strategy' && (
                      <span>Strategy: {(policy.config.strategy as string)}</span>
                    )}
                    {policy.policy_type === 'conditional' && (
                      <span>IF {(policy.config.condition as string)} THEN {(policy.config.source_model as string)} → {(policy.config.redirect_to as string)}</span>
                    )}
                  </div>
                </div>
                <div className="flex gap-1">
                  <button
                    onClick={() => {
                      setEditingId(policy.id)
                      loadFormFromPolicy(policy)
                      setShowForm(true)
                    }}
                    className="rounded p-1.5 text-gray-400 hover:text-indigo-600 hover:bg-gray-100"
                    title="Edit"
                  >
                    <PencilIcon className="h-4 w-4" />
                  </button>
                  <button
                    onClick={() => handleDelete(policy.id)}
                    className="rounded p-1.5 text-gray-400 hover:text-red-600 hover:bg-gray-100"
                    title="Delete"
                  >
                    <TrashIcon className="h-4 w-4" />
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
