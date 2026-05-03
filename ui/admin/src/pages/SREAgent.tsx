import { useState } from 'react'
import {
  useSREIncidents,
  useSREIncident,
  useApproveSREIncident,
  useRejectSREIncident,
  useTriggerSREIncident,
  useSREStats,
} from '../api/hooks'
import type { SREIncidentStatus, SREProposedAction } from '../types'
import { SkeletonCard } from '../components/Skeleton'
import { useToast } from '../components/Toast'
import ConfirmDialog from '../components/ConfirmDialog'

const TRIGGER_EVENTS = ['sla.violation', 'budget.exceeded', 'provider.unhealthy', 'guardrail.violation']

const STATUS_BADGE: Record<SREIncidentStatus, string> = {
  open: 'bg-blue-100 text-blue-800',
  diagnosing: 'bg-blue-100 text-blue-800',
  awaiting_approval: 'bg-yellow-100 text-yellow-800',
  executing: 'bg-purple-100 text-purple-800',
  closed_success: 'bg-green-100 text-green-800',
  closed_failed: 'bg-red-100 text-red-800',
  closed_rejected: 'bg-gray-100 text-gray-800',
}

type Tab = 'incidents' | 'approvals' | 'trigger' | 'stats'

export default function SREAgent() {
  const toast = useToast()
  const [tab, setTab] = useState<Tab>('incidents')
  const [selectedId, setSelectedId] = useState<string | null>(null)

  const { data: allIncidents, isLoading: incidentsLoading } = useSREIncidents()
  const { data: pending, isLoading: pendingLoading } = useSREIncidents({ status: 'awaiting_approval' })
  const { data: detail } = useSREIncident(selectedId)
  const { data: stats } = useSREStats()

  const approveMutation = useApproveSREIncident()
  const rejectMutation = useRejectSREIncident()
  const triggerMutation = useTriggerSREIncident()

  const [triggerEvent, setTriggerEvent] = useState(TRIGGER_EVENTS[0])
  const [triggerPayload, setTriggerPayload] = useState(
    '{\n  "provider": "openai",\n  "model": "gpt-4o",\n  "severity": "high"\n}',
  )

  // Confirmation modal for "Approve and execute". Native confirm() blocks the
  // event loop, can't be styled, and produces no audit-friendly DOM. The
  // ConfirmDialog component is used elsewhere in the admin UI for the same
  // class of action — keep it consistent.
  const [pendingApproveId, setPendingApproveId] = useState<string | null>(null)

  const requestApprove = (id: string) => setPendingApproveId(id)

  const confirmApprove = async () => {
    const id = pendingApproveId
    setPendingApproveId(null)
    if (!id) return
    try {
      const result = await approveMutation.mutateAsync(id)
      toast(result.ok ? 'success' : 'error', result.ok ? 'Plan executed' : 'Execution failed; see incident detail.')
    } catch {
      toast('error', 'Failed to approve incident')
    }
  }

  const handleReject = async (id: string) => {
    const reason = prompt('Reason for rejection (optional):') || undefined
    try {
      await rejectMutation.mutateAsync({ id, reason })
      toast('success', 'Incident rejected')
    } catch {
      toast('error', 'Failed to reject incident')
    }
  }

  const handleTrigger = async () => {
    let payload: Record<string, unknown>
    try {
      payload = JSON.parse(triggerPayload)
    } catch {
      toast('error', 'Payload must be valid JSON')
      return
    }
    try {
      const r = await triggerMutation.mutateAsync({ event_type: triggerEvent, payload })
      toast('success', `Incident opened: ${r.incident_id}`)
      setSelectedId(r.incident_id)
      setTab('incidents')
    } catch {
      toast('error', 'Trigger failed (is the SRE agent running?)')
    }
  }

  const agentReachable = stats?.agent_reachable !== false

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">SRE Agent</h1>
          <p className="text-gray-500 mt-1">
            LLM-driven incident response with human-in-loop approval.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <span
            className={`inline-flex items-center gap-2 px-3 py-1 rounded-full text-xs font-medium ${
              agentReachable ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'
            }`}
          >
            <span className={`w-2 h-2 rounded-full ${agentReachable ? 'bg-green-500' : 'bg-red-500'}`} />
            {agentReachable ? 'Agent reachable' : 'Agent unreachable'}
          </span>
        </div>
      </div>

      <div className="border-b border-gray-200">
        <nav className="-mb-px flex space-x-8">
          {(
            [
              ['incidents', 'Incidents', allIncidents?.length],
              ['approvals', 'Pending Approvals', pending?.length],
              ['trigger', 'Manual Trigger', null],
              ['stats', 'Stats', null],
            ] as Array<[Tab, string, number | null | undefined]>
          ).map(([id, label, count]) => (
            <button
              key={id}
              onClick={() => setTab(id)}
              className={`py-4 px-1 border-b-2 font-medium text-sm ${
                tab === id
                  ? 'border-primary-500 text-primary-600'
                  : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
              }`}
            >
              {label}
              {typeof count === 'number' && (
                <span className="ml-2 bg-gray-100 text-gray-600 py-0.5 px-2 rounded-full text-xs">{count}</span>
              )}
            </button>
          ))}
        </nav>
      </div>

      {tab === 'incidents' && (
        <IncidentsTable
          loading={incidentsLoading}
          incidents={allIncidents || []}
          selectedId={selectedId}
          onSelect={setSelectedId}
          detail={detail || null}
        />
      )}

      {tab === 'approvals' && (
        <ApprovalsTab
          loading={pendingLoading}
          incidents={pending || []}
          onApprove={requestApprove}
          onReject={handleReject}
          approving={approveMutation.isPending}
          rejecting={rejectMutation.isPending}
          onSelect={setSelectedId}
          selectedId={selectedId}
          detail={detail || null}
        />
      )}

      {tab === 'trigger' && (
        <div className="bg-white rounded-lg border border-gray-200 p-6 max-w-2xl">
          <h2 className="text-lg font-semibold mb-4">Manually open an incident</h2>
          <p className="text-sm text-gray-500 mb-4">
            Bypasses the event subscription path — directly invokes the SRE agent webhook with the
            payload you supply. Useful for smoke-testing.
          </p>
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Event Type</label>
              <select
                value={triggerEvent}
                onChange={(e) => setTriggerEvent(e.target.value)}
                className="block w-full rounded-lg border-gray-300 shadow-sm focus:border-primary-500 focus:ring-primary-500 text-sm"
              >
                {TRIGGER_EVENTS.map((ev) => (
                  <option key={ev} value={ev}>
                    {ev}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Payload (JSON)</label>
              <textarea
                value={triggerPayload}
                onChange={(e) => setTriggerPayload(e.target.value)}
                rows={10}
                className="block w-full rounded-lg border-gray-300 shadow-sm focus:border-primary-500 focus:ring-primary-500 text-sm font-mono"
              />
            </div>
            <div className="flex justify-end">
              <button
                onClick={handleTrigger}
                disabled={triggerMutation.isPending}
                className="px-4 py-2 text-sm font-medium text-white bg-primary-600 rounded-lg hover:bg-primary-700 disabled:opacity-50"
              >
                {triggerMutation.isPending ? 'Opening...' : 'Open incident'}
              </button>
            </div>
          </div>
        </div>
      )}

      {tab === 'stats' && (
        <StatsTab stats={stats || null} />
      )}

      <ConfirmDialog
        isOpen={pendingApproveId !== null}
        onClose={() => setPendingApproveId(null)}
        onConfirm={confirmApprove}
        title="Approve and execute remediation?"
        message="This calls admin-api mutations on your behalf and is logged to the audit trail. Reject instead if you only want to dismiss the incident."
        confirmLabel="Approve & execute"
        confirmVariant="danger"
      />
    </div>
  )
}

function IncidentsTable({
  loading,
  incidents,
  selectedId,
  onSelect,
  detail,
}: {
  loading: boolean
  incidents: Array<{
    id: string
    trigger_event: string
    status: SREIncidentStatus
    outcome_summary: string | null
    opened_at: string | null
    closed_at: string | null
    plan_count: number
    executed_count: number
  }>
  selectedId: string | null
  onSelect: (id: string | null) => void
  detail: ReturnType<typeof useSREIncident>['data'] | null
}) {
  if (loading) {
    return (
      <div className="space-y-3">
        {[1, 2, 3].map((i) => (
          <SkeletonCard key={i} />
        ))}
      </div>
    )
  }

  if (incidents.length === 0) {
    return (
      <div className="text-center py-12 bg-white rounded-lg border border-gray-200">
        <p className="text-gray-500">No incidents recorded yet</p>
      </div>
    )
  }

  return (
    <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
      <div className="lg:col-span-2 bg-white rounded-lg border border-gray-200 overflow-hidden">
        <table className="min-w-full divide-y divide-gray-200">
          <thead className="bg-gray-50">
            <tr>
              <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Trigger</th>
              <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Status</th>
              <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Plan / Executed</th>
              <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Opened</th>
            </tr>
          </thead>
          <tbody className="bg-white divide-y divide-gray-200">
            {incidents.map((row) => (
              <tr
                key={row.id}
                onClick={() => onSelect(row.id === selectedId ? null : row.id)}
                className={`hover:bg-gray-50 cursor-pointer ${selectedId === row.id ? 'bg-primary-50' : ''}`}
              >
                <td className="px-4 py-3 text-sm">
                  <span className="inline-flex px-2 py-1 text-xs font-semibold rounded-full bg-indigo-100 text-indigo-800">
                    {row.trigger_event}
                  </span>
                </td>
                <td className="px-4 py-3">
                  <span
                    className={`inline-flex px-2 py-1 text-xs font-semibold rounded-full ${
                      STATUS_BADGE[row.status] || 'bg-gray-100 text-gray-800'
                    }`}
                  >
                    {row.status}
                  </span>
                </td>
                <td className="px-4 py-3 text-sm text-gray-600">
                  {row.plan_count} / {row.executed_count}
                </td>
                <td className="px-4 py-3 text-sm text-gray-500">
                  {row.opened_at ? new Date(row.opened_at).toLocaleString() : '-'}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div>
        {selectedId && detail ? (
          <IncidentDetailCard detail={detail} />
        ) : (
          <div className="bg-white rounded-lg border border-gray-200 p-6 text-sm text-gray-500">
            Click an incident to see its diagnosis, proposed plan, and decision history.
          </div>
        )}
      </div>
    </div>
  )
}

function ApprovalsTab({
  loading,
  incidents,
  onApprove,
  onReject,
  approving,
  rejecting,
  onSelect,
  selectedId,
  detail,
}: {
  loading: boolean
  incidents: Array<{ id: string; trigger_event: string; outcome_summary: string | null; plan_count: number; opened_at: string | null }>
  onApprove: (id: string) => void
  onReject: (id: string) => void
  approving: boolean
  rejecting: boolean
  onSelect: (id: string | null) => void
  selectedId: string | null
  detail: ReturnType<typeof useSREIncident>['data'] | null
}) {
  if (loading) {
    return (
      <div className="space-y-3">
        {[1, 2].map((i) => (
          <SkeletonCard key={i} />
        ))}
      </div>
    )
  }

  if (incidents.length === 0) {
    return (
      <div className="text-center py-12 bg-white rounded-lg border border-gray-200">
        <p className="text-gray-500">No incidents awaiting approval.</p>
      </div>
    )
  }

  return (
    <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
      <div className="lg:col-span-2 space-y-3">
        {incidents.map((row) => (
          <div
            key={row.id}
            className={`bg-white rounded-lg border p-4 ${
              selectedId === row.id ? 'border-primary-300 ring-1 ring-primary-200' : 'border-gray-200'
            }`}
          >
            <div className="flex items-start justify-between">
              <button onClick={() => onSelect(row.id === selectedId ? null : row.id)} className="text-left flex-1">
                <div className="flex items-center gap-2 mb-1">
                  <span className="inline-flex px-2 py-1 text-xs font-semibold rounded-full bg-indigo-100 text-indigo-800">
                    {row.trigger_event}
                  </span>
                  <span className="text-xs text-gray-500">
                    {row.opened_at ? new Date(row.opened_at).toLocaleString() : ''}
                  </span>
                </div>
                <p className="text-sm text-gray-700">{row.outcome_summary || '(no summary yet)'}</p>
                <p className="text-xs text-gray-500 mt-1">{row.plan_count} action(s) proposed</p>
              </button>
              <div className="flex flex-col gap-2 ml-4">
                <button
                  onClick={() => onApprove(row.id)}
                  disabled={approving}
                  className="px-3 py-1 text-xs font-medium text-white bg-green-600 rounded hover:bg-green-700 disabled:opacity-50"
                >
                  Approve
                </button>
                <button
                  onClick={() => onReject(row.id)}
                  disabled={rejecting}
                  className="px-3 py-1 text-xs font-medium text-white bg-red-600 rounded hover:bg-red-700 disabled:opacity-50"
                >
                  Reject
                </button>
              </div>
            </div>
          </div>
        ))}
      </div>
      <div>
        {selectedId && detail ? (
          <IncidentDetailCard detail={detail} />
        ) : (
          <div className="bg-white rounded-lg border border-gray-200 p-6 text-sm text-gray-500">
            Select an incident to inspect its proposed plan before approving.
          </div>
        )}
      </div>
    </div>
  )
}

function IncidentDetailCard({ detail }: { detail: NonNullable<ReturnType<typeof useSREIncident>['data']> }) {
  return (
    <div className="bg-white rounded-lg border border-gray-200 p-4 space-y-4">
      <div>
        <h3 className="text-sm font-semibold text-gray-700">Trigger</h3>
        <pre className="mt-1 text-xs bg-gray-50 rounded p-2 overflow-x-auto">
          {JSON.stringify(detail.trigger_payload, null, 2)}
        </pre>
      </div>
      {detail.proposed_plan && detail.proposed_plan.length > 0 && (
        <div>
          <h3 className="text-sm font-semibold text-gray-700">Proposed plan</h3>
          <ul className="mt-1 space-y-2">
            {detail.proposed_plan.map((step: SREProposedAction, idx: number) => (
              <li key={idx} className="text-xs bg-gray-50 rounded p-2">
                <div className="flex justify-between mb-1">
                  <span className="font-medium text-gray-900">{step.action}</span>
                  <span className="text-gray-500">
                    risk {step.risk_score} · {step.decision}
                  </span>
                </div>
                <pre className="overflow-x-auto">{JSON.stringify(step.params, null, 2)}</pre>
              </li>
            ))}
          </ul>
        </div>
      )}
      {detail.executed_actions && detail.executed_actions.length > 0 && (
        <div>
          <h3 className="text-sm font-semibold text-gray-700">Executed</h3>
          <pre className="mt-1 text-xs bg-gray-50 rounded p-2 overflow-x-auto">
            {JSON.stringify(detail.executed_actions, null, 2)}
          </pre>
        </div>
      )}
      {detail.outcome_summary && (
        <div>
          <h3 className="text-sm font-semibold text-gray-700">Outcome</h3>
          <p className="mt-1 text-xs text-gray-600 whitespace-pre-line">{detail.outcome_summary}</p>
        </div>
      )}
    </div>
  )
}

function StatsTab({ stats }: { stats: ReturnType<typeof useSREStats>['data'] | null }) {
  if (!stats) {
    return <SkeletonCard />
  }
  if (stats.agent_reachable === false) {
    return (
      <div className="bg-red-50 border border-red-200 rounded-lg p-4 text-sm text-red-800">
        SRE agent is unreachable: {stats.error || 'unknown error'}
      </div>
    )
  }
  const entries = Object.entries(stats.by_status || {})
  return (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
      {entries.map(([status, n]) => (
        <div key={status} className="bg-white rounded-lg border border-gray-200 p-4">
          <p className="text-xs text-gray-500 uppercase tracking-wide">{status}</p>
          <p className="text-2xl font-semibold text-gray-900 mt-1">{n}</p>
        </div>
      ))}
      <div className="bg-white rounded-lg border border-gray-200 p-4">
        <p className="text-xs text-gray-500 uppercase tracking-wide">MTTR (30d)</p>
        <p className="text-2xl font-semibold text-gray-900 mt-1">
          {stats.mttr_seconds === null
            ? '—'
            : `${Math.round((stats.mttr_seconds || 0) / 60)} min`}
        </p>
      </div>
    </div>
  )
}
