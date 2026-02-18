import { useState } from 'react'
import {
  useTeams,
  useCreateTeam,
  useUpdateTeam,
  useDeleteTeam,
  useAddTeamMember,
  useDeleteTeamMember,
  useGuardrailAssignments,
  useGuardrails,
  useAssignGuardrail,
  useUnassignGuardrail,
} from '../api/hooks'
import { PlusIcon, UserGroupIcon, TrashIcon, PencilIcon, UserPlusIcon } from '@heroicons/react/24/outline'
import { SkeletonCard } from '../components/Skeleton'
import EmptyState from '../components/EmptyState'
import ConfirmDialog from '../components/ConfirmDialog'
import { useToast } from '../components/Toast'
import type { TeamInfo } from '../types'

export default function Teams() {
  const { data: teams, isLoading, error } = useTeams()
  const createTeam = useCreateTeam()
  const updateTeam = useUpdateTeam()
  const deleteTeam = useDeleteTeam()
  const addMember = useAddTeamMember()
  const deleteMember = useDeleteTeamMember()
  const { data: assignments } = useGuardrailAssignments()
  const { data: guardrails } = useGuardrails()
  const assignGuardrail = useAssignGuardrail()
  const unassignGuardrail = useUnassignGuardrail()
  const toast = useToast()

  const [showForm, setShowForm] = useState(false)
  const [editingTeam, setEditingTeam] = useState<TeamInfo | null>(null)
  const [deleteId, setDeleteId] = useState<string | null>(null)
  const [memberTeamId, setMemberTeamId] = useState<string | null>(null)
  const [guardrailTeamId, setGuardrailTeamId] = useState<string | null>(null)
  const [form, setForm] = useState({ team_alias: '', max_budget: '', models: '' })
  const [memberForm, setMemberForm] = useState({ user_id: '', role: 'user' })
  const [selectedGuardrailId, setSelectedGuardrailId] = useState('')

  const resetForm = () => {
    setForm({ team_alias: '', max_budget: '', models: '' })
    setEditingTeam(null)
    setShowForm(false)
  }

  const openEdit = (team: TeamInfo) => {
    setEditingTeam(team)
    setForm({
      team_alias: team.team_alias || '',
      max_budget: team.max_budget?.toString() || '',
      models: team.models?.join(', ') || '',
    })
    setShowForm(true)
  }

  if (isLoading) {
    return (
      <div className="space-y-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Teams</h1>
          <p className="text-gray-600">Manage teams and member access</p>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {Array.from({ length: 3 }).map((_, i) => <SkeletonCard key={i} />)}
        </div>
      </div>
    )
  }

  if (error) {
    return <div className="bg-red-50 text-red-700 p-4 rounded-lg">Failed to load teams</div>
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    try {
      const payload: Record<string, unknown> = { team_alias: form.team_alias }
      if (form.max_budget) payload.max_budget = parseFloat(form.max_budget)
      if (form.models) payload.models = form.models.split(',').map((m) => m.trim())

      if (editingTeam) {
        await updateTeam.mutateAsync({ team_id: editingTeam.team_id, ...payload } as any)
        toast('success', 'Team updated')
      } else {
        await createTeam.mutateAsync(payload as any)
        toast('success', 'Team created')
      }
      resetForm()
    } catch {
      toast('error', editingTeam ? 'Failed to update team' : 'Failed to create team')
    }
  }

  const handleDelete = async () => {
    if (!deleteId) return
    try {
      await deleteTeam.mutateAsync([deleteId])
      toast('success', 'Team deleted')
    } catch {
      toast('error', 'Failed to delete team')
    }
    setDeleteId(null)
  }

  const handleAddMember = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!memberTeamId) return
    try {
      await addMember.mutateAsync({
        teamId: memberTeamId,
        member: { role: memberForm.role, user_id: memberForm.user_id },
      })
      toast('success', 'Member added')
      setMemberForm({ user_id: '', role: 'user' })
      setMemberTeamId(null)
    } catch {
      toast('error', 'Failed to add member')
    }
  }

  const handleRemoveMember = async (teamId: string, userId: string) => {
    try {
      await deleteMember.mutateAsync({ teamId, userId })
      toast('success', 'Member removed')
    } catch {
      toast('error', 'Failed to remove member')
    }
  }

  const handleAssignGuardrail = async () => {
    if (!guardrailTeamId || !selectedGuardrailId) return
    try {
      await assignGuardrail.mutateAsync({ configId: selectedGuardrailId, teamId: guardrailTeamId })
      toast('success', 'Guardrail assigned')
      setSelectedGuardrailId('')
      setGuardrailTeamId(null)
    } catch {
      toast('error', 'Failed to assign guardrail')
    }
  }

  const handleUnassignGuardrail = async (configId: string, teamId: string) => {
    try {
      await unassignGuardrail.mutateAsync({ configId, teamId })
      toast('success', 'Guardrail unassigned')
    } catch {
      toast('error', 'Failed to unassign guardrail')
    }
  }

  const teamList = Array.isArray(teams) ? teams : []

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Teams</h1>
          <p className="text-gray-600">
            {teamList.length} team{teamList.length !== 1 ? 's' : ''}
          </p>
        </div>
        <button onClick={() => { resetForm(); setShowForm(true) }} className="btn btn-primary">
          <PlusIcon className="w-5 h-5 mr-2" />
          Create Team
        </button>
      </div>

      <ConfirmDialog
        isOpen={!!deleteId}
        onClose={() => setDeleteId(null)}
        onConfirm={handleDelete}
        title="Delete Team?"
        message="This will delete the team and disassociate all members. This action cannot be undone."
        confirmLabel="Delete Team"
        confirmVariant="danger"
      />

      {showForm && (
        <div className="card">
          <h2 className="text-lg font-semibold mb-4">
            {editingTeam ? 'Edit Team' : 'Create Team'}
          </h2>
          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div>
                <label htmlFor="team-name" className="label">Team Name</label>
                <input
                  id="team-name"
                  type="text"
                  value={form.team_alias}
                  onChange={(e) => setForm({ ...form, team_alias: e.target.value })}
                  className="input"
                  required
                  placeholder="e.g., Engineering"
                />
              </div>
              <div>
                <label htmlFor="team-budget" className="label">Max Budget ($)</label>
                <input
                  id="team-budget"
                  type="number"
                  step="0.01"
                  min="0"
                  value={form.max_budget}
                  onChange={(e) => setForm({ ...form, max_budget: e.target.value })}
                  className="input"
                  placeholder="Optional"
                />
              </div>
              <div>
                <label htmlFor="team-models" className="label">Allowed Models (comma-separated)</label>
                <input
                  id="team-models"
                  type="text"
                  value={form.models}
                  onChange={(e) => setForm({ ...form, models: e.target.value })}
                  className="input"
                  placeholder="e.g., gpt-4o, claude-3.5-sonnet"
                />
              </div>
            </div>
            <div className="flex space-x-3">
              <button type="submit" className="btn btn-primary" disabled={createTeam.isPending || updateTeam.isPending}>
                {editingTeam ? 'Update Team' : 'Create Team'}
              </button>
              <button type="button" onClick={resetForm} className="btn btn-secondary">
                Cancel
              </button>
            </div>
          </form>
        </div>
      )}

      {/* Add Member Form */}
      {memberTeamId && (
        <div className="card">
          <h2 className="text-lg font-semibold mb-4">Add Member</h2>
          <form onSubmit={handleAddMember} className="space-y-4">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label htmlFor="member-user-id" className="label">User ID</label>
                <input
                  id="member-user-id"
                  type="text"
                  value={memberForm.user_id}
                  onChange={(e) => setMemberForm({ ...memberForm, user_id: e.target.value })}
                  className="input"
                  required
                  placeholder="user@example.com"
                />
              </div>
              <div>
                <label htmlFor="member-role" className="label">Role</label>
                <select
                  id="member-role"
                  value={memberForm.role}
                  onChange={(e) => setMemberForm({ ...memberForm, role: e.target.value })}
                  className="input"
                >
                  <option value="user">User</option>
                  <option value="admin">Admin</option>
                </select>
              </div>
            </div>
            <div className="flex space-x-3">
              <button type="submit" className="btn btn-primary" disabled={addMember.isPending}>
                {addMember.isPending ? 'Adding...' : 'Add Member'}
              </button>
              <button type="button" onClick={() => setMemberTeamId(null)} className="btn btn-secondary">
                Cancel
              </button>
            </div>
          </form>
        </div>
      )}

      {/* Assign Guardrail Form */}
      {guardrailTeamId && (
        <div className="card">
          <h2 className="text-lg font-semibold mb-4">Assign Guardrail</h2>
          <div className="flex items-end gap-4">
            <div className="flex-1">
              <label htmlFor="guardrail-select" className="label">Guardrail Config</label>
              <select
                id="guardrail-select"
                value={selectedGuardrailId}
                onChange={(e) => setSelectedGuardrailId(e.target.value)}
                className="input"
              >
                <option value="">Select a guardrail...</option>
                {guardrails?.map((g) => (
                  <option key={g.id} value={g.id}>{g.name}</option>
                ))}
              </select>
            </div>
            <button
              onClick={handleAssignGuardrail}
              className="btn btn-primary"
              disabled={!selectedGuardrailId || assignGuardrail.isPending}
            >
              Assign
            </button>
            <button onClick={() => setGuardrailTeamId(null)} className="btn btn-secondary">
              Cancel
            </button>
          </div>
        </div>
      )}

      {teamList.length === 0 ? (
        <EmptyState
          icon={UserGroupIcon}
          title="No teams"
          description="Create teams to organize users and manage access."
          actionLabel="Create Team"
          onAction={() => setShowForm(true)}
        />
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {teamList.map((team) => {
            const teamAssignments = assignments?.filter((a) => a.team_id === team.team_id) || []
            return (
              <div key={team.team_id} className="card">
                <div className="flex items-start justify-between mb-3">
                  <div className="flex items-center">
                    <div className="p-2 bg-indigo-100 rounded-lg mr-3">
                      <UserGroupIcon className="w-5 h-5 text-indigo-600" />
                    </div>
                    <div>
                      <h3 className="font-semibold">{team.team_alias || team.team_id}</h3>
                      <code className="text-xs text-gray-400">{team.team_id}</code>
                    </div>
                  </div>
                </div>

                <div className="space-y-2 text-sm">
                  <div className="flex justify-between">
                    <span className="text-gray-500">Spend</span>
                    <span className="font-medium">${(team.spend || 0).toFixed(4)}</span>
                  </div>
                  {team.max_budget !== null && team.max_budget !== undefined && (
                    <div className="flex justify-between">
                      <span className="text-gray-500">Budget</span>
                      <span className="font-medium">${team.max_budget.toFixed(2)}</span>
                    </div>
                  )}

                  {/* Members */}
                  {team.members_with_roles && team.members_with_roles.length > 0 && (
                    <div>
                      <span className="text-gray-500 text-xs">Members:</span>
                      <div className="space-y-1 mt-1">
                        {team.members_with_roles.map((m) => (
                          <div key={m.user_id} className="flex items-center justify-between">
                            <span className="text-xs">
                              {m.user_id}
                              <span className="ml-1 text-gray-400">({m.role})</span>
                            </span>
                            <button
                              onClick={() => handleRemoveMember(team.team_id, m.user_id)}
                              className="text-red-400 hover:text-red-600"
                              title="Remove member"
                            >
                              <TrashIcon className="w-3 h-3" />
                            </button>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Models */}
                  {team.models && team.models.length > 0 && (
                    <div>
                      <span className="text-gray-500 text-xs">Models:</span>
                      <div className="flex flex-wrap gap-1 mt-1">
                        {team.models.map((m) => (
                          <span key={m} className="px-2 py-0.5 bg-blue-100 text-blue-700 rounded text-xs">{m}</span>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Guardrail Assignments */}
                  {teamAssignments.length > 0 && (
                    <div>
                      <span className="text-gray-500 text-xs">Guardrails:</span>
                      <div className="space-y-1 mt-1">
                        {teamAssignments.map((a) => (
                          <div key={a.guardrail_config_id} className="flex items-center justify-between">
                            <span className="px-2 py-0.5 bg-green-100 text-green-700 rounded text-xs">{a.config_name}</span>
                            <button
                              onClick={() => handleUnassignGuardrail(a.guardrail_config_id, team.team_id)}
                              className="text-red-400 hover:text-red-600"
                              title="Unassign guardrail"
                            >
                              <TrashIcon className="w-3 h-3" />
                            </button>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>

                <div className="flex gap-2 mt-4 pt-3 border-t border-gray-100">
                  <button
                    onClick={() => setMemberTeamId(team.team_id)}
                    className="btn btn-secondary text-xs flex-1"
                  >
                    <UserPlusIcon className="w-3.5 h-3.5 mr-1" />
                    Add Member
                  </button>
                  <button
                    onClick={() => setGuardrailTeamId(team.team_id)}
                    className="btn btn-secondary text-xs flex-1"
                  >
                    Guardrail
                  </button>
                  <button
                    onClick={() => openEdit(team)}
                    className="btn btn-secondary text-xs flex-1"
                  >
                    <PencilIcon className="w-3.5 h-3.5 mr-1" />
                    Edit
                  </button>
                  <button
                    onClick={() => setDeleteId(team.team_id)}
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
