import { useState } from 'react'
import {
  useTeams,
  useCreateTeam,
  useUpdateTeam,
  useDeleteTeam,
  useAddTeamMember,
  useGuardrails,
  useGuardrailAssignments,
  useAssignGuardrail,
  useUnassignGuardrail,
} from '../api/hooks'
import { PlusIcon, UserPlusIcon, UserGroupIcon, PencilIcon, TrashIcon } from '@heroicons/react/24/outline'
import { SkeletonCard } from '../components/Skeleton'
import EmptyState from '../components/EmptyState'
import ConfirmDialog from '../components/ConfirmDialog'
import { useToast } from '../components/Toast'
import type { Team } from '../types'

export default function Teams() {
  const { data: teams, isLoading, error } = useTeams()
  const { data: guardrailConfigs } = useGuardrails()
  const { data: assignments } = useGuardrailAssignments()
  const createTeam = useCreateTeam()
  const updateTeam = useUpdateTeam()
  const deleteTeam = useDeleteTeam()
  const addMember = useAddTeamMember()
  const assignGuardrail = useAssignGuardrail()
  const unassignGuardrail = useUnassignGuardrail()
  const toast = useToast()

  const [showForm, setShowForm] = useState(false)
  const [editing, setEditing] = useState<Team | null>(null)
  const [form, setForm] = useState({
    name: '',
    description: '',
    monthly_budget: '',
    default_model: '',
    guardrail_config_id: '',
  })
  const [deleteId, setDeleteId] = useState<string | null>(null)
  const [addMemberTeam, setAddMemberTeam] = useState<string | null>(null)
  const [memberForm, setMemberForm] = useState({
    user_id: '',
    role: 'member' as 'member' | 'admin',
  })

  const getTeamAssignment = (teamId: string) =>
    (assignments ?? []).find((a) => a.team_id === teamId)

  const openCreate = () => {
    setEditing(null)
    setForm({ name: '', description: '', monthly_budget: '', default_model: '', guardrail_config_id: '' })
    setShowForm(true)
  }

  const openEdit = (team: Team) => {
    const assignment = getTeamAssignment(team.id)
    setEditing(team)
    setForm({
      name: team.name,
      description: team.description || '',
      monthly_budget: team.monthly_budget != null ? String(team.monthly_budget) : '',
      default_model: team.default_model || '',
      guardrail_config_id: assignment?.guardrail_config_id || '',
    })
    setShowForm(true)
  }

  if (isLoading) {
    return (
      <div className="space-y-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Teams</h1>
          <p className="text-gray-600">Manage teams and members</p>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {Array.from({ length: 3 }).map((_, i) => <SkeletonCard key={i} />)}
        </div>
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
    const teamData = {
      name: form.name,
      description: form.description || null,
      monthly_budget: form.monthly_budget ? parseFloat(form.monthly_budget) : null,
      default_model: form.default_model || null,
    }

    try {
      if (editing) {
        await updateTeam.mutateAsync({ id: editing.id, data: teamData })

        // Handle guardrail assignment changes
        const currentAssignment = getTeamAssignment(editing.id)
        const newConfigId = form.guardrail_config_id

        if (currentAssignment && !newConfigId) {
          await unassignGuardrail.mutateAsync({
            configId: currentAssignment.guardrail_config_id,
            teamId: editing.id,
          })
        } else if (newConfigId && currentAssignment?.guardrail_config_id !== newConfigId) {
          if (currentAssignment) {
            await unassignGuardrail.mutateAsync({
              configId: currentAssignment.guardrail_config_id,
              teamId: editing.id,
            })
          }
          await assignGuardrail.mutateAsync({ configId: newConfigId, teamId: editing.id })
        }

        toast('success', 'Team updated successfully')
      } else {
        const created = await createTeam.mutateAsync({
          name: teamData.name,
          description: teamData.description ?? '',
          monthly_budget: teamData.monthly_budget,
          default_model: teamData.default_model ?? '',
        })

        if (form.guardrail_config_id && created.id) {
          await assignGuardrail.mutateAsync({
            configId: form.guardrail_config_id,
            teamId: created.id,
          })
        }

        toast('success', 'Team created successfully')
      }
      setShowForm(false)
      setEditing(null)
    } catch {
      toast('error', editing ? 'Failed to update team' : 'Failed to create team')
    }
  }

  const handleDelete = async () => {
    if (!deleteId) return
    try {
      await deleteTeam.mutateAsync(deleteId)
      toast('success', 'Team deleted successfully')
      setDeleteId(null)
    } catch {
      toast('error', 'Failed to delete team')
    }
  }

  const handleAddMember = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!addMemberTeam) return
    try {
      await addMember.mutateAsync({
        teamId: addMemberTeam,
        data: memberForm,
      })
      toast('success', 'Member added successfully')
      setAddMemberTeam(null)
      setMemberForm({ user_id: '', role: 'member' })
    } catch {
      toast('error', 'Failed to add member')
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Teams</h1>
          <p className="text-gray-600">Manage teams and members</p>
        </div>
        <button onClick={openCreate} className="btn btn-primary">
          <PlusIcon className="w-5 h-5 mr-2" />
          Add Team
        </button>
      </div>

      <ConfirmDialog
        isOpen={!!deleteId}
        onClose={() => setDeleteId(null)}
        onConfirm={handleDelete}
        title="Delete Team?"
        message="This will permanently delete the team, remove all members, and unassign any guardrail profiles."
        confirmLabel="Delete"
        confirmVariant="danger"
      />

      {showForm && (
        <div className="card border-2 border-primary-200">
          <h2 className="text-lg font-semibold mb-4">
            {editing ? `Edit: ${editing.name}` : 'Create Team'}
          </h2>
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
              <div>
                <label className="label">Guardrail Profile</label>
                <select
                  value={form.guardrail_config_id}
                  onChange={(e) =>
                    setForm({ ...form, guardrail_config_id: e.target.value })
                  }
                  className="input"
                >
                  <option value="">None</option>
                  {(guardrailConfigs ?? []).map((cfg) => (
                    <option key={cfg.id} value={cfg.id}>
                      {cfg.name}
                    </option>
                  ))}
                </select>
              </div>
            </div>
            <div className="flex space-x-3">
              <button
                type="submit"
                className="btn btn-primary"
                disabled={createTeam.isPending || updateTeam.isPending}
              >
                {editing ? 'Update' : 'Create Team'}
              </button>
              <button
                type="button"
                onClick={() => { setShowForm(false); setEditing(null) }}
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
                    setMemberForm({ ...memberForm, role: e.target.value as 'member' | 'admin' })
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

      {(!teams || teams.length === 0) ? (
        <EmptyState
          icon={UserGroupIcon}
          title="No teams yet"
          description="Create teams to organize users and manage access."
          actionLabel="Create Team"
          onAction={openCreate}
        />
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {teams.map((team) => {
            const assignment = getTeamAssignment(team.id)
            return (
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
                  {team.monthly_budget != null && (
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
                  {assignment && (
                    <p>
                      <span className="text-gray-500">Guardrail:</span>{' '}
                      <span className="px-1.5 py-0.5 bg-purple-50 text-purple-700 rounded text-xs">
                        {assignment.config_name}
                      </span>
                    </p>
                  )}
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

                <div className="mt-4 flex gap-2">
                  <button
                    onClick={() => openEdit(team)}
                    className="btn btn-secondary flex-1 text-sm"
                  >
                    <PencilIcon className="w-4 h-4 mr-1" />
                    Edit
                  </button>
                  <button
                    onClick={() => setAddMemberTeam(team.id)}
                    className="btn btn-secondary flex-1 text-sm"
                  >
                    <UserPlusIcon className="w-4 h-4 mr-1" />
                    Member
                  </button>
                  <button
                    onClick={() => setDeleteId(team.id)}
                    className="btn bg-red-50 text-red-600 hover:bg-red-100 text-sm px-3"
                  >
                    <TrashIcon className="w-4 h-4" />
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
