import { useState } from 'react'
import { useTeams, useCreateTeam, useAddTeamMember } from '../api/hooks'
import { PlusIcon, UserPlusIcon } from '@heroicons/react/24/outline'

export default function Teams() {
  const { data: teams, isLoading, error } = useTeams()
  const createTeam = useCreateTeam()
  const addMember = useAddTeamMember()
  const [showForm, setShowForm] = useState(false)
  const [form, setForm] = useState({
    name: '',
    description: '',
    monthly_budget: '',
    default_model: '',
  })
  const [addMemberTeam, setAddMemberTeam] = useState<string | null>(null)
  const [memberForm, setMemberForm] = useState({
    user_id: '',
    role: 'member',
  })

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
        Failed to load teams
      </div>
    )
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    await createTeam.mutateAsync({
      ...form,
      monthly_budget: form.monthly_budget
        ? parseFloat(form.monthly_budget)
        : null,
    })
    setShowForm(false)
    setForm({
      name: '',
      description: '',
      monthly_budget: '',
      default_model: '',
    })
  }

  const handleAddMember = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!addMemberTeam) return
    await addMember.mutateAsync({
      teamId: addMemberTeam,
      data: memberForm,
    })
    setAddMemberTeam(null)
    setMemberForm({ user_id: '', role: 'member' })
  }

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Teams</h1>
          <p className="text-gray-600">Manage teams and members</p>
        </div>
        <button onClick={() => setShowForm(true)} className="btn btn-primary">
          <PlusIcon className="w-5 h-5 mr-2" />
          Add Team
        </button>
      </div>

      {showForm && (
        <div className="card">
          <h2 className="text-lg font-semibold mb-4">Create Team</h2>
          <form onSubmit={handleSubmit} className="space-y-4">
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
                <label className="label">Monthly Budget ($)</label>
                <input
                  type="number"
                  value={form.monthly_budget}
                  onChange={(e) =>
                    setForm({ ...form, monthly_budget: e.target.value })
                  }
                  className="input"
                  placeholder="Optional"
                />
              </div>
              <div className="col-span-2">
                <label className="label">Description</label>
                <textarea
                  value={form.description}
                  onChange={(e) =>
                    setForm({ ...form, description: e.target.value })
                  }
                  className="input"
                  rows={2}
                />
              </div>
              <div>
                <label className="label">Default Model</label>
                <input
                  type="text"
                  value={form.default_model}
                  onChange={(e) =>
                    setForm({ ...form, default_model: e.target.value })
                  }
                  className="input"
                  placeholder="e.g., gpt-4o-mini"
                />
              </div>
            </div>
            <div className="flex space-x-3">
              <button type="submit" className="btn btn-primary">
                Create Team
              </button>
              <button
                type="button"
                onClick={() => setShowForm(false)}
                className="btn btn-secondary"
              >
                Cancel
              </button>
            </div>
          </form>
        </div>
      )}

      {addMemberTeam && (
        <div className="card">
          <h2 className="text-lg font-semibold mb-4">Add Team Member</h2>
          <form onSubmit={handleAddMember} className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="label">User ID</label>
                <input
                  type="text"
                  value={memberForm.user_id}
                  onChange={(e) =>
                    setMemberForm({ ...memberForm, user_id: e.target.value })
                  }
                  className="input"
                  required
                />
              </div>
              <div>
                <label className="label">Role</label>
                <select
                  value={memberForm.role}
                  onChange={(e) =>
                    setMemberForm({ ...memberForm, role: e.target.value })
                  }
                  className="input"
                >
                  <option value="member">Member</option>
                  <option value="admin">Admin</option>
                </select>
              </div>
            </div>
            <div className="flex space-x-3">
              <button type="submit" className="btn btn-primary">
                Add Member
              </button>
              <button
                type="button"
                onClick={() => setAddMemberTeam(null)}
                className="btn btn-secondary"
              >
                Cancel
              </button>
            </div>
          </form>
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {teams?.map((team: any) => (
          <div key={team.id} className="card">
            <div className="flex justify-between items-start mb-4">
              <div>
                <h3 className="font-semibold">{team.name}</h3>
                {team.description && (
                  <p className="text-sm text-gray-500">{team.description}</p>
                )}
              </div>
              <span
                className={`px-2 py-1 rounded text-xs ${
                  team.is_active
                    ? 'bg-green-100 text-green-700'
                    : 'bg-gray-100 text-gray-700'
                }`}
              >
                {team.is_active ? 'Active' : 'Inactive'}
              </span>
            </div>

            <div className="space-y-2 text-sm">
              {team.monthly_budget && (
                <p>
                  <span className="text-gray-500">Budget:</span> $
                  {team.monthly_budget.toFixed(2)}/mo
                </p>
              )}
              {team.default_model && (
                <p>
                  <span className="text-gray-500">Default Model:</span>{' '}
                  {team.default_model}
                </p>
              )}
              <p>
                <span className="text-gray-500">Members:</span>{' '}
                {team.members?.length || 0}
              </p>
            </div>

            {team.members && team.members.length > 0 && (
              <div className="mt-4 pt-4 border-t border-gray-100">
                <p className="text-xs text-gray-500 mb-2">Members:</p>
                <div className="flex flex-wrap gap-1">
                  {team.members.slice(0, 5).map((member: string) => (
                    <span
                      key={member}
                      className="px-2 py-1 bg-gray-100 rounded text-xs"
                    >
                      {member}
                    </span>
                  ))}
                  {team.members.length > 5 && (
                    <span className="px-2 py-1 text-gray-500 text-xs">
                      +{team.members.length - 5} more
                    </span>
                  )}
                </div>
              </div>
            )}

            <button
              onClick={() => setAddMemberTeam(team.id)}
              className="mt-4 btn btn-secondary w-full text-sm"
            >
              <UserPlusIcon className="w-4 h-4 mr-2" />
              Add Member
            </button>
          </div>
        ))}
      </div>

      {(!teams || teams.length === 0) && (
        <div className="text-center py-12 text-gray-500">
          No teams configured yet
        </div>
      )}
    </div>
  )
}
