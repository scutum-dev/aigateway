import { useState } from 'react'
import { useAuditLogs } from '../api/hooks'
import { auditApi } from '../api/client'
import { ArrowDownTrayIcon, FunnelIcon } from '@heroicons/react/24/outline'
import { SkeletonCard } from '../components/Skeleton'
import { useToast } from '../components/Toast'

export default function AuditLog() {
  const toast = useToast()

  const [filters, setFilters] = useState({
    resource_type: '',
    action: '',
    actor_id: '',
  })
  const [appliedFilters, setAppliedFilters] = useState<Record<string, string>>({})
  const [showFilters, setShowFilters] = useState(false)

  const queryParams: Record<string, string | number> = { limit: 100 }
  if (appliedFilters.resource_type) queryParams.resource_type = appliedFilters.resource_type
  if (appliedFilters.action) queryParams.action = appliedFilters.action
  if (appliedFilters.actor_id) queryParams.actor_id = appliedFilters.actor_id

  const { data: logs, isLoading, error } = useAuditLogs(queryParams)

  const applyFilters = () => {
    const f: Record<string, string> = {}
    if (filters.resource_type) f.resource_type = filters.resource_type
    if (filters.action) f.action = filters.action
    if (filters.actor_id) f.actor_id = filters.actor_id
    setAppliedFilters(f)
  }

  const clearFilters = () => {
    setFilters({ resource_type: '', action: '', actor_id: '' })
    setAppliedFilters({})
  }

  const handleExport = async (format: string) => {
    try {
      const blob = await auditApi.export(format)
      const url = window.URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `audit_logs.${format}`
      document.body.appendChild(a)
      a.click()
      window.URL.revokeObjectURL(url)
      document.body.removeChild(a)
      toast('success', `Exported as ${format.toUpperCase()}`)
    } catch {
      toast('error', 'Failed to export audit logs')
    }
  }

  if (isLoading) {
    return (
      <div className="space-y-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Audit Log</h1>
          <p className="text-gray-600">Track all administrative actions</p>
        </div>
        <SkeletonCard />
      </div>
    )
  }

  if (error) {
    return <div className="bg-red-50 text-red-700 p-4 rounded-lg">Failed to load audit logs</div>
  }

  const logList = Array.isArray(logs) ? logs : []

  const actionColors: Record<string, string> = {
    create: 'bg-green-100 text-green-800',
    update: 'bg-blue-100 text-blue-800',
    delete: 'bg-red-100 text-red-800',
    configure_sso: 'bg-purple-100 text-purple-800',
    disable_sso: 'bg-yellow-100 text-yellow-800',
    assign_team: 'bg-indigo-100 text-indigo-800',
    remove_team: 'bg-orange-100 text-orange-800',
    add_member: 'bg-teal-100 text-teal-800',
    remove_member: 'bg-pink-100 text-pink-800',
  }

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Audit Log</h1>
          <p className="text-gray-600">
            {logList.length} event{logList.length !== 1 ? 's' : ''}
          </p>
        </div>
        <div className="flex gap-2">
          <button onClick={() => setShowFilters(!showFilters)} className="btn btn-secondary">
            <FunnelIcon className="w-4 h-4 mr-1" />
            Filters
          </button>
          <button onClick={() => handleExport('csv')} className="btn btn-secondary">
            <ArrowDownTrayIcon className="w-4 h-4 mr-1" />
            CSV
          </button>
          <button onClick={() => handleExport('json')} className="btn btn-secondary">
            <ArrowDownTrayIcon className="w-4 h-4 mr-1" />
            JSON
          </button>
        </div>
      </div>

      {showFilters && (
        <div className="card">
          <h3 className="text-sm font-semibold mb-3">Filters</h3>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div>
              <label htmlFor="filter-resource" className="label">Resource Type</label>
              <select
                id="filter-resource"
                value={filters.resource_type}
                onChange={(e) => setFilters({ ...filters, resource_type: e.target.value })}
                className="input"
              >
                <option value="">All</option>
                <option value="organization">Organization</option>
                <option value="business_unit">Business Unit</option>
                <option value="team_hierarchy">Team Hierarchy</option>
                <option value="org_membership">Membership</option>
                <option value="sso_config">SSO Config</option>
                <option value="content_detector">Content Detector</option>
                <option value="guardrail_detector">Guardrail Detector</option>
                <option value="team_content_policy">Content Policy</option>
              </select>
            </div>
            <div>
              <label htmlFor="filter-action" className="label">Action</label>
              <select
                id="filter-action"
                value={filters.action}
                onChange={(e) => setFilters({ ...filters, action: e.target.value })}
                className="input"
              >
                <option value="">All</option>
                <option value="create">Create</option>
                <option value="update">Update</option>
                <option value="delete">Delete</option>
                <option value="configure_sso">Configure SSO</option>
                <option value="disable_sso">Disable SSO</option>
                <option value="assign_team">Assign Team</option>
                <option value="remove_team">Remove Team</option>
                <option value="add_member">Add Member</option>
                <option value="remove_member">Remove Member</option>
              </select>
            </div>
            <div>
              <label htmlFor="filter-actor" className="label">Actor ID</label>
              <input
                id="filter-actor"
                type="text"
                value={filters.actor_id}
                onChange={(e) => setFilters({ ...filters, actor_id: e.target.value })}
                className="input"
                placeholder="Filter by actor"
              />
            </div>
          </div>
          <div className="flex gap-2 mt-3">
            <button onClick={applyFilters} className="btn btn-primary">Apply</button>
            <button onClick={clearFilters} className="btn btn-secondary">Clear</button>
          </div>
        </div>
      )}

      {logList.length === 0 ? (
        <div className="card text-center text-gray-500 py-12">
          <p className="text-lg font-medium">No audit events found</p>
          <p className="text-sm mt-1">Administrative actions will appear here as they happen.</p>
        </div>
      ) : (
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Timestamp</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Actor</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Action</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Resource Type</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Resource</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Changes</th>
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-200">
              {logList.map((entry) => (
                <tr key={entry.id} className="hover:bg-gray-50">
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                    {entry.timestamp ? new Date(entry.timestamp).toLocaleString() : '--'}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap">
                    <div className="text-sm font-medium text-gray-900">{entry.actor_id}</div>
                    {entry.actor_email && <div className="text-xs text-gray-500">{entry.actor_email}</div>}
                    {entry.actor_ip && <div className="text-xs text-gray-400">{entry.actor_ip}</div>}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap">
                    <span className={`px-2 py-1 text-xs font-medium rounded-full ${actionColors[entry.action] || 'bg-gray-100 text-gray-800'}`}>
                      {entry.action}
                    </span>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-600">
                    {entry.resource_type}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap">
                    <div className="text-sm text-gray-900">{entry.resource_name || entry.resource_id || '--'}</div>
                    {entry.resource_name && entry.resource_id && (
                      <code className="text-xs text-gray-400">{entry.resource_id}</code>
                    )}
                  </td>
                  <td className="px-6 py-4 text-sm text-gray-500 max-w-xs truncate">
                    {Object.keys(entry.changes).length > 0 ? (
                      <code className="text-xs bg-gray-50 px-2 py-1 rounded">
                        {JSON.stringify(entry.changes).substring(0, 80)}
                        {JSON.stringify(entry.changes).length > 80 ? '...' : ''}
                      </code>
                    ) : (
                      '--'
                    )}
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
