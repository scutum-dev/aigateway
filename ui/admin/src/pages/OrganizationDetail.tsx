import { useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import {
  useOrganization,
  useUpdateOrganization,
  useBusinessUnits,
  useCreateBusinessUnit,
  useOrgMembers,
} from '../api/hooks'
import { organizationsApi } from '../api/client'
import {
  BuildingOffice2Icon,
  PlusIcon,
  TrashIcon,
  ArrowLeftIcon,
  UserGroupIcon,
  CubeIcon,
  ShieldCheckIcon,
} from '@heroicons/react/24/outline'
import { useToast } from '../components/Toast'
import type { BusinessUnit, OrgMembership, TeamHierarchy, SSOConfig } from '../types'
import { useQuery, useQueryClient } from '@tanstack/react-query'

type TabName = 'overview' | 'business-units' | 'teams' | 'members' | 'sso'

export default function OrganizationDetail() {
  const { orgId } = useParams<{ orgId: string }>()
  const navigate = useNavigate()
  const toast = useToast()
  const queryClient = useQueryClient()

  const { data: org, isLoading, error } = useOrganization(orgId || null)
  const updateOrg = useUpdateOrganization()
  const { data: businessUnits } = useBusinessUnits(orgId || null)
  const createBU = useCreateBusinessUnit()
  const { data: members } = useOrgMembers(orgId || null)
  const { data: teams } = useQuery<TeamHierarchy[]>({
    queryKey: ['organizations', orgId, 'teams'],
    queryFn: () => organizationsApi.listTeams(orgId!),
    enabled: !!orgId,
  })
  const { data: ssoConfig } = useQuery<SSOConfig>({
    queryKey: ['organizations', orgId, 'sso'],
    queryFn: () => organizationsApi.getSSO(orgId!),
    enabled: !!orgId,
    retry: false,
  })

  const [activeTab, setActiveTab] = useState<TabName>('overview')
  const [showBUForm, setShowBUForm] = useState(false)
  const [buForm, setBUForm] = useState({ name: '', slug: '', description: '', max_budget: '' })
  const [showTeamForm, setShowTeamForm] = useState(false)
  const [teamForm, setTeamForm] = useState({ team_id: '', bu_id: '' })
  const [showMemberForm, setShowMemberForm] = useState(false)
  const [memberForm, setMemberForm] = useState({ user_id: '', role: 'member' })
  const [editForm, setEditForm] = useState({ name: '', description: '', max_budget: '', allowed_models: '' })
  const [editing, setEditing] = useState(false)
  const [ssoForm, setSSOForm] = useState({
    provider_type: 'oidc',
    provider_name: '',
    client_id: '',
    client_secret: '',
    issuer_url: '',
  })

  if (isLoading) {
    return (
      <div className="space-y-6">
        <div className="animate-pulse bg-gray-200 h-8 w-64 rounded"></div>
        <div className="animate-pulse bg-gray-200 h-64 rounded-lg"></div>
      </div>
    )
  }

  if (error || !org) {
    return <div className="bg-red-50 text-red-700 p-4 rounded-lg">Organization not found</div>
  }

  const startEditing = () => {
    setEditForm({
      name: org.name,
      description: org.description || '',
      max_budget: org.max_budget?.toString() || '',
      allowed_models: org.allowed_models?.join(', ') || '',
    })
    setEditing(true)
  }

  const handleUpdateOrg = async (e: React.FormEvent) => {
    e.preventDefault()
    try {
      const data: Record<string, unknown> = {}
      if (editForm.name !== org.name) data.name = editForm.name
      if (editForm.description !== (org.description || '')) data.description = editForm.description || null
      if (editForm.max_budget !== (org.max_budget?.toString() || '')) {
        data.max_budget = editForm.max_budget ? parseFloat(editForm.max_budget) : null
      }
      const models = editForm.allowed_models ? editForm.allowed_models.split(',').map(m => m.trim()) : null
      data.allowed_models = models

      if (Object.keys(data).length > 0) {
        await updateOrg.mutateAsync({ id: orgId!, data: data as any })
        toast('success', 'Organization updated')
      }
      setEditing(false)
    } catch {
      toast('error', 'Failed to update organization')
    }
  }

  const handleCreateBU = async (e: React.FormEvent) => {
    e.preventDefault()
    try {
      await createBU.mutateAsync({
        orgId: orgId!,
        data: {
          name: buForm.name,
          slug: buForm.slug || buForm.name.toLowerCase().replace(/[^a-z0-9]+/g, '-'),
          description: buForm.description || undefined,
          max_budget: buForm.max_budget ? parseFloat(buForm.max_budget) : undefined,
        },
      })
      toast('success', 'Business unit created')
      setBUForm({ name: '', slug: '', description: '', max_budget: '' })
      setShowBUForm(false)
    } catch {
      toast('error', 'Failed to create business unit')
    }
  }

  const handleDeleteBU = async (buId: string) => {
    try {
      await organizationsApi.deleteBU(orgId!, buId)
      queryClient.invalidateQueries({ queryKey: ['organizations'] })
      toast('success', 'Business unit deleted')
    } catch {
      toast('error', 'Failed to delete business unit')
    }
  }

  const handleAssignTeam = async (e: React.FormEvent) => {
    e.preventDefault()
    try {
      await organizationsApi.assignTeam(orgId!, teamForm.team_id, teamForm.bu_id || undefined)
      queryClient.invalidateQueries({ queryKey: ['organizations', orgId, 'teams'] })
      toast('success', 'Team assigned')
      setTeamForm({ team_id: '', bu_id: '' })
      setShowTeamForm(false)
    } catch {
      toast('error', 'Failed to assign team')
    }
  }

  const handleRemoveTeam = async (teamId: string) => {
    try {
      await organizationsApi.removeTeam(orgId!, teamId)
      queryClient.invalidateQueries({ queryKey: ['organizations', orgId, 'teams'] })
      toast('success', 'Team removed')
    } catch {
      toast('error', 'Failed to remove team')
    }
  }

  const handleAddMember = async (e: React.FormEvent) => {
    e.preventDefault()
    try {
      await organizationsApi.addMember(orgId!, {
        user_id: memberForm.user_id,
        role: memberForm.role,
      })
      queryClient.invalidateQueries({ queryKey: ['organizations', orgId, 'members'] })
      toast('success', 'Member added')
      setMemberForm({ user_id: '', role: 'member' })
      setShowMemberForm(false)
    } catch {
      toast('error', 'Failed to add member')
    }
  }

  const handleRemoveMember = async (userId: string) => {
    try {
      await organizationsApi.removeMember(orgId!, userId)
      queryClient.invalidateQueries({ queryKey: ['organizations', orgId, 'members'] })
      toast('success', 'Member removed')
    } catch {
      toast('error', 'Failed to remove member')
    }
  }

  const handleSaveSSO = async (e: React.FormEvent) => {
    e.preventDefault()
    try {
      await organizationsApi.updateSSO(orgId!, ssoForm)
      queryClient.invalidateQueries({ queryKey: ['organizations', orgId, 'sso'] })
      toast('success', 'SSO configuration saved')
    } catch {
      toast('error', 'Failed to save SSO configuration')
    }
  }

  const handleDisableSSO = async () => {
    try {
      await organizationsApi.deleteSSO(orgId!)
      queryClient.invalidateQueries({ queryKey: ['organizations', orgId, 'sso'] })
      toast('success', 'SSO disabled')
    } catch {
      toast('error', 'Failed to disable SSO')
    }
  }

  const tabs: { name: string; key: TabName; icon: typeof BuildingOffice2Icon }[] = [
    { name: 'Overview', key: 'overview', icon: BuildingOffice2Icon },
    { name: 'Business Units', key: 'business-units', icon: CubeIcon },
    { name: 'Teams', key: 'teams', icon: UserGroupIcon },
    { name: 'Members', key: 'members', icon: UserGroupIcon },
    { name: 'SSO', key: 'sso', icon: ShieldCheckIcon },
  ]

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-4">
        <button onClick={() => navigate('/organizations')} className="text-gray-500 hover:text-gray-700">
          <ArrowLeftIcon className="w-5 h-5" />
        </button>
        <div>
          <h1 className="text-2xl font-bold text-gray-900">{org.name}</h1>
          <p className="text-gray-500">
            <code className="text-sm bg-gray-100 px-2 py-0.5 rounded">{org.slug}</code>
          </p>
        </div>
      </div>

      {/* Tabs */}
      <div className="border-b border-gray-200">
        <nav className="flex space-x-8">
          {tabs.map((tab) => (
            <button
              key={tab.key}
              onClick={() => setActiveTab(tab.key)}
              className={`flex items-center px-1 py-4 border-b-2 text-sm font-medium ${
                activeTab === tab.key
                  ? 'border-indigo-500 text-indigo-600'
                  : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
              }`}
            >
              <tab.icon className="w-4 h-4 mr-2" />
              {tab.name}
            </button>
          ))}
        </nav>
      </div>

      {/* Overview Tab */}
      {activeTab === 'overview' && (
        <div className="card">
          {editing ? (
            <form onSubmit={handleUpdateOrg} className="space-y-4">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <label htmlFor="edit-name" className="label">Name</label>
                  <input id="edit-name" type="text" value={editForm.name} onChange={(e) => setEditForm({ ...editForm, name: e.target.value })} className="input" required />
                </div>
                <div>
                  <label htmlFor="edit-budget" className="label">Max Budget ($)</label>
                  <input id="edit-budget" type="number" step="0.01" value={editForm.max_budget} onChange={(e) => setEditForm({ ...editForm, max_budget: e.target.value })} className="input" placeholder="Optional" />
                </div>
              </div>
              <div>
                <label htmlFor="edit-desc" className="label">Description</label>
                <input id="edit-desc" type="text" value={editForm.description} onChange={(e) => setEditForm({ ...editForm, description: e.target.value })} className="input" />
              </div>
              <div>
                <label htmlFor="edit-models" className="label">Allowed Models (comma-separated)</label>
                <input id="edit-models" type="text" value={editForm.allowed_models} onChange={(e) => setEditForm({ ...editForm, allowed_models: e.target.value })} className="input" />
              </div>
              <div className="flex space-x-3">
                <button type="submit" className="btn btn-primary" disabled={updateOrg.isPending}>Save</button>
                <button type="button" onClick={() => setEditing(false)} className="btn btn-secondary">Cancel</button>
              </div>
            </form>
          ) : (
            <div className="space-y-4">
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <div>
                  <span className="text-sm text-gray-500">Business Units</span>
                  <p className="text-2xl font-semibold">{org.bu_count || 0}</p>
                </div>
                <div>
                  <span className="text-sm text-gray-500">Teams</span>
                  <p className="text-2xl font-semibold">{org.team_count || 0}</p>
                </div>
                <div>
                  <span className="text-sm text-gray-500">Members</span>
                  <p className="text-2xl font-semibold">{org.member_count || 0}</p>
                </div>
                <div>
                  <span className="text-sm text-gray-500">Max Budget</span>
                  <p className="text-2xl font-semibold">{org.max_budget != null ? `$${org.max_budget.toFixed(2)}` : '--'}</p>
                </div>
              </div>
              {org.description && <p className="text-gray-600">{org.description}</p>}
              {org.allowed_models && org.allowed_models.length > 0 && (
                <div>
                  <span className="text-sm text-gray-500">Allowed Models:</span>
                  <div className="flex flex-wrap gap-1 mt-1">
                    {org.allowed_models.map((m) => (
                      <span key={m} className="px-2 py-0.5 bg-blue-100 text-blue-700 rounded text-xs">{m}</span>
                    ))}
                  </div>
                </div>
              )}
              <button onClick={startEditing} className="btn btn-secondary">Edit Organization</button>
            </div>
          )}
        </div>
      )}

      {/* Business Units Tab */}
      {activeTab === 'business-units' && (
        <div className="space-y-4">
          <div className="flex justify-between items-center">
            <h2 className="text-lg font-semibold">Business Units</h2>
            <button onClick={() => setShowBUForm(true)} className="btn btn-primary">
              <PlusIcon className="w-4 h-4 mr-1" /> Add BU
            </button>
          </div>

          {showBUForm && (
            <div className="card">
              <form onSubmit={handleCreateBU} className="space-y-4">
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                  <div>
                    <label htmlFor="bu-name" className="label">Name</label>
                    <input id="bu-name" type="text" value={buForm.name} onChange={(e) => setBUForm({ ...buForm, name: e.target.value })} className="input" required placeholder="e.g., Engineering" />
                  </div>
                  <div>
                    <label htmlFor="bu-slug" className="label">Slug</label>
                    <input id="bu-slug" type="text" value={buForm.slug} onChange={(e) => setBUForm({ ...buForm, slug: e.target.value })} className="input" placeholder="Auto-generated" />
                  </div>
                  <div>
                    <label htmlFor="bu-budget" className="label">Max Budget ($)</label>
                    <input id="bu-budget" type="number" step="0.01" value={buForm.max_budget} onChange={(e) => setBUForm({ ...buForm, max_budget: e.target.value })} className="input" placeholder="Optional" />
                  </div>
                </div>
                <div className="flex space-x-3">
                  <button type="submit" className="btn btn-primary" disabled={createBU.isPending}>Create</button>
                  <button type="button" onClick={() => setShowBUForm(false)} className="btn btn-secondary">Cancel</button>
                </div>
              </form>
            </div>
          )}

          {(!businessUnits || businessUnits.length === 0) ? (
            <div className="card text-center text-gray-500 py-8">No business units yet</div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {businessUnits.map((bu: BusinessUnit) => (
                <div key={bu.id} className="card">
                  <div className="flex justify-between items-start">
                    <div>
                      <h3 className="font-semibold">{bu.name}</h3>
                      <code className="text-xs text-gray-400">{bu.slug}</code>
                    </div>
                    <button onClick={() => handleDeleteBU(bu.id)} className="text-red-500 hover:text-red-700">
                      <TrashIcon className="w-4 h-4" />
                    </button>
                  </div>
                  {bu.description && <p className="text-sm text-gray-600 mt-2">{bu.description}</p>}
                  {bu.max_budget != null && (
                    <p className="text-sm text-gray-500 mt-1">Budget: ${bu.max_budget.toFixed(2)}</p>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Teams Tab */}
      {activeTab === 'teams' && (
        <div className="space-y-4">
          <div className="flex justify-between items-center">
            <h2 className="text-lg font-semibold">Assigned Teams</h2>
            <button onClick={() => setShowTeamForm(true)} className="btn btn-primary">
              <PlusIcon className="w-4 h-4 mr-1" /> Assign Team
            </button>
          </div>

          {showTeamForm && (
            <div className="card">
              <form onSubmit={handleAssignTeam} className="space-y-4">
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div>
                    <label htmlFor="team-id" className="label">Team ID</label>
                    <input id="team-id" type="text" value={teamForm.team_id} onChange={(e) => setTeamForm({ ...teamForm, team_id: e.target.value })} className="input" required placeholder="Team ID from LiteLLM" />
                  </div>
                  <div>
                    <label htmlFor="team-bu" className="label">Business Unit (optional)</label>
                    <select id="team-bu" value={teamForm.bu_id} onChange={(e) => setTeamForm({ ...teamForm, bu_id: e.target.value })} className="input">
                      <option value="">None</option>
                      {businessUnits?.map((bu: BusinessUnit) => (
                        <option key={bu.id} value={bu.id}>{bu.name}</option>
                      ))}
                    </select>
                  </div>
                </div>
                <div className="flex space-x-3">
                  <button type="submit" className="btn btn-primary">Assign</button>
                  <button type="button" onClick={() => setShowTeamForm(false)} className="btn btn-secondary">Cancel</button>
                </div>
              </form>
            </div>
          )}

          {(!teams || teams.length === 0) ? (
            <div className="card text-center text-gray-500 py-8">No teams assigned</div>
          ) : (
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-gray-200">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Team ID</th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Business Unit</th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Actions</th>
                  </tr>
                </thead>
                <tbody className="bg-white divide-y divide-gray-200">
                  {teams.map((t: TeamHierarchy) => (
                    <tr key={t.team_id}>
                      <td className="px-6 py-4 text-sm font-medium">{t.team_id}</td>
                      <td className="px-6 py-4 text-sm text-gray-500">{t.bu_id || '--'}</td>
                      <td className="px-6 py-4">
                        <button onClick={() => handleRemoveTeam(t.team_id)} className="text-red-600 hover:text-red-900">
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
      )}

      {/* Members Tab */}
      {activeTab === 'members' && (
        <div className="space-y-4">
          <div className="flex justify-between items-center">
            <h2 className="text-lg font-semibold">Members</h2>
            <button onClick={() => setShowMemberForm(true)} className="btn btn-primary">
              <PlusIcon className="w-4 h-4 mr-1" /> Add Member
            </button>
          </div>

          {showMemberForm && (
            <div className="card">
              <form onSubmit={handleAddMember} className="space-y-4">
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div>
                    <label htmlFor="member-uid" className="label">User ID</label>
                    <input id="member-uid" type="text" value={memberForm.user_id} onChange={(e) => setMemberForm({ ...memberForm, user_id: e.target.value })} className="input" required placeholder="UUID of the user" />
                  </div>
                  <div>
                    <label htmlFor="member-role" className="label">Role</label>
                    <select id="member-role" value={memberForm.role} onChange={(e) => setMemberForm({ ...memberForm, role: e.target.value })} className="input">
                      <option value="member">Member</option>
                      <option value="admin">Admin</option>
                      <option value="owner">Owner</option>
                      <option value="viewer">Viewer</option>
                    </select>
                  </div>
                </div>
                <div className="flex space-x-3">
                  <button type="submit" className="btn btn-primary">Add Member</button>
                  <button type="button" onClick={() => setShowMemberForm(false)} className="btn btn-secondary">Cancel</button>
                </div>
              </form>
            </div>
          )}

          {(!members || members.length === 0) ? (
            <div className="card text-center text-gray-500 py-8">No members yet</div>
          ) : (
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-gray-200">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">User</th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Role</th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Joined</th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Actions</th>
                  </tr>
                </thead>
                <tbody className="bg-white divide-y divide-gray-200">
                  {members.map((m: OrgMembership) => (
                    <tr key={m.id}>
                      <td className="px-6 py-4">
                        <div className="text-sm font-medium text-gray-900">{m.display_name || m.email || m.user_id}</div>
                        {m.email && <div className="text-sm text-gray-500">{m.email}</div>}
                      </td>
                      <td className="px-6 py-4">
                        <span className={`px-2 py-1 text-xs rounded-full font-medium ${
                          m.role === 'admin' || m.role === 'owner' ? 'bg-purple-100 text-purple-800' : 'bg-gray-100 text-gray-800'
                        }`}>
                          {m.role}
                        </span>
                      </td>
                      <td className="px-6 py-4 text-sm text-gray-500">{m.created_at ? new Date(m.created_at).toLocaleDateString() : '--'}</td>
                      <td className="px-6 py-4">
                        <button onClick={() => handleRemoveMember(m.user_id)} className="text-red-600 hover:text-red-900">
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
      )}

      {/* SSO Tab */}
      {activeTab === 'sso' && (
        <div className="space-y-4">
          <h2 className="text-lg font-semibold">Single Sign-On (SSO)</h2>

          {ssoConfig ? (
            <div className="card space-y-4">
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <div>
                  <span className="text-sm text-gray-500">Provider</span>
                  <p className="font-medium">{ssoConfig.provider_name}</p>
                </div>
                <div>
                  <span className="text-sm text-gray-500">Type</span>
                  <p className="font-medium">{ssoConfig.provider_type}</p>
                </div>
                <div>
                  <span className="text-sm text-gray-500">Client ID</span>
                  <p className="font-medium text-sm truncate">{ssoConfig.client_id || '--'}</p>
                </div>
                <div>
                  <span className="text-sm text-gray-500">Status</span>
                  <span className={`px-2 py-1 text-xs rounded-full font-medium ${
                    ssoConfig.is_active ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'
                  }`}>
                    {ssoConfig.is_active ? 'Active' : 'Disabled'}
                  </span>
                </div>
              </div>
              {ssoConfig.issuer_url && (
                <div>
                  <span className="text-sm text-gray-500">Issuer URL:</span>
                  <p className="text-sm font-mono break-all">{ssoConfig.issuer_url}</p>
                </div>
              )}
              <button onClick={handleDisableSSO} className="btn btn-secondary text-red-600">Disable SSO</button>
            </div>
          ) : (
            <div className="card">
              <p className="text-gray-500 mb-4">No SSO configured. Set up an OIDC or SAML provider below.</p>
              <form onSubmit={handleSaveSSO} className="space-y-4">
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div>
                    <label htmlFor="sso-type" className="label">Provider Type</label>
                    <select id="sso-type" value={ssoForm.provider_type} onChange={(e) => setSSOForm({ ...ssoForm, provider_type: e.target.value })} className="input">
                      <option value="oidc">OIDC</option>
                      <option value="saml">SAML</option>
                      <option value="azure_ad">Azure AD</option>
                      <option value="okta">Okta</option>
                      <option value="google">Google Workspace</option>
                    </select>
                  </div>
                  <div>
                    <label htmlFor="sso-name" className="label">Provider Name</label>
                    <input id="sso-name" type="text" value={ssoForm.provider_name} onChange={(e) => setSSOForm({ ...ssoForm, provider_name: e.target.value })} className="input" required placeholder="e.g., Corporate Okta" />
                  </div>
                  <div>
                    <label htmlFor="sso-client-id" className="label">Client ID</label>
                    <input id="sso-client-id" type="text" value={ssoForm.client_id} onChange={(e) => setSSOForm({ ...ssoForm, client_id: e.target.value })} className="input" placeholder="OAuth2 Client ID" />
                  </div>
                  <div>
                    <label htmlFor="sso-client-secret" className="label">Client Secret</label>
                    <input id="sso-client-secret" type="password" value={ssoForm.client_secret} onChange={(e) => setSSOForm({ ...ssoForm, client_secret: e.target.value })} className="input" placeholder="OAuth2 Client Secret" />
                  </div>
                  <div className="md:col-span-2">
                    <label htmlFor="sso-issuer" className="label">Issuer URL</label>
                    <input id="sso-issuer" type="url" value={ssoForm.issuer_url} onChange={(e) => setSSOForm({ ...ssoForm, issuer_url: e.target.value })} className="input" placeholder="https://accounts.google.com" />
                  </div>
                </div>
                <button type="submit" className="btn btn-primary">Save SSO Configuration</button>
              </form>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
