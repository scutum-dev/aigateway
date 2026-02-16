import { useState, useMemo } from 'react'
import { useModels, useUpdateModel } from '../api/hooks'
import {
  PencilIcon,
  CheckIcon,
  XMarkIcon,
  MagnifyingGlassIcon,
  ChevronUpIcon,
  ChevronDownIcon,
} from '@heroicons/react/24/outline'
import { SkeletonTable } from '../components/Skeleton'
import EmptyState from '../components/EmptyState'
import { CubeIcon } from '@heroicons/react/24/outline'
import { useToast } from '../components/Toast'
import type { ModelConfig, ModelUpdate } from '../types'

type SortKey = 'model_id' | 'provider' | 'tier' | 'cost_per_1k_input' | 'default_latency_sla_ms'
type SortDir = 'asc' | 'desc'

export default function Models() {
  const { data: models, isLoading, error } = useModels()
  const updateModel = useUpdateModel()
  const toast = useToast()
  const [editingModel, setEditingModel] = useState<string | null>(null)
  const [editForm, setEditForm] = useState<ModelUpdate>({})
  const [search, setSearch] = useState('')
  const [providerFilter, setProviderFilter] = useState<string | null>(null)
  const [sortKey, setSortKey] = useState<SortKey>('model_id')
  const [sortDir, setSortDir] = useState<SortDir>('asc')

  const providers = useMemo(() => {
    if (!models) return []
    return [...new Set(models.map((m) => m.provider))].sort()
  }, [models])

  const filtered = useMemo(() => {
    if (!models) return []
    let result = models

    if (search) {
      const q = search.toLowerCase()
      result = result.filter(
        (m) =>
          m.model_id.toLowerCase().includes(q) ||
          m.provider.toLowerCase().includes(q)
      )
    }

    if (providerFilter) {
      result = result.filter((m) => m.provider === providerFilter)
    }

    result = [...result].sort((a, b) => {
      const aVal = a[sortKey]
      const bVal = b[sortKey]
      if (typeof aVal === 'string' && typeof bVal === 'string') {
        return sortDir === 'asc' ? aVal.localeCompare(bVal) : bVal.localeCompare(aVal)
      }
      return sortDir === 'asc'
        ? (aVal as number) - (bVal as number)
        : (bVal as number) - (aVal as number)
    })

    return result
  }, [models, search, providerFilter, sortKey, sortDir])

  const handleSort = (key: SortKey) => {
    if (sortKey === key) {
      setSortDir(sortDir === 'asc' ? 'desc' : 'asc')
    } else {
      setSortKey(key)
      setSortDir('asc')
    }
  }

  const SortIcon = ({ col }: { col: SortKey }) => {
    if (sortKey !== col) return null
    return sortDir === 'asc' ? (
      <ChevronUpIcon className="w-3 h-3 inline ml-1" />
    ) : (
      <ChevronDownIcon className="w-3 h-3 inline ml-1" />
    )
  }

  if (isLoading) {
    return (
      <div className="space-y-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Models</h1>
          <p className="text-gray-600">Configure model routing and pricing</p>
        </div>
        <SkeletonTable rows={8} cols={6} />
      </div>
    )
  }

  if (error) {
    return (
      <div className="bg-red-50 text-red-700 p-4 rounded-lg">
        Failed to load models
      </div>
    )
  }

  const handleEdit = (model: ModelConfig) => {
    setEditingModel(model.model_id)
    setEditForm({
      tier: model.tier,
      cost_per_1k_input: model.cost_per_1k_input,
      cost_per_1k_output: model.cost_per_1k_output,
      default_latency_sla_ms: model.default_latency_sla_ms,
    })
  }

  const handleSave = async (modelId: string) => {
    try {
      await updateModel.mutateAsync({ modelId, data: editForm })
      toast('success', 'Model updated successfully')
      setEditingModel(null)
    } catch {
      toast('error', 'Failed to update model')
    }
  }

  const handleCancel = () => {
    setEditingModel(null)
    setEditForm({})
  }

  if (!models || models.length === 0) {
    return (
      <div className="space-y-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Models</h1>
          <p className="text-gray-600">Configure model routing and pricing</p>
        </div>
        <EmptyState
          icon={CubeIcon}
          title="No models configured"
          description="Models will appear here once they are added to your LiteLLM configuration."
        />
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Models</h1>
        <p className="text-gray-600">Configure model routing and pricing</p>
      </div>

      {/* Search + Filter */}
      <div className="flex flex-col sm:flex-row gap-4">
        <div className="relative flex-1">
          <MagnifyingGlassIcon className="w-5 h-5 absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
          <input
            type="text"
            placeholder="Search models..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="input pl-10"
          />
        </div>
        <div className="flex flex-wrap gap-2">
          <button
            onClick={() => setProviderFilter(null)}
            className={`px-3 py-1.5 rounded-full text-sm font-medium transition-colors ${
              !providerFilter
                ? 'bg-primary-100 text-primary-700'
                : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
            }`}
          >
            All
          </button>
          {providers.map((p) => (
            <button
              key={p}
              onClick={() => setProviderFilter(providerFilter === p ? null : p)}
              className={`px-3 py-1.5 rounded-full text-sm font-medium capitalize transition-colors ${
                providerFilter === p
                  ? 'bg-primary-100 text-primary-700'
                  : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
              }`}
            >
              {p}
            </button>
          ))}
        </div>
      </div>

      <p className="text-sm text-gray-500">
        Showing {filtered.length} of {models.length} models
      </p>

      <div className="card overflow-hidden">
        <table className="min-w-full divide-y divide-gray-200">
          <thead className="bg-gray-50">
            <tr>
              <th
                className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider cursor-pointer hover:text-gray-700"
                onClick={() => handleSort('model_id')}
              >
                Model <SortIcon col="model_id" />
              </th>
              <th
                className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider cursor-pointer hover:text-gray-700"
                onClick={() => handleSort('provider')}
              >
                Provider <SortIcon col="provider" />
              </th>
              <th
                className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider cursor-pointer hover:text-gray-700"
                onClick={() => handleSort('tier')}
              >
                Tier <SortIcon col="tier" />
              </th>
              <th
                className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider cursor-pointer hover:text-gray-700"
                onClick={() => handleSort('cost_per_1k_input')}
              >
                Cost/1K (In/Out) <SortIcon col="cost_per_1k_input" />
              </th>
              <th
                className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider cursor-pointer hover:text-gray-700"
                onClick={() => handleSort('default_latency_sla_ms')}
              >
                Latency SLA <SortIcon col="default_latency_sla_ms" />
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                Features
              </th>
              <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                Actions
              </th>
            </tr>
          </thead>
          <tbody className="bg-white divide-y divide-gray-200">
            {filtered.map((model) => (
              <tr key={model.model_id}>
                <td className="px-6 py-4 whitespace-nowrap">
                  <span className="font-mono text-sm">{model.model_id}</span>
                </td>
                <td className="px-6 py-4 whitespace-nowrap">
                  <span className="capitalize">{model.provider}</span>
                </td>
                <td className="px-6 py-4 whitespace-nowrap">
                  {editingModel === model.model_id ? (
                    <select
                      value={editForm.tier}
                      onChange={(e) =>
                        setEditForm({ ...editForm, tier: e.target.value })
                      }
                      className="input text-sm py-1"
                    >
                      <option value="free">Free</option>
                      <option value="budget">Budget</option>
                      <option value="standard">Standard</option>
                      <option value="premium">Premium</option>
                    </select>
                  ) : (
                    <span
                      className={`px-2 py-1 rounded text-xs font-medium ${
                        model.tier === 'premium'
                          ? 'bg-purple-100 text-purple-700'
                          : model.tier === 'budget'
                          ? 'bg-green-100 text-green-700'
                          : 'bg-gray-100 text-gray-700'
                      }`}
                    >
                      {model.tier}
                    </span>
                  )}
                </td>
                <td className="px-6 py-4 whitespace-nowrap">
                  {editingModel === model.model_id ? (
                    <div className="flex space-x-2">
                      <input
                        type="number"
                        step="0.0001"
                        value={editForm.cost_per_1k_input}
                        onChange={(e) =>
                          setEditForm({
                            ...editForm,
                            cost_per_1k_input: parseFloat(e.target.value),
                          })
                        }
                        className="input text-sm py-1 w-24"
                      />
                      <input
                        type="number"
                        step="0.0001"
                        value={editForm.cost_per_1k_output}
                        onChange={(e) =>
                          setEditForm({
                            ...editForm,
                            cost_per_1k_output: parseFloat(e.target.value),
                          })
                        }
                        className="input text-sm py-1 w-24"
                      />
                    </div>
                  ) : (
                    <span className="text-sm">
                      ${model.cost_per_1k_input} / ${model.cost_per_1k_output}
                    </span>
                  )}
                </td>
                <td className="px-6 py-4 whitespace-nowrap">
                  {editingModel === model.model_id ? (
                    <input
                      type="number"
                      value={editForm.default_latency_sla_ms}
                      onChange={(e) =>
                        setEditForm({
                          ...editForm,
                          default_latency_sla_ms: parseInt(e.target.value),
                        })
                      }
                      className="input text-sm py-1 w-24"
                    />
                  ) : (
                    <span className="text-sm">
                      {model.default_latency_sla_ms}ms
                    </span>
                  )}
                </td>
                <td className="px-6 py-4 whitespace-nowrap">
                  <div className="flex space-x-1">
                    {model.supports_streaming && (
                      <span className="px-2 py-0.5 bg-blue-100 text-blue-700 text-xs rounded">
                        Stream
                      </span>
                    )}
                    {model.supports_function_calling && (
                      <span className="px-2 py-0.5 bg-green-100 text-green-700 text-xs rounded">
                        Tools
                      </span>
                    )}
                    {model.supports_vision && (
                      <span className="px-2 py-0.5 bg-purple-100 text-purple-700 text-xs rounded">
                        Vision
                      </span>
                    )}
                  </div>
                </td>
                <td className="px-6 py-4 whitespace-nowrap text-right">
                  {editingModel === model.model_id ? (
                    <div className="flex justify-end space-x-2">
                      <button
                        onClick={() => handleSave(model.model_id)}
                        className="p-1 text-green-600 hover:text-green-800"
                      >
                        <CheckIcon className="w-5 h-5" />
                      </button>
                      <button
                        onClick={handleCancel}
                        className="p-1 text-red-600 hover:text-red-800"
                      >
                        <XMarkIcon className="w-5 h-5" />
                      </button>
                    </div>
                  ) : (
                    <button
                      onClick={() => handleEdit(model)}
                      className="p-1 text-gray-400 hover:text-gray-600"
                    >
                      <PencilIcon className="w-5 h-5" />
                    </button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
