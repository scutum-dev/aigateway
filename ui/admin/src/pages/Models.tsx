import { useState, useMemo } from 'react'
import { useModels, useCreateModel, useDeleteModel } from '../api/hooks'
import { PlusIcon, CubeIcon, TrashIcon, MagnifyingGlassIcon } from '@heroicons/react/24/outline'
import { SkeletonTable } from '../components/Skeleton'
import EmptyState from '../components/EmptyState'
import ConfirmDialog from '../components/ConfirmDialog'
import { useToast } from '../components/Toast'
import type { ModelInfo } from '../types'

function extractProvider(model: ModelInfo): string {
  const params = model.litellm_params || {}
  const litellmModel = (params.model as string) || ''
  if (litellmModel.includes('/')) {
    return litellmModel.split('/')[0]
  }
  const customProvider = params.custom_llm_provider as string
  if (customProvider) return customProvider
  if (litellmModel.startsWith('gpt-') || litellmModel.startsWith('o1') || litellmModel.startsWith('o3')) return 'openai'
  if (litellmModel.startsWith('claude-')) return 'anthropic'
  if (litellmModel.startsWith('gemini')) return 'google'
  return 'unknown'
}

export default function Models() {
  const { data, isLoading, error } = useModels()
  const createModel = useCreateModel()
  const deleteModel = useDeleteModel()
  const toast = useToast()

  const [search, setSearch] = useState('')
  const [providerFilter, setProviderFilter] = useState('')
  const [showForm, setShowForm] = useState(false)
  const [deleteId, setDeleteId] = useState<string | null>(null)
  const [form, setForm] = useState({ model_name: '', model: '', custom_llm_provider: '' })

  const models = data?.data || []

  const providers = useMemo(() => {
    const set = new Set(models.map(extractProvider))
    return Array.from(set).sort()
  }, [models])

  const filtered = useMemo(() => {
    return models.filter((m) => {
      const matchesSearch = !search || m.model_name.toLowerCase().includes(search.toLowerCase())
      const matchesProvider = !providerFilter || extractProvider(m) === providerFilter
      return matchesSearch && matchesProvider
    })
  }, [models, search, providerFilter])

  if (isLoading) {
    return (
      <div className="space-y-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Models</h1>
          <p className="text-gray-600">Manage LLM model configurations</p>
        </div>
        <SkeletonTable rows={8} cols={4} />
      </div>
    )
  }

  if (error) {
    return <div className="bg-red-50 text-red-700 p-4 rounded-lg">Failed to load models</div>
  }

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault()
    try {
      const litellm_params: Record<string, unknown> = { model: form.model }
      if (form.custom_llm_provider) {
        litellm_params.custom_llm_provider = form.custom_llm_provider
      }
      await createModel.mutateAsync({ model_name: form.model_name, litellm_params })
      toast('success', 'Model added')
      setForm({ model_name: '', model: '', custom_llm_provider: '' })
      setShowForm(false)
    } catch {
      toast('error', 'Failed to add model')
    }
  }

  const handleDelete = async () => {
    if (!deleteId) return
    try {
      await deleteModel.mutateAsync(deleteId)
      toast('success', 'Model deleted')
    } catch {
      toast('error', 'Failed to delete model')
    }
    setDeleteId(null)
  }

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Models</h1>
          <p className="text-gray-600">
            {models.length} model{models.length !== 1 ? 's' : ''} configured
          </p>
        </div>
        <button onClick={() => setShowForm(true)} className="btn btn-primary">
          <PlusIcon className="w-5 h-5 mr-2" />
          Add Model
        </button>
      </div>

      <ConfirmDialog
        isOpen={!!deleteId}
        onClose={() => setDeleteId(null)}
        onConfirm={handleDelete}
        title="Delete Model?"
        message="This will remove the model from LiteLLM. Existing keys referencing this model may stop working."
        confirmLabel="Delete Model"
        confirmVariant="danger"
      />

      {showForm && (
        <div className="card">
          <h2 className="text-lg font-semibold mb-4">Add Model</h2>
          <form onSubmit={handleCreate} className="space-y-4">
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div>
                <label htmlFor="model-name" className="label">Model Name (alias)</label>
                <input
                  id="model-name"
                  type="text"
                  value={form.model_name}
                  onChange={(e) => setForm({ ...form, model_name: e.target.value })}
                  className="input"
                  required
                  placeholder="e.g., gpt-4o"
                />
              </div>
              <div>
                <label htmlFor="model-id" className="label">Provider Model ID</label>
                <input
                  id="model-id"
                  type="text"
                  value={form.model}
                  onChange={(e) => setForm({ ...form, model: e.target.value })}
                  className="input"
                  required
                  placeholder="e.g., openai/gpt-4o"
                />
              </div>
              <div>
                <label htmlFor="model-provider" className="label">Custom Provider (optional)</label>
                <input
                  id="model-provider"
                  type="text"
                  value={form.custom_llm_provider}
                  onChange={(e) => setForm({ ...form, custom_llm_provider: e.target.value })}
                  className="input"
                  placeholder="e.g., openai"
                />
              </div>
            </div>
            <div className="flex space-x-3">
              <button type="submit" className="btn btn-primary" disabled={createModel.isPending}>
                {createModel.isPending ? 'Adding...' : 'Add Model'}
              </button>
              <button type="button" onClick={() => setShowForm(false)} className="btn btn-secondary">
                Cancel
              </button>
            </div>
          </form>
        </div>
      )}

      {models.length === 0 ? (
        <EmptyState
          icon={CubeIcon}
          title="No models configured"
          description="Add models to route LLM requests through the gateway."
          actionLabel="Add Model"
          onAction={() => setShowForm(true)}
        />
      ) : (
        <>
          {/* Search and filter */}
          <div className="flex gap-4">
            <div className="relative flex-1">
              <MagnifyingGlassIcon className="w-5 h-5 absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
              <input
                type="text"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="input pl-10"
                placeholder="Search models..."
              />
            </div>
            <select
              value={providerFilter}
              onChange={(e) => setProviderFilter(e.target.value)}
              className="input w-48"
            >
              <option value="">All providers</option>
              {providers.map((p) => (
                <option key={p} value={p}>{p}</option>
              ))}
            </select>
          </div>

          {/* Table */}
          <div className="card overflow-hidden">
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-gray-200">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Model Name</th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Provider</th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Provider Model</th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Mode</th>
                    <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">Actions</th>
                  </tr>
                </thead>
                <tbody className="bg-white divide-y divide-gray-200">
                  {filtered.map((model) => {
                    const provider = extractProvider(model)
                    const modelId = (model.model_info as Record<string, unknown>)?.id as string || ''
                    const mode = (model.model_info as Record<string, unknown>)?.mode as string || 'chat'
                    return (
                      <tr key={modelId || model.model_name} className="hover:bg-gray-50">
                        <td className="px-6 py-4 whitespace-nowrap">
                          <span className="font-medium text-gray-900">{model.model_name}</span>
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap">
                          <span className="px-2 py-1 text-xs rounded-full bg-blue-100 text-blue-700">{provider}</span>
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                          {(model.litellm_params?.model as string) || '-'}
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">{mode}</td>
                        <td className="px-6 py-4 whitespace-nowrap text-right">
                          <button
                            onClick={() => setDeleteId(modelId)}
                            className="text-red-500 hover:text-red-700"
                            title="Delete model"
                          >
                            <TrashIcon className="w-4 h-4" />
                          </button>
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
            {filtered.length === 0 && (
              <p className="text-center text-gray-500 py-8">No models match your search</p>
            )}
          </div>
        </>
      )}
    </div>
  )
}
