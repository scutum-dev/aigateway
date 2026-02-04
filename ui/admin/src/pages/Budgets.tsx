import { useState } from 'react'
import { useBudgets, useCreateBudget, useUpdateBudget } from '../api/hooks'
import { PlusIcon, PencilIcon, XMarkIcon } from '@heroicons/react/24/outline'

interface BudgetForm {
  name: string
  entity_type: string
  entity_id: string
  monthly_limit: number
  soft_limit_percent: number
  hard_limit_percent: number
  alert_email: string
  is_active?: boolean
}

const emptyForm: BudgetForm = {
  name: '',
  entity_type: 'team',
  entity_id: '',
  monthly_limit: 100,
  soft_limit_percent: 0.8,
  hard_limit_percent: 1.0,
  alert_email: '',
}

export default function Budgets() {
  const { data: budgets, isLoading, error } = useBudgets()
  const createBudget = useCreateBudget()
  const updateBudget = useUpdateBudget()
  const [showForm, setShowForm] = useState(false)
  const [editingId, setEditingId] = useState<string | null>(null)
  const [form, setForm] = useState<BudgetForm>(emptyForm)

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
        Failed to load budgets
      </div>
    )
  }

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault()
    await createBudget.mutateAsync(form)
    setShowForm(false)
    setForm(emptyForm)
  }

  const handleEdit = (budget: any) => {
    setEditingId(budget.id)
    setForm({
      name: budget.name,
      entity_type: budget.entity_type,
      entity_id: budget.entity_id || '',
      monthly_limit: budget.monthly_limit,
      soft_limit_percent: budget.soft_limit_percent,
      hard_limit_percent: budget.hard_limit_percent,
      alert_email: budget.alert_email || '',
      is_active: budget.is_active,
    })
  }

  const handleUpdate = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!editingId) return
    await updateBudget.mutateAsync({
      id: editingId,
      data: {
        name: form.name,
        monthly_limit: form.monthly_limit,
        soft_limit_percent: form.soft_limit_percent,
        hard_limit_percent: form.hard_limit_percent,
        alert_email: form.alert_email || null,
        is_active: form.is_active,
      },
    })
    setEditingId(null)
    setForm(emptyForm)
  }

  const handleCancel = () => {
    setShowForm(false)
    setEditingId(null)
    setForm(emptyForm)
  }

  const getUtilization = (budget: any) => {
    return (budget.current_spend / budget.monthly_limit) * 100
  }

  const getUtilizationColor = (utilization: number, soft: number, hard: number) => {
    if (utilization >= hard * 100) return 'bg-red-500'
    if (utilization >= soft * 100) return 'bg-yellow-500'
    return 'bg-green-500'
  }

  const renderForm = (isEdit: boolean) => (
    <div className="card">
      <div className="flex justify-between items-center mb-4">
        <h2 className="text-lg font-semibold">
          {isEdit ? 'Edit Budget' : 'Create Budget'}
        </h2>
        <button onClick={handleCancel} className="text-gray-400 hover:text-gray-600">
          <XMarkIcon className="w-5 h-5" />
        </button>
      </div>
      <form onSubmit={isEdit ? handleUpdate : handleCreate} className="space-y-4">
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="label">Name</label>
            <input
              type="text"
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
              className="input"
              required
            />
          </div>
          <div>
            <label className="label">Entity Type</label>
            <select
              value={form.entity_type}
              onChange={(e) => setForm({ ...form, entity_type: e.target.value })}
              className="input"
              disabled={isEdit}
            >
              <option value="global">Global</option>
              <option value="team">Team</option>
              <option value="user">User</option>
            </select>
          </div>
          <div>
            <label className="label">Entity ID</label>
            <input
              type="text"
              value={form.entity_id}
              onChange={(e) => setForm({ ...form, entity_id: e.target.value })}
              className="input"
              placeholder="Leave empty for global"
              disabled={isEdit}
            />
          </div>
          <div>
            <label className="label">Monthly Limit ($)</label>
            <input
              type="number"
              value={form.monthly_limit}
              onChange={(e) =>
                setForm({ ...form, monthly_limit: parseFloat(e.target.value) })
              }
              className="input"
              required
            />
          </div>
          <div>
            <label className="label">Soft Limit (%)</label>
            <input
              type="number"
              step="0.01"
              min="0"
              max="1"
              value={form.soft_limit_percent}
              onChange={(e) =>
                setForm({
                  ...form,
                  soft_limit_percent: parseFloat(e.target.value),
                })
              }
              className="input"
            />
          </div>
          <div>
            <label className="label">Hard Limit (%)</label>
            <input
              type="number"
              step="0.01"
              min="0"
              max="1"
              value={form.hard_limit_percent}
              onChange={(e) =>
                setForm({
                  ...form,
                  hard_limit_percent: parseFloat(e.target.value),
                })
              }
              className="input"
            />
          </div>
          <div>
            <label className="label">Alert Email</label>
            <input
              type="email"
              value={form.alert_email}
              onChange={(e) => setForm({ ...form, alert_email: e.target.value })}
              className="input"
            />
          </div>
          {isEdit && (
            <div className="flex items-center">
              <label className="flex items-center space-x-2 cursor-pointer">
                <input
                  type="checkbox"
                  checked={form.is_active}
                  onChange={(e) => setForm({ ...form, is_active: e.target.checked })}
                  className="w-4 h-4 rounded border-gray-300"
                />
                <span className="label mb-0">Active</span>
              </label>
            </div>
          )}
        </div>
        <div className="flex space-x-3">
          <button
            type="submit"
            className="btn btn-primary"
            disabled={createBudget.isPending || updateBudget.isPending}
          >
            {createBudget.isPending || updateBudget.isPending
              ? 'Saving...'
              : isEdit
              ? 'Update Budget'
              : 'Create Budget'}
          </button>
          <button type="button" onClick={handleCancel} className="btn btn-secondary">
            Cancel
          </button>
        </div>
      </form>
    </div>
  )

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Budgets</h1>
          <p className="text-gray-600">Manage cost limits and alerts</p>
        </div>
        {!showForm && !editingId && (
          <button onClick={() => setShowForm(true)} className="btn btn-primary">
            <PlusIcon className="w-5 h-5 mr-2" />
            Add Budget
          </button>
        )}
      </div>

      {showForm && renderForm(false)}
      {editingId && renderForm(true)}

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {budgets?.map((budget: any) => {
          const utilization = getUtilization(budget)
          return (
            <div key={budget.id} className="card">
              <div className="flex justify-between items-start mb-4">
                <div>
                  <h3 className="font-semibold">{budget.name}</h3>
                  <p className="text-sm text-gray-500 capitalize">
                    {budget.entity_type}
                    {budget.entity_id && `: ${budget.entity_id}`}
                  </p>
                </div>
                <div className="flex items-center space-x-2">
                  <button
                    onClick={() => handleEdit(budget)}
                    className="text-gray-400 hover:text-primary-600 p-1"
                    title="Edit budget"
                  >
                    <PencilIcon className="w-4 h-4" />
                  </button>
                  <span
                    className={`px-2 py-1 rounded text-xs ${
                      budget.is_active
                        ? 'bg-green-100 text-green-700'
                        : 'bg-gray-100 text-gray-700'
                    }`}
                  >
                    {budget.is_active ? 'Active' : 'Inactive'}
                  </span>
                </div>
              </div>

              <div className="mb-4">
                <div className="flex justify-between text-sm mb-1">
                  <span>
                    ${budget.current_spend?.toFixed(2)} / $
                    {budget.monthly_limit?.toFixed(2)}
                  </span>
                  <span>{utilization.toFixed(1)}%</span>
                </div>
                <div className="w-full bg-gray-200 rounded-full h-2">
                  <div
                    className={`h-2 rounded-full ${getUtilizationColor(
                      utilization,
                      budget.soft_limit_percent,
                      budget.hard_limit_percent
                    )}`}
                    style={{ width: `${Math.min(utilization, 100)}%` }}
                  ></div>
                </div>
              </div>

              <div className="text-sm text-gray-500 space-y-1">
                <p>
                  Soft limit: {(budget.soft_limit_percent * 100).toFixed(0)}%
                </p>
                <p>
                  Hard limit: {(budget.hard_limit_percent * 100).toFixed(0)}%
                </p>
                {budget.alert_email && <p>Alert: {budget.alert_email}</p>}
              </div>
            </div>
          )
        })}
      </div>

      {(!budgets || budgets.length === 0) && (
        <div className="text-center py-12 text-gray-500">
          No budgets configured yet
        </div>
      )}
    </div>
  )
}
