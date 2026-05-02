import { useState } from 'react'
import { useLeads, useLead, useUpdateLead } from '../api/hooks'
import type { Lead, LeadStatus } from '../types'
import { SkeletonCard } from '../components/Skeleton'
import { useToast } from '../components/Toast'

const STATUS_BADGE: Record<LeadStatus, string> = {
  new: 'bg-blue-100 text-blue-800',
  scheduled: 'bg-purple-100 text-purple-800',
  contacted: 'bg-yellow-100 text-yellow-800',
  closed: 'bg-gray-100 text-gray-800',
}

const STATUS_OPTIONS: LeadStatus[] = ['new', 'scheduled', 'contacted', 'closed']

export default function Leads() {
  const toast = useToast()
  const [statusFilter, setStatusFilter] = useState<LeadStatus | ''>('')
  const [selectedId, setSelectedId] = useState<string | null>(null)

  const { data: leads, isLoading } = useLeads(statusFilter ? { status: statusFilter as LeadStatus } : undefined)
  const { data: detail } = useLead(selectedId)
  const updateMutation = useUpdateLead()

  const [notesDraft, setNotesDraft] = useState('')

  const handleStatusChange = async (id: string, status: LeadStatus) => {
    try {
      await updateMutation.mutateAsync({ id, data: { status } })
      toast('success', `Marked as ${status}`)
    } catch {
      toast('error', 'Failed to update lead')
    }
  }

  const handleSaveNotes = async () => {
    if (!selectedId) return
    try {
      await updateMutation.mutateAsync({ id: selectedId, data: { notes: notesDraft } })
      toast('success', 'Notes saved')
    } catch {
      toast('error', 'Failed to save notes')
    }
  }

  const handleSelect = (lead: Lead) => {
    if (selectedId === lead.id) {
      setSelectedId(null)
    } else {
      setSelectedId(lead.id)
      setNotesDraft(lead.notes || '')
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Leads</h1>
          <p className="text-gray-500 mt-1">Demo requests captured from the public landing page.</p>
        </div>
        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value as LeadStatus | '')}
          className="block w-48 rounded-lg border-gray-300 shadow-sm focus:border-primary-500 focus:ring-primary-500 text-sm"
        >
          <option value="">All statuses</option>
          {STATUS_OPTIONS.map((s) => (
            <option key={s} value={s}>
              {s}
            </option>
          ))}
        </select>
      </div>

      {isLoading ? (
        <div className="space-y-3">
          {[1, 2, 3].map((i) => (
            <SkeletonCard key={i} />
          ))}
        </div>
      ) : !leads?.length ? (
        <div className="text-center py-12 bg-white rounded-lg border border-gray-200">
          <p className="text-gray-500">No demo requests yet.</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
          <div className="lg:col-span-2 bg-white rounded-lg border border-gray-200 overflow-hidden">
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Name / Company</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Status</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Booked</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Created</th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-200">
                {leads.map((lead) => (
                  <tr
                    key={lead.id}
                    onClick={() => handleSelect(lead)}
                    className={`hover:bg-gray-50 cursor-pointer ${selectedId === lead.id ? 'bg-primary-50' : ''}`}
                  >
                    <td className="px-4 py-3 text-sm">
                      <div className="font-medium text-gray-900">{lead.name}</div>
                      <div className="text-xs text-gray-500">
                        {lead.company || '(no company)'} · {lead.work_email}
                      </div>
                    </td>
                    <td className="px-4 py-3">
                      <span
                        className={`inline-flex px-2 py-1 text-xs font-semibold rounded-full ${
                          STATUS_BADGE[lead.status]
                        }`}
                      >
                        {lead.status}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-sm text-gray-600">
                      {lead.calcom_meeting_url ? (
                        <a
                          href={lead.calcom_meeting_url}
                          target="_blank"
                          rel="noreferrer"
                          onClick={(e) => e.stopPropagation()}
                          className="text-primary-600 hover:underline"
                        >
                          Meeting link
                        </a>
                      ) : (
                        <span className="text-gray-400">—</span>
                      )}
                    </td>
                    <td className="px-4 py-3 text-sm text-gray-500">
                      {lead.created_at ? new Date(lead.created_at).toLocaleString() : '-'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div>
            {selectedId && detail ? (
              <div className="bg-white rounded-lg border border-gray-200 p-4 space-y-4">
                <div>
                  <h3 className="text-sm font-semibold text-gray-700">Requester</h3>
                  <p className="text-sm">{detail.name}</p>
                  <p className="text-xs text-gray-500">
                    {detail.role || '(no role)'} at {detail.company || '(no company)'} · team {detail.team_size || '?'}
                  </p>
                  <a
                    href={`mailto:${detail.work_email}`}
                    className="text-xs text-primary-600 hover:underline"
                  >
                    {detail.work_email}
                  </a>
                </div>
                {detail.use_case && (
                  <div>
                    <h3 className="text-sm font-semibold text-gray-700">Use case</h3>
                    <p className="text-xs text-gray-600 whitespace-pre-line">{detail.use_case}</p>
                  </div>
                )}
                {detail.calcom_meeting_url && (
                  <div>
                    <h3 className="text-sm font-semibold text-gray-700">Booking</h3>
                    <a
                      href={detail.calcom_meeting_url}
                      target="_blank"
                      rel="noreferrer"
                      className="text-xs text-primary-600 hover:underline break-all"
                    >
                      {detail.calcom_meeting_url}
                    </a>
                  </div>
                )}

                <div>
                  <h3 className="text-sm font-semibold text-gray-700 mb-2">Status</h3>
                  <div className="flex flex-wrap gap-2">
                    {STATUS_OPTIONS.map((s) => (
                      <button
                        key={s}
                        onClick={() => handleStatusChange(detail.id, s)}
                        disabled={detail.status === s || updateMutation.isPending}
                        className={`px-2 py-1 text-xs font-medium rounded ${
                          detail.status === s
                            ? 'bg-primary-600 text-white'
                            : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                        } disabled:opacity-50`}
                      >
                        {s}
                      </button>
                    ))}
                  </div>
                </div>

                <div>
                  <h3 className="text-sm font-semibold text-gray-700 mb-2">Notes</h3>
                  <textarea
                    value={notesDraft}
                    onChange={(e) => setNotesDraft(e.target.value)}
                    rows={5}
                    className="block w-full rounded-lg border-gray-300 shadow-sm focus:border-primary-500 focus:ring-primary-500 text-sm font-mono"
                    placeholder="Internal notes..."
                  />
                  <button
                    onClick={handleSaveNotes}
                    disabled={updateMutation.isPending}
                    className="mt-2 px-3 py-1 text-xs font-medium text-white bg-primary-600 rounded hover:bg-primary-700 disabled:opacity-50"
                  >
                    Save notes
                  </button>
                </div>
              </div>
            ) : (
              <div className="bg-white rounded-lg border border-gray-200 p-6 text-sm text-gray-500">
                Click a row to view requester details, mark status, and add notes.
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
