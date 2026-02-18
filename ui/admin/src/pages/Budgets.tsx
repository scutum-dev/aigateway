import { useState } from 'react'
import { useBudgets, useCreateBudget, useUpdateBudget, useDeleteBudget } from '../api/hooks'
import { PlusIcon, CurrencyDollarIcon, TrashIcon, PencilIcon } from '@heroicons/react/24/outline'
import { SkeletonCard } from '../components/Skeleton'
import EmptyState from '../components/EmptyState'
import ConfirmDialog from '../components/ConfirmDialog'
import { useToast } from '../components/Toast'
import type { BudgetInfo } from '../types'

export default function Budgets() {
  const { data: budgets, isLoading, error } = useBudgets()
  const createBudget = useCreateBudget()
  const updateBudget = useUpdateBudget()
  const deleteBudget = useDeleteBudget()
  const toast = useToast()

  const [showForm, setShowForm] = useState(false)
  const [editingBudget, setEditingBudget] = useState<BudgetInfo | null>(null)
  const [deleteId, setDeleteId] = useState<string | null>(null)
  const [form, setForm] = useState({
    max_budget: '',
    soft_budget: '',
    max_parallel_requests: '',
    tpm_limit: '',
    rpm_limit: '',
  })

  const resetForm = () => {
    setForm({ max_budget: '', soft_budget: '', max_parallel_requests: '', tpm_limit: '', rpm_limit: '' })
    setEditingBudget(null)
    setShowForm(false)
  }

  const openEdit = (budget: BudgetInfo) => {
    setEditingBudget(budget)
    setForm({
      max_budget: budget.max_budget?.toString() || '',
      soft_budget: budget.soft_budget?.toString() || '',
      max_parallel_requests: budget.max_parallel_requests?.toString() || '',
      tpm_limit: budget.tpm_limit?.toString() || '',
      rpm_limit: budget.rpm_limit?.toString() || '',
    })
    setShowForm(true)
  }

  if (isLoading) {
    return (
      <div className="space-y-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Budgets</h1>
          <p className="text-gray-600">Manage spending limits and rate controls</p>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {Array.from({ length: 3 }).map((_, i) => <SkeletonCard key={i} />)}
        </div>
      </div>
    )
  }

  if (error) {
    return <div className="bg-red-50 text-red-700 p-4 rounded-lg">Failed to load budgets</div>
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    try {
      const payload: Record<string, unknown> = {}
      if (form.max_budget) payload.max_budget = parseFloat(form.max_budget)
      if (form.soft_budget) payload.soft_budget = parseFloat(form.soft_budget)
      if (form.max_parallel_requests) payload.max_parallel_requests = parseInt(form.max_parallel_requests)
      if (form.tpm_limit) payload.tpm_limit = parseInt(form.tpm_limit)
      if (form.rpm_limit) payload.rpm_limit = parseInt(form.rpm_limit)

      if (editingBudget) {
        await updateBudget.mutateAsync({ budget_id: editingBudget.budget_id, ...payload } as any)
        toast('success', 'Budget updated')
      } else {
        await createBudget.mutateAsync(payload as any)
        toast('success', 'Budget created')
      }
      resetForm()
    } catch {
      toast('error', editingBudget ? 'Failed to update budget' : 'Failed to create budget')
    }
  }

  const handleDelete = async () => {
    if (!deleteId) return
    try {
      await deleteBudget.mutateAsync(deleteId)
      toast('success', 'Budget deleted')
    } catch {
      toast('error', 'Failed to delete budget')
    }
    setDeleteId(null)
  }

  const budgetList = Array.isArray(budgets) ? budgets : []

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Budgets</h1>
          <p className="text-gray-600">
            {budgetList.length} budget{budgetList.length !== 1 ? 's' : ''} configured
          </p>
        </div>
        <button onClick={() => { resetForm(); setShowForm(true) }} className="btn btn-primary">
          <PlusIcon className="w-5 h-5 mr-2" />
          Create Budget
        </button>
      </div>

      <ConfirmDialog
        isOpen={!!deleteId}
        onClose={() => setDeleteId(null)}
        onConfirm={handleDelete}
        title="Delete Budget?"
        message="This will remove the budget. Teams or keys using this budget will lose their limits."
        confirmLabel="Delete Budget"
        confirmVariant="danger"
      />

      {showForm && (
        <div className="card">
          <h2 className="text-lg font-semibold mb-4">
            {editingBudget ? 'Edit Budget' : 'Create Budget'}
          </h2>
          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              <div>
                <label htmlFor="budget-max" className="label">Max Budget ($)</label>
                <input
                  id="budget-max"
                  type="number"
                  step="0.01"
                  min="0"
                  value={form.max_budget}
                  onChange={(e) => setForm({ ...form, max_budget: e.target.value })}
                  className="input"
                  placeholder="e.g., 100.00"
                />
              </div>
              <div>
                <label htmlFor="budget-soft" className="label">Soft Budget ($)</label>
                <input
                  id="budget-soft"
                  type="number"
                  step="0.01"
                  min="0"
                  value={form.soft_budget}
                  onChange={(e) => setForm({ ...form, soft_budget: e.target.value })}
                  className="input"
                  placeholder="Alert threshold"
                />
              </div>
              <div>
                <label htmlFor="budget-parallel" className="label">Max Parallel Requests</label>
                <input
                  id="budget-parallel"
                  type="number"
                  min="1"
                  value={form.max_parallel_requests}
                  onChange={(e) => setForm({ ...form, max_parallel_requests: e.target.value })}
                  className="input"
                  placeholder="Optional"
                />
              </div>
              <div>
                <label htmlFor="budget-tpm" className="label">TPM Limit</label>
                <input
                  id="budget-tpm"
                  type="number"
                  min="1"
                  value={form.tpm_limit}
                  onChange={(e) => setForm({ ...form, tpm_limit: e.target.value })}
                  className="input"
                  placeholder="Tokens per minute"
                />
              </div>
              <div>
                <label htmlFor="budget-rpm" className="label">RPM Limit</label>
                <input
                  id="budget-rpm"
                  type="number"
                  min="1"
                  value={form.rpm_limit}
                  onChange={(e) => setForm({ ...form, rpm_limit: e.target.value })}
                  className="input"
                  placeholder="Requests per minute"
                />
              </div>
            </div>
            <div className="flex space-x-3">
              <button type="submit" className="btn btn-primary" disabled={createBudget.isPending || updateBudget.isPending}>
                {editingBudget ? 'Update Budget' : 'Create Budget'}
              </button>
              <button type="button" onClick={resetForm} className="btn btn-secondary">
                Cancel
              </button>
            </div>
          </form>
        </div>
      )}

      {budgetList.length === 0 ? (
        <EmptyState
          icon={CurrencyDollarIcon}
          title="No budgets configured"
          description="Create budgets to control spending limits and rate controls for teams and keys."
          actionLabel="Create Budget"
          onAction={() => setShowForm(true)}
        />
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {budgetList.map((budget) => {
            const spendPercent = budget.max_budget
              ? Math.min(100, (0 / budget.max_budget) * 100) // spend not available in budget list
              : 0
            return (
              <div key={budget.budget_id} className="card">
                <div className="flex items-start justify-between mb-3">
                  <div className="flex items-center">
                    <div className="p-2 bg-green-100 rounded-lg mr-3">
                      <CurrencyDollarIcon className="w-5 h-5 text-green-600" />
                    </div>
                    <div>
                      <h3 className="font-semibold">Budget</h3>
                      <code className="text-xs text-gray-400">{budget.budget_id}</code>
                    </div>
                  </div>
                </div>

                {/* Progress bar */}
                {budget.max_budget !== null && budget.max_budget !== undefined && (
                  <div className="mb-3">
                    <div className="flex justify-between text-sm mb-1">
                      <span className="text-gray-500">Spend</span>
                      <span className="font-medium">${budget.max_budget.toFixed(2)} limit</span>
                    </div>
                    <div className="w-full bg-gray-200 rounded-full h-2">
                      <div
                        className={`h-2 rounded-full ${spendPercent > 80 ? 'bg-red-500' : spendPercent > 50 ? 'bg-amber-500' : 'bg-green-500'}`}
                        style={{ width: `${spendPercent}%` }}
                      />
                    </div>
                  </div>
                )}

                <div className="space-y-2 text-sm">
                  {budget.soft_budget !== null && budget.soft_budget !== undefined && (
                    <div className="flex justify-between">
                      <span className="text-gray-500">Soft Budget</span>
                      <span className="font-medium">${budget.soft_budget.toFixed(2)}</span>
                    </div>
                  )}
                  {budget.max_parallel_requests !== null && budget.max_parallel_requests !== undefined && (
                    <div className="flex justify-between">
                      <span className="text-gray-500">Max Parallel</span>
                      <span className="font-medium">{budget.max_parallel_requests}</span>
                    </div>
                  )}
                  {budget.tpm_limit !== null && budget.tpm_limit !== undefined && (
                    <div className="flex justify-between">
                      <span className="text-gray-500">TPM Limit</span>
                      <span className="font-medium">{budget.tpm_limit.toLocaleString()}</span>
                    </div>
                  )}
                  {budget.rpm_limit !== null && budget.rpm_limit !== undefined && (
                    <div className="flex justify-between">
                      <span className="text-gray-500">RPM Limit</span>
                      <span className="font-medium">{budget.rpm_limit.toLocaleString()}</span>
                    </div>
                  )}
                </div>

                <div className="flex gap-2 mt-4 pt-3 border-t border-gray-100">
                  <button
                    onClick={() => openEdit(budget)}
                    className="btn btn-secondary text-xs flex-1"
                  >
                    <PencilIcon className="w-3.5 h-3.5 mr-1" />
                    Edit
                  </button>
                  <button
                    onClick={() => setDeleteId(budget.budget_id)}
                    className="btn btn-secondary text-xs text-red-600 hover:text-red-800 flex-1"
                  >
                    <TrashIcon className="w-3.5 h-3.5 mr-1" />
                    Delete
                  </button>
                </div>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
