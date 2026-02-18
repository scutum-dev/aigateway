import { useState } from 'react'
import {
  useABTests,
  useABTest,
  useCreateABTest,
  useDeleteABTest,
  useStartABTest,
  useStopABTest,
  usePromoteABTest,
  useABTestSnapshots,
} from '../api/hooks'
import type { ABTestCreate } from '../types'
import {
  PlusIcon,
  TrashIcon,
  PlayIcon,
  StopIcon,
  ArrowUpIcon,
  BeakerIcon,
  ChevronLeftIcon,
} from '@heroicons/react/24/outline'
import { SkeletonCard } from '../components/Skeleton'
import { useToast } from '../components/Toast'

const statusBadge: Record<string, string> = {
  draft: 'bg-gray-100 text-gray-800',
  running: 'bg-green-100 text-green-800',
  completed: 'bg-blue-100 text-blue-800',
  rolled_back: 'bg-red-100 text-red-800',
}

const metricLabels: Record<string, string> = {
  cost_efficiency: 'Cost Efficiency',
  latency: 'Latency',
  error_rate: 'Error Rate',
  quality: 'Quality',
  throughput: 'Throughput',
}

export default function ABTests() {
  const toast = useToast()
  const [showCreate, setShowCreate] = useState(false)
  const [selectedTestId, setSelectedTestId] = useState<string | null>(null)

  const { data: tests, isLoading } = useABTests()
  const { data: testDetail } = useABTest(selectedTestId)
  const { data: snapshots } = useABTestSnapshots(selectedTestId)
  const createMutation = useCreateABTest()
  const deleteMutation = useDeleteABTest()
  const startMutation = useStartABTest()
  const stopMutation = useStopABTest()
  const promoteMutation = usePromoteABTest()

  const [form, setForm] = useState<ABTestCreate>({
    name: '',
    base_model: '',
    variant_model: '',
    traffic_split_percent: 10,
    success_metric: 'cost_efficiency',
    auto_promote: false,
    auto_rollback: true,
  })

  const handleCreate = async () => {
    try {
      await createMutation.mutateAsync(form)
      toast('success', 'A/B test created')
      setShowCreate(false)
      setForm({
        name: '',
        base_model: '',
        variant_model: '',
        traffic_split_percent: 10,
        success_metric: 'cost_efficiency',
        auto_promote: false,
        auto_rollback: true,
      })
    } catch {
      toast('error', 'Failed to create A/B test')
    }
  }

  const handleDelete = async (id: string) => {
    if (!confirm('Delete this A/B test and all its snapshots?')) return
    try {
      await deleteMutation.mutateAsync(id)
      toast('success', 'A/B test deleted')
      if (selectedTestId === id) setSelectedTestId(null)
    } catch {
      toast('error', 'Failed to delete A/B test')
    }
  }

  const handleStart = async (id: string) => {
    try {
      await startMutation.mutateAsync(id)
      toast('success', 'A/B test started')
    } catch {
      toast('error', 'Failed to start A/B test')
    }
  }

  const handleStop = async (id: string) => {
    if (!confirm('Stop this A/B test?')) return
    try {
      await stopMutation.mutateAsync(id)
      toast('success', 'A/B test stopped')
    } catch {
      toast('error', 'Failed to stop A/B test')
    }
  }

  const handlePromote = async (id: string) => {
    if (!confirm('Promote the variant model? This will complete the test.')) return
    try {
      await promoteMutation.mutateAsync(id)
      toast('success', 'Variant promoted successfully')
    } catch {
      toast('error', 'Failed to promote variant')
    }
  }

  const testList = Array.isArray(tests) ? tests : []
  const snapshotList = Array.isArray(snapshots) ? snapshots : []

  if (isLoading) {
    return (
      <div className="space-y-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">A/B Tests</h1>
          <p className="text-gray-600">Compare model performance with controlled experiments</p>
        </div>
        <SkeletonCard />
      </div>
    )
  }

  // Detail view
  if (selectedTestId && testDetail) {
    return (
      <div className="space-y-6">
        <div className="flex items-center gap-4">
          <button
            onClick={() => setSelectedTestId(null)}
            className="p-2 text-gray-500 hover:text-gray-700 hover:bg-gray-100 rounded-lg"
          >
            <ChevronLeftIcon className="w-5 h-5" />
          </button>
          <div className="flex-1">
            <h1 className="text-2xl font-bold text-gray-900">{testDetail.name}</h1>
            <div className="flex items-center gap-3 mt-1">
              <span className={`px-2 py-0.5 text-xs font-medium rounded-full ${statusBadge[testDetail.status] || 'bg-gray-100 text-gray-800'}`}>
                {testDetail.status}
              </span>
              <span className="text-sm text-gray-500">
                {metricLabels[testDetail.success_metric] || testDetail.success_metric}
              </span>
            </div>
          </div>
          <div className="flex gap-2">
            {testDetail.status === 'draft' && (
              <button onClick={() => handleStart(testDetail.id)} className="btn btn-primary">
                <PlayIcon className="w-4 h-4 mr-1" /> Start
              </button>
            )}
            {testDetail.status === 'running' && (
              <>
                <button onClick={() => handlePromote(testDetail.id)} className="btn btn-primary">
                  <ArrowUpIcon className="w-4 h-4 mr-1" /> Promote Variant
                </button>
                <button onClick={() => handleStop(testDetail.id)} className="btn btn-secondary">
                  <StopIcon className="w-4 h-4 mr-1" /> Stop
                </button>
              </>
            )}
            {(testDetail.status === 'completed' || testDetail.status === 'rolled_back') && (
              <button onClick={() => handleStart(testDetail.id)} className="btn btn-secondary">
                <PlayIcon className="w-4 h-4 mr-1" /> Restart
              </button>
            )}
          </div>
        </div>

        {/* Test configuration */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div className="card">
            <h3 className="text-sm font-medium text-gray-500 uppercase tracking-wider mb-4">Base Model</h3>
            <div className="flex items-center gap-3">
              <div className="w-3 h-3 rounded-full bg-blue-500" />
              <code className="text-lg bg-blue-50 px-3 py-1 rounded">{testDetail.base_model}</code>
            </div>
            <p className="text-sm text-gray-500 mt-2">
              {100 - testDetail.traffic_split_percent}% of traffic
            </p>
            {testDetail.latest_snapshot?.base_metrics && (
              <div className="mt-4 pt-4 border-t border-gray-100">
                <h4 className="text-xs font-medium text-gray-500 mb-2">Latest Metrics</h4>
                <div className="space-y-1">
                  {Object.entries(testDetail.latest_snapshot.base_metrics).map(([k, v]) => (
                    <div key={k} className="flex justify-between text-sm">
                      <span className="text-gray-600">{k}</span>
                      <span className="font-medium">{typeof v === 'number' ? v.toFixed(4) : String(v)}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>

          <div className="card">
            <h3 className="text-sm font-medium text-gray-500 uppercase tracking-wider mb-4">Variant Model</h3>
            <div className="flex items-center gap-3">
              <div className="w-3 h-3 rounded-full bg-green-500" />
              <code className="text-lg bg-green-50 px-3 py-1 rounded text-green-800">{testDetail.variant_model}</code>
            </div>
            <p className="text-sm text-gray-500 mt-2">
              {testDetail.traffic_split_percent}% of traffic
            </p>
            {testDetail.latest_snapshot?.variant_metrics && (
              <div className="mt-4 pt-4 border-t border-gray-100">
                <h4 className="text-xs font-medium text-gray-500 mb-2">Latest Metrics</h4>
                <div className="space-y-1">
                  {Object.entries(testDetail.latest_snapshot.variant_metrics).map(([k, v]) => (
                    <div key={k} className="flex justify-between text-sm">
                      <span className="text-gray-600">{k}</span>
                      <span className="font-medium">{typeof v === 'number' ? v.toFixed(4) : String(v)}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Test details */}
        <div className="card">
          <h3 className="text-sm font-medium text-gray-500 uppercase tracking-wider mb-4">Configuration</h3>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
            <div>
              <p className="text-gray-500">Traffic Split</p>
              <p className="font-medium">{testDetail.traffic_split_percent}% variant</p>
            </div>
            <div>
              <p className="text-gray-500">Success Metric</p>
              <p className="font-medium">{metricLabels[testDetail.success_metric] || testDetail.success_metric}</p>
            </div>
            <div>
              <p className="text-gray-500">Auto Promote</p>
              <p className="font-medium">{testDetail.auto_promote ? 'Yes' : 'No'}</p>
            </div>
            <div>
              <p className="text-gray-500">Auto Rollback</p>
              <p className="font-medium">{testDetail.auto_rollback ? 'Yes' : 'No'}</p>
            </div>
            {testDetail.started_at && (
              <div>
                <p className="text-gray-500">Started At</p>
                <p className="font-medium">{new Date(testDetail.started_at).toLocaleString()}</p>
              </div>
            )}
            {testDetail.completed_at && (
              <div>
                <p className="text-gray-500">Completed At</p>
                <p className="font-medium">{new Date(testDetail.completed_at).toLocaleString()}</p>
              </div>
            )}
            {testDetail.created_by && (
              <div>
                <p className="text-gray-500">Created By</p>
                <p className="font-medium">{testDetail.created_by}</p>
              </div>
            )}
            <div>
              <p className="text-gray-500">Created At</p>
              <p className="font-medium">{new Date(testDetail.created_at).toLocaleString()}</p>
            </div>
          </div>
        </div>

        {/* Snapshots */}
        <div className="card">
          <h3 className="text-sm font-medium text-gray-500 uppercase tracking-wider mb-4">
            Snapshots ({snapshotList.length})
          </h3>
          {snapshotList.length === 0 ? (
            <p className="text-gray-500 text-sm">No snapshots recorded yet. Snapshots are created automatically during test runs.</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-gray-200">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Timestamp</th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Recommendation</th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Base Metrics</th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Variant Metrics</th>
                  </tr>
                </thead>
                <tbody className="bg-white divide-y divide-gray-200">
                  {snapshotList.map((snap) => (
                    <tr key={snap.id} className="hover:bg-gray-50">
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-600">
                        {new Date(snap.snapshot_at).toLocaleString()}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap">
                        {snap.recommendation ? (
                          <span className={`px-2 py-0.5 text-xs font-medium rounded-full ${
                            snap.recommendation === 'promoted'
                              ? 'bg-green-100 text-green-800'
                              : snap.recommendation === 'rollback'
                              ? 'bg-red-100 text-red-800'
                              : 'bg-yellow-100 text-yellow-800'
                          }`}>
                            {snap.recommendation}
                          </span>
                        ) : (
                          <span className="text-gray-400 text-sm">--</span>
                        )}
                      </td>
                      <td className="px-6 py-4 text-sm text-gray-600">
                        {snap.base_metrics
                          ? Object.entries(snap.base_metrics).map(([k, v]) => (
                              <span key={k} className="mr-3">
                                <span className="text-gray-400">{k}:</span> {typeof v === 'number' ? v.toFixed(4) : String(v)}
                              </span>
                            ))
                          : '--'}
                      </td>
                      <td className="px-6 py-4 text-sm text-gray-600">
                        {snap.variant_metrics
                          ? Object.entries(snap.variant_metrics).map(([k, v]) => (
                              <span key={k} className="mr-3">
                                <span className="text-gray-400">{k}:</span> {typeof v === 'number' ? v.toFixed(4) : String(v)}
                              </span>
                            ))
                          : '--'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
    )
  }

  // List view
  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">A/B Tests</h1>
          <p className="text-gray-600">Compare model performance with controlled experiments</p>
        </div>
        <button onClick={() => setShowCreate(true)} className="btn btn-primary">
          <PlusIcon className="w-4 h-4 mr-1" />
          New Test
        </button>
      </div>

      {/* Create modal */}
      {showCreate && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg p-6 w-full max-w-lg max-h-[90vh] overflow-y-auto">
            <h2 className="text-xl font-bold mb-4">Create A/B Test</h2>
            <div className="space-y-4">
              <div>
                <label className="label">Test Name</label>
                <input
                  type="text"
                  value={form.name}
                  onChange={(e) => setForm({ ...form, name: e.target.value })}
                  className="input"
                  placeholder="e.g. GPT-4o vs Claude Sonnet cost test"
                />
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="label">Base Model</label>
                  <input
                    type="text"
                    value={form.base_model}
                    onChange={(e) => setForm({ ...form, base_model: e.target.value })}
                    className="input"
                    placeholder="e.g. gpt-4o"
                  />
                </div>
                <div>
                  <label className="label">Variant Model</label>
                  <input
                    type="text"
                    value={form.variant_model}
                    onChange={(e) => setForm({ ...form, variant_model: e.target.value })}
                    className="input"
                    placeholder="e.g. claude-sonnet-4"
                  />
                </div>
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="label">Traffic Split (% to variant)</label>
                  <input
                    type="number"
                    min={1}
                    max={99}
                    value={form.traffic_split_percent ?? 10}
                    onChange={(e) => setForm({ ...form, traffic_split_percent: Number(e.target.value) })}
                    className="input"
                  />
                </div>
                <div>
                  <label className="label">Success Metric</label>
                  <select
                    value={form.success_metric || 'cost_efficiency'}
                    onChange={(e) => setForm({ ...form, success_metric: e.target.value })}
                    className="input"
                  >
                    <option value="cost_efficiency">Cost Efficiency</option>
                    <option value="latency">Latency</option>
                    <option value="error_rate">Error Rate</option>
                    <option value="quality">Quality</option>
                    <option value="throughput">Throughput</option>
                  </select>
                </div>
              </div>
              <div className="grid grid-cols-2 gap-4">
                <label className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    checked={form.auto_promote || false}
                    onChange={(e) => setForm({ ...form, auto_promote: e.target.checked })}
                    className="rounded border-gray-300"
                  />
                  <span className="text-sm text-gray-700">Auto-promote on success</span>
                </label>
                <label className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    checked={form.auto_rollback !== false}
                    onChange={(e) => setForm({ ...form, auto_rollback: e.target.checked })}
                    className="rounded border-gray-300"
                  />
                  <span className="text-sm text-gray-700">Auto-rollback on failure</span>
                </label>
              </div>
              <div className="flex justify-end gap-2 pt-2">
                <button onClick={() => setShowCreate(false)} className="btn btn-secondary">Cancel</button>
                <button
                  onClick={handleCreate}
                  className="btn btn-primary"
                  disabled={!form.name || !form.base_model || !form.variant_model}
                >
                  Create Test
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Test list */}
      {testList.length === 0 ? (
        <div className="card text-center text-gray-500 py-12">
          <BeakerIcon className="w-12 h-12 mx-auto mb-3 text-gray-300" />
          <p className="text-lg font-medium">No A/B tests</p>
          <p className="text-sm mt-1">Create your first experiment to compare model performance.</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {testList.map((test) => (
            <div
              key={test.id}
              className="card cursor-pointer hover:shadow-md transition-shadow"
              onClick={() => setSelectedTestId(test.id)}
            >
              <div className="flex justify-between items-start">
                <div className="flex-1 min-w-0">
                  <h3 className="text-lg font-semibold truncate">{test.name}</h3>
                  <span className={`inline-block mt-1 px-2 py-0.5 text-xs font-medium rounded-full ${statusBadge[test.status] || 'bg-gray-100 text-gray-800'}`}>
                    {test.status}
                  </span>
                </div>
                <button
                  onClick={(e) => {
                    e.stopPropagation()
                    handleDelete(test.id)
                  }}
                  className="p-1 text-gray-400 hover:text-red-600 ml-2"
                  title="Delete"
                >
                  <TrashIcon className="w-4 h-4" />
                </button>
              </div>
              <div className="mt-4 space-y-2">
                <div className="flex items-center gap-2 text-sm">
                  <div className="w-2 h-2 rounded-full bg-blue-500" />
                  <span className="text-gray-600">Base:</span>
                  <code className="bg-gray-100 px-1.5 py-0.5 rounded text-xs">{test.base_model}</code>
                </div>
                <div className="flex items-center gap-2 text-sm">
                  <div className="w-2 h-2 rounded-full bg-green-500" />
                  <span className="text-gray-600">Variant:</span>
                  <code className="bg-green-50 px-1.5 py-0.5 rounded text-xs text-green-800">{test.variant_model}</code>
                </div>
              </div>
              <div className="mt-3 pt-3 border-t border-gray-100 flex justify-between items-center text-sm">
                <span className="text-gray-500">
                  {test.traffic_split_percent}% variant | {metricLabels[test.success_metric] || test.success_metric}
                </span>
                <div className="flex gap-1" onClick={(e) => e.stopPropagation()}>
                  {test.status === 'draft' && (
                    <button
                      onClick={() => handleStart(test.id)}
                      className="p-1 text-gray-400 hover:text-green-600"
                      title="Start"
                    >
                      <PlayIcon className="w-4 h-4" />
                    </button>
                  )}
                  {test.status === 'running' && (
                    <>
                      <button
                        onClick={() => handlePromote(test.id)}
                        className="p-1 text-gray-400 hover:text-green-600"
                        title="Promote variant"
                      >
                        <ArrowUpIcon className="w-4 h-4" />
                      </button>
                      <button
                        onClick={() => handleStop(test.id)}
                        className="p-1 text-gray-400 hover:text-red-600"
                        title="Stop"
                      >
                        <StopIcon className="w-4 h-4" />
                      </button>
                    </>
                  )}
                </div>
              </div>
              {test.created_at && (
                <p className="text-xs text-gray-400 mt-2">
                  Created {new Date(test.created_at).toLocaleDateString()}
                </p>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
