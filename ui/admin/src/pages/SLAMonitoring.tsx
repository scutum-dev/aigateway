import { useState } from 'react'
import {
  useSLADefinitions,
  useCreateSLADefinition,
  useProviderHealth,
  useActiveViolations,
  useFailoverRules,
  useCreateFailoverRule,
} from '../api/hooks'
import { slaApi } from '../api/client'
import type { SLADefinitionCreate, FailoverRuleCreate } from '../types'
import { PlusIcon, TrashIcon, CheckIcon, BoltIcon } from '@heroicons/react/24/outline'
import { SkeletonCard } from '../components/Skeleton'
import { useToast } from '../components/Toast'

type TabId = 'health' | 'definitions' | 'violations' | 'failover'

function healthColor(errorRate: number): string {
  if (errorRate <= 0.01) return 'bg-green-100 text-green-800 border-green-300'
  if (errorRate <= 0.05) return 'bg-yellow-100 text-yellow-800 border-yellow-300'
  return 'bg-red-100 text-red-800 border-red-300'
}

function healthDot(errorRate: number): string {
  if (errorRate <= 0.01) return 'bg-green-500'
  if (errorRate <= 0.05) return 'bg-yellow-500'
  return 'bg-red-500'
}

export default function SLAMonitoring() {
  const toast = useToast()
  const [activeTab, setActiveTab] = useState<TabId>('health')
  const [showCreateDef, setShowCreateDef] = useState(false)
  const [showCreateFailover, setShowCreateFailover] = useState(false)

  const { data: health, isLoading: healthLoading } = useProviderHealth()
  const { data: definitions, isLoading: defsLoading } = useSLADefinitions()
  const { data: violations, isLoading: violationsLoading } = useActiveViolations()
  const { data: failoverRules, isLoading: failoverLoading } = useFailoverRules()
  const createDefMutation = useCreateSLADefinition()
  const createFailoverMutation = useCreateFailoverRule()

  const [defForm, setDefForm] = useState<SLADefinitionCreate>({
    name: '',
    provider: '',
    model_pattern: '',
    target_p50_ms: undefined,
    target_p95_ms: undefined,
    target_p99_ms: undefined,
    target_error_rate: 0.01,
    target_availability: 0.999,
    evaluation_window_minutes: 60,
    alert_channels: [],
  })

  const [failoverForm, setFailoverForm] = useState<FailoverRuleCreate>({
    primary_model: '',
    fallback_model: '',
    trigger_condition: 'error_rate',
    trigger_threshold: 0.05,
    cooldown_minutes: 15,
  })

  const handleCreateDef = async () => {
    try {
      const payload = { ...defForm }
      if (!payload.provider) delete payload.provider
      if (!payload.model_pattern) delete payload.model_pattern
      if (!payload.target_p50_ms) delete payload.target_p50_ms
      if (!payload.target_p95_ms) delete payload.target_p95_ms
      if (!payload.target_p99_ms) delete payload.target_p99_ms
      await createDefMutation.mutateAsync(payload)
      toast('success', 'SLA definition created')
      setShowCreateDef(false)
      setDefForm({
        name: '', provider: '', model_pattern: '',
        target_p50_ms: undefined, target_p95_ms: undefined, target_p99_ms: undefined,
        target_error_rate: 0.01, target_availability: 0.999,
        evaluation_window_minutes: 60, alert_channels: [],
      })
    } catch {
      toast('error', 'Failed to create SLA definition')
    }
  }

  const handleDeleteDef = async (id: string) => {
    if (!confirm('Delete this SLA definition?')) return
    try {
      await slaApi.deleteDefinition(id)
      toast('success', 'SLA definition deleted')
      window.location.reload()
    } catch {
      toast('error', 'Failed to delete definition')
    }
  }

  const handleResolve = async (id: string) => {
    try {
      await slaApi.resolveViolation(id)
      toast('success', 'Violation resolved')
      window.location.reload()
    } catch {
      toast('error', 'Failed to resolve violation')
    }
  }

  const handleCreateFailover = async () => {
    try {
      await createFailoverMutation.mutateAsync(failoverForm)
      toast('success', 'Failover rule created')
      setShowCreateFailover(false)
      setFailoverForm({
        primary_model: '', fallback_model: '',
        trigger_condition: 'error_rate', trigger_threshold: 0.05, cooldown_minutes: 15,
      })
    } catch {
      toast('error', 'Failed to create failover rule')
    }
  }

  const handleDeleteFailover = async (id: string) => {
    if (!confirm('Delete this failover rule?')) return
    try {
      await slaApi.deleteFailoverRule(id)
      toast('success', 'Failover rule deleted')
      window.location.reload()
    } catch {
      toast('error', 'Failed to delete failover rule')
    }
  }

  const handleTriggerFailover = async (id: string) => {
    if (!confirm('Manually trigger this failover?')) return
    try {
      await slaApi.triggerFailover(id)
      toast('success', 'Failover triggered')
      window.location.reload()
    } catch {
      toast('error', 'Failed to trigger failover')
    }
  }

  const healthList = Array.isArray(health) ? health : []
  const defList = Array.isArray(definitions) ? definitions : []
  const violationList = Array.isArray(violations) ? violations : []
  const failoverList = Array.isArray(failoverRules) ? failoverRules : []

  const tabs: { id: TabId; label: string; count: number }[] = [
    { id: 'health', label: 'Provider Health', count: healthList.length },
    { id: 'definitions', label: 'SLA Definitions', count: defList.length },
    { id: 'violations', label: 'Violations', count: violationList.length },
    { id: 'failover', label: 'Failover Rules', count: failoverList.length },
  ]

  const isLoading = healthLoading || defsLoading || violationsLoading || failoverLoading

  if (isLoading) {
    return (
      <div className="space-y-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">SLA Monitor</h1>
          <p className="text-gray-600">Provider health, SLA compliance, and failover management</p>
        </div>
        <SkeletonCard />
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">SLA Monitor</h1>
          <p className="text-gray-600">Provider health, SLA compliance, and failover management</p>
        </div>
        <div className="flex gap-2">
          {activeTab === 'definitions' && (
            <button onClick={() => setShowCreateDef(true)} className="btn btn-primary">
              <PlusIcon className="w-4 h-4 mr-1" />
              New SLA
            </button>
          )}
          {activeTab === 'failover' && (
            <button onClick={() => setShowCreateFailover(true)} className="btn btn-primary">
              <PlusIcon className="w-4 h-4 mr-1" />
              New Failover Rule
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

      {/* Create SLA Definition Modal */}
      {showCreateDef && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg p-6 w-full max-w-lg max-h-[90vh] overflow-y-auto">
            <h2 className="text-xl font-bold mb-4">Create SLA Definition</h2>
            <div className="space-y-4">
              <div>
                <label className="label">Name</label>
                <input
                  type="text"
                  value={defForm.name}
                  onChange={(e) => setDefForm({ ...defForm, name: e.target.value })}
                  className="input"
                  placeholder="e.g. Production API SLA"
                />
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="label">Provider</label>
                  <input
                    type="text"
                    value={defForm.provider || ''}
                    onChange={(e) => setDefForm({ ...defForm, provider: e.target.value })}
                    className="input"
                    placeholder="e.g. openai, anthropic"
                  />
                </div>
                <div>
                  <label className="label">Model Pattern</label>
                  <input
                    type="text"
                    value={defForm.model_pattern || ''}
                    onChange={(e) => setDefForm({ ...defForm, model_pattern: e.target.value })}
                    className="input"
                    placeholder="e.g. gpt-4*, claude*"
                  />
                </div>
              </div>
              <div className="grid grid-cols-3 gap-4">
                <div>
                  <label className="label">P50 Target (ms)</label>
                  <input
                    type="number"
                    value={defForm.target_p50_ms ?? ''}
                    onChange={(e) => setDefForm({ ...defForm, target_p50_ms: e.target.value ? Number(e.target.value) : undefined })}
                    className="input"
                    placeholder="500"
                  />
                </div>
                <div>
                  <label className="label">P95 Target (ms)</label>
                  <input
                    type="number"
                    value={defForm.target_p95_ms ?? ''}
                    onChange={(e) => setDefForm({ ...defForm, target_p95_ms: e.target.value ? Number(e.target.value) : undefined })}
                    className="input"
                    placeholder="2000"
                  />
                </div>
                <div>
                  <label className="label">P99 Target (ms)</label>
                  <input
                    type="number"
                    value={defForm.target_p99_ms ?? ''}
                    onChange={(e) => setDefForm({ ...defForm, target_p99_ms: e.target.value ? Number(e.target.value) : undefined })}
                    className="input"
                    placeholder="5000"
                  />
                </div>
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="label">Target Error Rate</label>
                  <input
                    type="number"
                    step="0.001"
                    value={defForm.target_error_rate ?? 0.01}
                    onChange={(e) => setDefForm({ ...defForm, target_error_rate: Number(e.target.value) })}
                    className="input"
                  />
                </div>
                <div>
                  <label className="label">Target Availability</label>
                  <input
                    type="number"
                    step="0.001"
                    value={defForm.target_availability ?? 0.999}
                    onChange={(e) => setDefForm({ ...defForm, target_availability: Number(e.target.value) })}
                    className="input"
                  />
                </div>
              </div>
              <div>
                <label className="label">Evaluation Window (minutes)</label>
                <input
                  type="number"
                  value={defForm.evaluation_window_minutes ?? 60}
                  onChange={(e) => setDefForm({ ...defForm, evaluation_window_minutes: Number(e.target.value) })}
                  className="input"
                />
              </div>
              <div className="flex justify-end gap-2">
                <button onClick={() => setShowCreateDef(false)} className="btn btn-secondary">Cancel</button>
                <button
                  onClick={handleCreateDef}
                  className="btn btn-primary"
                  disabled={!defForm.name}
                >
                  Create
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Create Failover Rule Modal */}
      {showCreateFailover && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg p-6 w-full max-w-lg">
            <h2 className="text-xl font-bold mb-4">Create Failover Rule</h2>
            <div className="space-y-4">
              <div>
                <label className="label">Primary Model</label>
                <input
                  type="text"
                  value={failoverForm.primary_model}
                  onChange={(e) => setFailoverForm({ ...failoverForm, primary_model: e.target.value })}
                  className="input"
                  placeholder="e.g. gpt-4o"
                />
              </div>
              <div>
                <label className="label">Fallback Model</label>
                <input
                  type="text"
                  value={failoverForm.fallback_model}
                  onChange={(e) => setFailoverForm({ ...failoverForm, fallback_model: e.target.value })}
                  className="input"
                  placeholder="e.g. claude-sonnet-4"
                />
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="label">Trigger Condition</label>
                  <select
                    value={failoverForm.trigger_condition || 'error_rate'}
                    onChange={(e) => setFailoverForm({ ...failoverForm, trigger_condition: e.target.value })}
                    className="input"
                  >
                    <option value="error_rate">Error Rate</option>
                    <option value="latency_p95">P95 Latency</option>
                    <option value="latency_p99">P99 Latency</option>
                    <option value="availability">Availability</option>
                  </select>
                </div>
                <div>
                  <label className="label">Threshold</label>
                  <input
                    type="number"
                    step="0.01"
                    value={failoverForm.trigger_threshold ?? 0.05}
                    onChange={(e) => setFailoverForm({ ...failoverForm, trigger_threshold: Number(e.target.value) })}
                    className="input"
                  />
                </div>
              </div>
              <div>
                <label className="label">Cooldown (minutes)</label>
                <input
                  type="number"
                  value={failoverForm.cooldown_minutes ?? 15}
                  onChange={(e) => setFailoverForm({ ...failoverForm, cooldown_minutes: Number(e.target.value) })}
                  className="input"
                />
              </div>
              <div className="flex justify-end gap-2">
                <button onClick={() => setShowCreateFailover(false)} className="btn btn-secondary">Cancel</button>
                <button
                  onClick={handleCreateFailover}
                  className="btn btn-primary"
                  disabled={!failoverForm.primary_model || !failoverForm.fallback_model}
                >
                  Create
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Provider Health Tab */}
      {activeTab === 'health' && (
        <>
          {healthList.length === 0 ? (
            <div className="card text-center text-gray-500 py-12">
              <p className="text-lg font-medium">No health metrics available</p>
              <p className="text-sm mt-1">Provider health metrics will appear once data is collected.</p>
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {healthList.map((metric) => {
                const errorRate = metric.request_count > 0 ? metric.error_count / metric.request_count : 0
                return (
                  <div key={metric.id} className={`card border-2 ${healthColor(errorRate)}`}>
                    <div className="flex justify-between items-start">
                      <div>
                        <div className="flex items-center gap-2">
                          <div className={`w-3 h-3 rounded-full ${healthDot(errorRate)}`} />
                          <h3 className="text-lg font-semibold">{metric.provider}</h3>
                        </div>
                        <p className="text-sm text-gray-600 mt-1">{metric.model}</p>
                      </div>
                      <span className="text-xs text-gray-500">
                        {new Date(metric.bucket_start).toLocaleString()}
                      </span>
                    </div>
                    <div className="mt-4 grid grid-cols-2 gap-3">
                      <div>
                        <p className="text-xs text-gray-500">Requests</p>
                        <p className="text-lg font-semibold">{metric.request_count}</p>
                      </div>
                      <div>
                        <p className="text-xs text-gray-500">Error Rate</p>
                        <p className="text-lg font-semibold">{(errorRate * 100).toFixed(2)}%</p>
                      </div>
                      <div>
                        <p className="text-xs text-gray-500">P50 Latency</p>
                        <p className="text-sm font-medium">{metric.p50_latency_ms ?? '--'}ms</p>
                      </div>
                      <div>
                        <p className="text-xs text-gray-500">P95 Latency</p>
                        <p className="text-sm font-medium">{metric.p95_latency_ms ?? '--'}ms</p>
                      </div>
                      <div>
                        <p className="text-xs text-gray-500">P99 Latency</p>
                        <p className="text-sm font-medium">{metric.p99_latency_ms ?? '--'}ms</p>
                      </div>
                      <div>
                        <p className="text-xs text-gray-500">Tokens</p>
                        <p className="text-sm font-medium">{metric.total_tokens.toLocaleString()}</p>
                      </div>
                    </div>
                  </div>
                )
              })}
            </div>
          )}
        </>
      )}

      {/* SLA Definitions Tab */}
      {activeTab === 'definitions' && (
        <>
          {defList.length === 0 ? (
            <div className="card text-center text-gray-500 py-12">
              <p className="text-lg font-medium">No SLA definitions</p>
              <p className="text-sm mt-1">Define SLA targets for your providers and models.</p>
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {defList.map((def) => (
                <div key={def.id} className="card">
                  <div className="flex justify-between items-start">
                    <div>
                      <h3 className="text-lg font-semibold">{def.name}</h3>
                      <div className="flex gap-2 mt-1">
                        {def.provider && (
                          <span className="px-2 py-0.5 text-xs rounded-full bg-blue-100 text-blue-800">{def.provider}</span>
                        )}
                        {def.model_pattern && (
                          <span className="px-2 py-0.5 text-xs rounded-full bg-purple-100 text-purple-800">{def.model_pattern}</span>
                        )}
                        <span className={`px-2 py-0.5 text-xs rounded-full ${def.is_active ? 'bg-green-100 text-green-800' : 'bg-gray-100 text-gray-600'}`}>
                          {def.is_active ? 'Active' : 'Inactive'}
                        </span>
                      </div>
                    </div>
                    <button
                      onClick={() => handleDeleteDef(def.id)}
                      className="p-1 text-gray-400 hover:text-red-600"
                      title="Delete"
                    >
                      <TrashIcon className="w-4 h-4" />
                    </button>
                  </div>
                  <div className="mt-4 grid grid-cols-3 gap-2 text-sm">
                    {def.target_p50_ms && (
                      <div>
                        <p className="text-xs text-gray-500">P50</p>
                        <p className="font-medium">{def.target_p50_ms}ms</p>
                      </div>
                    )}
                    {def.target_p95_ms && (
                      <div>
                        <p className="text-xs text-gray-500">P95</p>
                        <p className="font-medium">{def.target_p95_ms}ms</p>
                      </div>
                    )}
                    {def.target_p99_ms && (
                      <div>
                        <p className="text-xs text-gray-500">P99</p>
                        <p className="font-medium">{def.target_p99_ms}ms</p>
                      </div>
                    )}
                    <div>
                      <p className="text-xs text-gray-500">Error Rate</p>
                      <p className="font-medium">{(def.target_error_rate * 100).toFixed(2)}%</p>
                    </div>
                    <div>
                      <p className="text-xs text-gray-500">Availability</p>
                      <p className="font-medium">{(def.target_availability * 100).toFixed(1)}%</p>
                    </div>
                    <div>
                      <p className="text-xs text-gray-500">Window</p>
                      <p className="font-medium">{def.evaluation_window_minutes}m</p>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </>
      )}

      {/* Violations Tab */}
      {activeTab === 'violations' && (
        <>
          {violationList.length === 0 ? (
            <div className="card text-center text-gray-500 py-12">
              <p className="text-lg font-medium">No active violations</p>
              <p className="text-sm mt-1">All providers are operating within SLA targets.</p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-gray-200">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Type</th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Provider</th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Model</th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Threshold</th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Actual</th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Status</th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Created</th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Actions</th>
                  </tr>
                </thead>
                <tbody className="bg-white divide-y divide-gray-200">
                  {violationList.map((v) => (
                    <tr key={v.id} className="hover:bg-gray-50">
                      <td className="px-6 py-4 whitespace-nowrap">
                        <span className="px-2 py-0.5 text-xs rounded-full bg-red-100 text-red-800">{v.violation_type}</span>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-600">{v.provider || '--'}</td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-600">{v.model || '--'}</td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-600">{v.threshold_value}</td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-red-600">{v.actual_value}</td>
                      <td className="px-6 py-4 whitespace-nowrap">
                        <span className={`px-2 py-1 text-xs font-medium rounded-full ${
                          v.resolved_at ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'
                        }`}>
                          {v.resolved_at ? 'Resolved' : 'Active'}
                        </span>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                        {v.created_at ? new Date(v.created_at).toLocaleString() : '--'}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap">
                        {!v.resolved_at && (
                          <button
                            onClick={() => handleResolve(v.id)}
                            className="p-1 text-gray-500 hover:text-green-600"
                            title="Resolve"
                          >
                            <CheckIcon className="w-4 h-4" />
                          </button>
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

      {/* Failover Rules Tab */}
      {activeTab === 'failover' && (
        <>
          {failoverList.length === 0 ? (
            <div className="card text-center text-gray-500 py-12">
              <p className="text-lg font-medium">No failover rules</p>
              <p className="text-sm mt-1">Create rules to automatically failover between models.</p>
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {failoverList.map((rule) => (
                <div key={rule.id} className="card">
                  <div className="flex justify-between items-start">
                    <div>
                      <div className="flex items-center gap-2">
                        <code className="text-sm bg-gray-100 px-2 py-0.5 rounded">{rule.primary_model}</code>
                        <span className="text-gray-400">-&gt;</span>
                        <code className="text-sm bg-green-100 px-2 py-0.5 rounded text-green-800">{rule.fallback_model}</code>
                      </div>
                      <div className="flex gap-2 mt-2">
                        <span className={`px-2 py-0.5 text-xs rounded-full ${rule.is_active ? 'bg-green-100 text-green-800' : 'bg-gray-100 text-gray-600'}`}>
                          {rule.is_active ? 'Active' : 'Inactive'}
                        </span>
                        {rule.trigger_condition && (
                          <span className="px-2 py-0.5 text-xs rounded-full bg-blue-100 text-blue-800">
                            {rule.trigger_condition}: {rule.trigger_threshold}
                          </span>
                        )}
                      </div>
                    </div>
                    <div className="flex gap-1">
                      <button
                        onClick={() => handleTriggerFailover(rule.id)}
                        className="p-1 text-gray-400 hover:text-yellow-600"
                        title="Manual trigger"
                      >
                        <BoltIcon className="w-4 h-4" />
                      </button>
                      <button
                        onClick={() => handleDeleteFailover(rule.id)}
                        className="p-1 text-gray-400 hover:text-red-600"
                        title="Delete"
                      >
                        <TrashIcon className="w-4 h-4" />
                      </button>
                    </div>
                  </div>
                  <div className="mt-3 text-sm text-gray-600 space-y-1">
                    <p>Cooldown: {rule.cooldown_minutes} minutes</p>
                    {rule.last_triggered_at && (
                      <p className="text-orange-600">Last triggered: {new Date(rule.last_triggered_at).toLocaleString()}</p>
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
