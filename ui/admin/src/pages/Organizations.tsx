import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  useOrganizations,
  useCreateOrganization,
  useDeleteOrganization,
} from '../api/hooks'
import { PlusIcon, BuildingOffice2Icon, TrashIcon } from '@heroicons/react/24/outline'
import { SkeletonCard } from '../components/Skeleton'
import EmptyState from '../components/EmptyState'
import ConfirmDialog from '../components/ConfirmDialog'
import { useToast } from '../components/Toast'

export default function Organizations() {
  const { data: organizations, isLoading, error } = useOrganizations()
  const createOrg = useCreateOrganization()
  const deleteOrg = useDeleteOrganization()
  const navigate = useNavigate()
  const toast = useToast()

  const [showForm, setShowForm] = useState(false)
  const [deleteId, setDeleteId] = useState<string | null>(null)
  const [form, setForm] = useState({
    name: '',
    slug: '',
    description: '',
    max_budget: '',
    allowed_models: '',
  })

  const resetForm = () => {
    setForm({ name: '', slug: '', description: '', max_budget: '', allowed_models: '' })
    setShowForm(false)
  }

  const generateSlug = (name: string) => {
    return name.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/(^-|-$)/g, '')
  }

  if (isLoading) {
    return (
      <div className="space-y-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Organizations</h1>
          <p className="text-gray-600">Manage organizations and multi-tenancy</p>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {Array.from({ length: 3 }).map((_, i) => <SkeletonCard key={i} />)}
        </div>
      </div>
    )
  }

  if (error) {
    return <div className="bg-red-50 text-red-700 p-4 rounded-lg">Failed to load organizations</div>
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    try {
      const payload: Record<string, unknown> = {
        name: form.name,
        slug: form.slug || generateSlug(form.name),
      }
      if (form.description) payload.description = form.description
      if (form.max_budget) payload.max_budget = parseFloat(form.max_budget)
      if (form.allowed_models) payload.allowed_models = form.allowed_models.split(',').map((m) => m.trim())

      await createOrg.mutateAsync(payload as any)
      toast('success', 'Organization created')
      resetForm()
    } catch {
      toast('error', 'Failed to create organization')
    }
  }

  const handleDelete = async () => {
    if (!deleteId) return
    try {
      await deleteOrg.mutateAsync(deleteId)
      toast('success', 'Organization deleted')
    } catch {
      toast('error', 'Failed to delete organization')
    }
    setDeleteId(null)
  }

  const orgList = Array.isArray(organizations) ? organizations : []

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Organizations</h1>
          <p className="text-gray-600">
            {orgList.length} organization{orgList.length !== 1 ? 's' : ''}
          </p>
        </div>
        <button onClick={() => { resetForm(); setShowForm(true) }} className="btn btn-primary">
          <PlusIcon className="w-5 h-5 mr-2" />
          Create Organization
        </button>
      </div>

      <ConfirmDialog
        isOpen={!!deleteId}
        onClose={() => setDeleteId(null)}
        onConfirm={handleDelete}
        title="Delete Organization?"
        message="This will delete the organization, all business units, team assignments, and memberships. This action cannot be undone."
        confirmLabel="Delete Organization"
        confirmVariant="danger"
      />

      {showForm && (
        <div className="card">
          <h2 className="text-lg font-semibold mb-4">Create Organization</h2>
          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              <div>
                <label htmlFor="org-name" className="label">Name</label>
                <input
                  id="org-name"
                  type="text"
                  value={form.name}
                  onChange={(e) => setForm({ ...form, name: e.target.value, slug: generateSlug(e.target.value) })}
                  className="input"
                  required
                  placeholder="e.g., Acme Corp"
                />
              </div>
              <div>
                <label htmlFor="org-slug" className="label">Slug</label>
                <input
                  id="org-slug"
                  type="text"
                  value={form.slug}
                  onChange={(e) => setForm({ ...form, slug: e.target.value })}
                  className="input"
                  required
                  placeholder="e.g., acme-corp"
                />
              </div>
              <div>
                <label htmlFor="org-budget" className="label">Max Budget ($)</label>
                <input
                  id="org-budget"
                  type="number"
                  step="0.01"
                  min="0"
                  value={form.max_budget}
                  onChange={(e) => setForm({ ...form, max_budget: e.target.value })}
                  className="input"
                  placeholder="Optional"
                />
              </div>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label htmlFor="org-description" className="label">Description</label>
                <input
                  id="org-description"
                  type="text"
                  value={form.description}
                  onChange={(e) => setForm({ ...form, description: e.target.value })}
                  className="input"
                  placeholder="Optional description"
                />
              </div>
              <div>
                <label htmlFor="org-models" className="label">Allowed Models (comma-separated)</label>
                <input
                  id="org-models"
                  type="text"
                  value={form.allowed_models}
                  onChange={(e) => setForm({ ...form, allowed_models: e.target.value })}
                  className="input"
                  placeholder="e.g., gpt-4o, claude-3.5-sonnet"
                />
              </div>
            </div>
            <div className="flex space-x-3">
              <button type="submit" className="btn btn-primary" disabled={createOrg.isPending}>
                {createOrg.isPending ? 'Creating...' : 'Create Organization'}
              </button>
              <button type="button" onClick={resetForm} className="btn btn-secondary">
                Cancel
              </button>
            </div>
          </form>
        </div>
      )}

      {orgList.length === 0 ? (
        <EmptyState
          icon={BuildingOffice2Icon}
          title="No organizations"
          description="Create organizations to enable multi-tenancy and manage teams across business units."
          actionLabel="Create Organization"
          onAction={() => setShowForm(true)}
        />
      ) : (
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Name</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Slug</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">BUs</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Teams</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Members</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Budget</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Status</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Actions</th>
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-200">
              {orgList.map((org) => (
                <tr
                  key={org.id}
                  className="hover:bg-gray-50 cursor-pointer"
                  onClick={() => navigate(`/organizations/${org.id}`)}
                >
                  <td className="px-6 py-4 whitespace-nowrap">
                    <div className="flex items-center">
                      <div className="p-2 bg-indigo-100 rounded-lg mr-3">
                        <BuildingOffice2Icon className="w-5 h-5 text-indigo-600" />
                      </div>
                      <div>
                        <div className="text-sm font-medium text-gray-900">{org.name}</div>
                        {org.description && (
                          <div className="text-sm text-gray-500 truncate max-w-xs">{org.description}</div>
                        )}
                      </div>
                    </div>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap">
                    <code className="text-sm text-gray-600 bg-gray-100 px-2 py-1 rounded">{org.slug}</code>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">{org.bu_count || 0}</td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">{org.team_count || 0}</td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">{org.member_count || 0}</td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                    {org.max_budget != null ? `$${org.max_budget.toFixed(2)}` : '--'}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap">
                    <span className={`px-2 py-1 inline-flex text-xs leading-5 font-semibold rounded-full ${
                      org.is_active ? 'bg-green-100 text-green-800' : 'bg-gray-100 text-gray-800'
                    }`}>
                      {org.is_active ? 'Active' : 'Inactive'}
                    </span>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm" onClick={(e) => e.stopPropagation()}>
                    <button
                      onClick={() => setDeleteId(org.id)}
                      className="text-red-600 hover:text-red-900"
                      title="Delete organization"
                    >
                      <TrashIcon className="w-4 h-4" />
                    </button>
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
