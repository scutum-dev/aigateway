import { useState } from 'react'
import { useModels, useUpdateModel } from '../api/hooks'
import { PencilIcon, CheckIcon, XMarkIcon } from '@heroicons/react/24/outline'

export default function Models() {
  const { data: models, isLoading, error } = useModels()
  const updateModel = useUpdateModel()
  const [editingModel, setEditingModel] = useState<string | null>(null)
  const [editForm, setEditForm] = useState<any>({})

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
        Failed to load models
      </div>
    )
  }

  const handleEdit = (model: any) => {
    setEditingModel(model.model_id)
    setEditForm({
      tier: model.tier,
      cost_per_1k_input: model.cost_per_1k_input,
      cost_per_1k_output: model.cost_per_1k_output,
      default_latency_sla_ms: model.default_latency_sla_ms,
    })
  }

  const handleSave = async (modelId: string) => {
    await updateModel.mutateAsync({ modelId, data: editForm })
    setEditingModel(null)
  }

  const handleCancel = () => {
    setEditingModel(null)
    setEditForm({})
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Models</h1>
        <p className="text-gray-600">Configure model routing and pricing</p>
      </div>

      <div className="card overflow-hidden">
        <table className="min-w-full divide-y divide-gray-200">
          <thead className="bg-gray-50">
            <tr>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                Model
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                Provider
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                Tier
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                Cost/1K (In/Out)
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                Latency SLA
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
            {models?.map((model: any) => (
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
