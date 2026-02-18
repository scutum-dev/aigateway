import { useState } from 'react'
import {
  useEventSubscriptions,
  useCreateEventSubscription,
  useDeleteEventSubscription,
  useEventLog,
  useSendTestEvent,
} from '../api/hooks'
import type { EventSubscriptionCreate } from '../types'
import {
  PlusIcon,
  TrashIcon,
  PaperAirplaneIcon,
} from '@heroicons/react/24/outline'
import { SkeletonCard } from '../components/Skeleton'
import { useToast } from '../components/Toast'

const EVENT_TYPES = [
  'model.created',
  'model.deleted',
  'model.deprecated',
  'key.created',
  'key.revoked',
  'budget.exceeded',
  'budget.warning',
  'guardrail.triggered',
  'sla.violation',
  'workflow.completed',
  'workflow.failed',
  'team.created',
  'team.deleted',
  'config.changed',
  'cache.cleared',
  'failover.triggered',
]

const CHANNELS = ['webhook', 'slack', 'pagerduty', 'email']

const channelBadge: Record<string, string> = {
  webhook: 'bg-blue-100 text-blue-800',
  slack: 'bg-purple-100 text-purple-800',
  pagerduty: 'bg-red-100 text-red-800',
  email: 'bg-green-100 text-green-800',
}

type Tab = 'subscriptions' | 'log'

export default function Events() {
  const toast = useToast()
  const [activeTab, setActiveTab] = useState<Tab>('subscriptions')
  const [showCreate, setShowCreate] = useState(false)
  const [showTestEvent, setShowTestEvent] = useState(false)
  const [logFilter, setLogFilter] = useState<string>('')

  // Subscriptions state
  const { data: subscriptions, isLoading: subsLoading } = useEventSubscriptions()
  const createMutation = useCreateEventSubscription()
  const deleteMutation = useDeleteEventSubscription()

  // Event log state
  const { data: events, isLoading: eventsLoading } = useEventLog(
    logFilter ? { event_type: logFilter, limit: 100 } : { limit: 100 }
  )
  const testEventMutation = useSendTestEvent()

  // Create form state
  const [form, setForm] = useState<EventSubscriptionCreate>({
    name: '',
    event_types: [],
    channel: 'webhook',
    config: {},
    filters: undefined,
  })
  const [configJson, setConfigJson] = useState('{\n  "url": "https://example.com/webhook"\n}')
  const [filtersJson, setFiltersJson] = useState('')

  // Test event form
  const [testEventType, setTestEventType] = useState('model.created')
  const [testPayloadJson, setTestPayloadJson] = useState('{\n  "model": "gpt-4",\n  "action": "test"\n}')

  const handleCreate = async () => {
    try {
      const config = JSON.parse(configJson)
      const filters = filtersJson.trim() ? JSON.parse(filtersJson) : undefined
      await createMutation.mutateAsync({
        ...form,
        config,
        filters,
      })
      toast('success', 'Subscription created')
      setShowCreate(false)
      setForm({
        name: '',
        event_types: [],
        channel: 'webhook',
        config: {},
        filters: undefined,
      })
      setConfigJson('{\n  "url": "https://example.com/webhook"\n}')
      setFiltersJson('')
    } catch {
      toast('error', 'Failed to create subscription. Check JSON fields.')
    }
  }

  const handleDelete = async (id: string) => {
    if (!confirm('Delete this subscription?')) return
    try {
      await deleteMutation.mutateAsync(id)
      toast('success', 'Subscription deleted')
    } catch {
      toast('error', 'Failed to delete subscription')
    }
  }

  const handleSendTestEvent = async () => {
    try {
      const payload = JSON.parse(testPayloadJson)
      await testEventMutation.mutateAsync({ event_type: testEventType, payload })
      toast('success', 'Test event sent')
      setShowTestEvent(false)
    } catch {
      toast('error', 'Failed to send test event. Check payload JSON.')
    }
  }

  const toggleEventType = (et: string) => {
    setForm((prev) => ({
      ...prev,
      event_types: prev.event_types.includes(et)
        ? prev.event_types.filter((t) => t !== et)
        : [...prev.event_types, et],
    }))
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Events</h1>
          <p className="text-gray-500 mt-1">
            Manage event subscriptions and view the event log
          </p>
        </div>
        <div className="flex gap-2">
          <button
            onClick={() => setShowTestEvent(true)}
            className="inline-flex items-center px-3 py-2 border border-gray-300 text-sm font-medium rounded-lg text-gray-700 bg-white hover:bg-gray-50"
          >
            <PaperAirplaneIcon className="w-4 h-4 mr-2" />
            Send Test Event
          </button>
          {activeTab === 'subscriptions' && (
            <button
              onClick={() => setShowCreate(true)}
              className="inline-flex items-center px-4 py-2 bg-primary-600 text-white text-sm font-medium rounded-lg hover:bg-primary-700"
            >
              <PlusIcon className="w-4 h-4 mr-2" />
              Add Subscription
            </button>
          )}
        </div>
      </div>

      {/* Tabs */}
      <div className="border-b border-gray-200">
        <nav className="-mb-px flex space-x-8">
          <button
            onClick={() => setActiveTab('subscriptions')}
            className={`py-4 px-1 border-b-2 font-medium text-sm ${
              activeTab === 'subscriptions'
                ? 'border-primary-500 text-primary-600'
                : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
            }`}
          >
            Subscriptions
            {subscriptions && (
              <span className="ml-2 bg-gray-100 text-gray-600 py-0.5 px-2 rounded-full text-xs">
                {subscriptions.length}
              </span>
            )}
          </button>
          <button
            onClick={() => setActiveTab('log')}
            className={`py-4 px-1 border-b-2 font-medium text-sm ${
              activeTab === 'log'
                ? 'border-primary-500 text-primary-600'
                : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
            }`}
          >
            Event Log
            {events && (
              <span className="ml-2 bg-gray-100 text-gray-600 py-0.5 px-2 rounded-full text-xs">
                {events.length}
              </span>
            )}
          </button>
        </nav>
      </div>

      {/* Subscriptions Tab */}
      {activeTab === 'subscriptions' && (
        <>
          {subsLoading ? (
            <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
              {[1, 2, 3].map((i) => (
                <SkeletonCard key={i} />
              ))}
            </div>
          ) : !subscriptions?.length ? (
            <div className="text-center py-12 bg-white rounded-lg border border-gray-200">
              <p className="text-gray-500">No event subscriptions configured</p>
              <button
                onClick={() => setShowCreate(true)}
                className="mt-4 text-primary-600 hover:text-primary-700 text-sm font-medium"
              >
                Create your first subscription
              </button>
            </div>
          ) : (
            <div className="bg-white rounded-lg border border-gray-200 overflow-hidden">
              <table className="min-w-full divide-y divide-gray-200">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Name
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Channel
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Event Types
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Status
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Created
                    </th>
                    <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Actions
                    </th>
                  </tr>
                </thead>
                <tbody className="bg-white divide-y divide-gray-200">
                  {subscriptions.map((sub) => (
                    <tr key={sub.id} className="hover:bg-gray-50">
                      <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">
                        {sub.name}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap">
                        <span
                          className={`inline-flex px-2 py-1 text-xs font-semibold rounded-full ${
                            channelBadge[sub.channel] || 'bg-gray-100 text-gray-800'
                          }`}
                        >
                          {sub.channel}
                        </span>
                      </td>
                      <td className="px-6 py-4 text-sm text-gray-500">
                        <div className="flex flex-wrap gap-1">
                          {sub.event_types.slice(0, 3).map((et) => (
                            <span
                              key={et}
                              className="inline-flex px-2 py-0.5 text-xs bg-gray-100 text-gray-700 rounded"
                            >
                              {et}
                            </span>
                          ))}
                          {sub.event_types.length > 3 && (
                            <span className="text-xs text-gray-400">
                              +{sub.event_types.length - 3} more
                            </span>
                          )}
                        </div>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap">
                        <span
                          className={`inline-flex px-2 py-1 text-xs font-semibold rounded-full ${
                            sub.is_active
                              ? 'bg-green-100 text-green-800'
                              : 'bg-gray-100 text-gray-800'
                          }`}
                        >
                          {sub.is_active ? 'Active' : 'Inactive'}
                        </span>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                        {sub.created_at ? new Date(sub.created_at).toLocaleDateString() : '-'}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-right">
                        <button
                          onClick={() => handleDelete(sub.id)}
                          className="text-red-600 hover:text-red-800"
                          title="Delete subscription"
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
        </>
      )}

      {/* Event Log Tab */}
      {activeTab === 'log' && (
        <>
          <div className="flex items-center gap-4 mb-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Filter by Event Type
              </label>
              <select
                value={logFilter}
                onChange={(e) => setLogFilter(e.target.value)}
                className="block w-64 rounded-lg border-gray-300 shadow-sm focus:border-primary-500 focus:ring-primary-500 text-sm"
              >
                <option value="">All events</option>
                {EVENT_TYPES.map((et) => (
                  <option key={et} value={et}>
                    {et}
                  </option>
                ))}
              </select>
            </div>
          </div>

          {eventsLoading ? (
            <div className="space-y-3">
              {[1, 2, 3, 4, 5].map((i) => (
                <SkeletonCard key={i} />
              ))}
            </div>
          ) : !events?.length ? (
            <div className="text-center py-12 bg-white rounded-lg border border-gray-200">
              <p className="text-gray-500">No events recorded yet</p>
              <button
                onClick={() => setShowTestEvent(true)}
                className="mt-4 text-primary-600 hover:text-primary-700 text-sm font-medium"
              >
                Send a test event
              </button>
            </div>
          ) : (
            <div className="bg-white rounded-lg border border-gray-200 overflow-hidden">
              <table className="min-w-full divide-y divide-gray-200">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Event Type
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Payload Preview
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Source
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Timestamp
                    </th>
                  </tr>
                </thead>
                <tbody className="bg-white divide-y divide-gray-200">
                  {events.map((event) => {
                    const payloadStr = JSON.stringify(event.payload)
                    const preview =
                      payloadStr.length > 80
                        ? payloadStr.substring(0, 80) + '...'
                        : payloadStr
                    return (
                      <tr key={event.id} className="hover:bg-gray-50">
                        <td className="px-6 py-4 whitespace-nowrap">
                          <span className="inline-flex px-2 py-1 text-xs font-semibold rounded-full bg-indigo-100 text-indigo-800">
                            {event.event_type}
                          </span>
                        </td>
                        <td className="px-6 py-4 text-sm text-gray-500 font-mono max-w-xs truncate">
                          {preview}
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                          {event.source_service || '-'}
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                          {event.created_at
                            ? new Date(event.created_at).toLocaleString()
                            : '-'}
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          )}
        </>
      )}

      {/* Create Subscription Modal */}
      {showCreate && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-white rounded-xl shadow-xl p-6 w-full max-w-lg max-h-[90vh] overflow-y-auto">
            <h2 className="text-lg font-semibold mb-4">Create Event Subscription</h2>

            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Name
                </label>
                <input
                  type="text"
                  value={form.name}
                  onChange={(e) => setForm({ ...form, name: e.target.value })}
                  className="block w-full rounded-lg border-gray-300 shadow-sm focus:border-primary-500 focus:ring-primary-500 text-sm"
                  placeholder="e.g., Slack Budget Alerts"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Channel
                </label>
                <select
                  value={form.channel}
                  onChange={(e) => setForm({ ...form, channel: e.target.value })}
                  className="block w-full rounded-lg border-gray-300 shadow-sm focus:border-primary-500 focus:ring-primary-500 text-sm"
                >
                  {CHANNELS.map((ch) => (
                    <option key={ch} value={ch}>
                      {ch}
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Event Types
                </label>
                <div className="max-h-48 overflow-y-auto border rounded-lg p-2 space-y-1">
                  {EVENT_TYPES.map((et) => (
                    <label
                      key={et}
                      className="flex items-center gap-2 px-2 py-1 hover:bg-gray-50 rounded cursor-pointer"
                    >
                      <input
                        type="checkbox"
                        checked={form.event_types.includes(et)}
                        onChange={() => toggleEventType(et)}
                        className="rounded border-gray-300 text-primary-600 focus:ring-primary-500"
                      />
                      <span className="text-sm text-gray-700">{et}</span>
                    </label>
                  ))}
                </div>
                {form.event_types.length > 0 && (
                  <p className="mt-1 text-xs text-gray-500">
                    {form.event_types.length} selected
                  </p>
                )}
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Config (JSON)
                </label>
                <textarea
                  value={configJson}
                  onChange={(e) => setConfigJson(e.target.value)}
                  rows={4}
                  className="block w-full rounded-lg border-gray-300 shadow-sm focus:border-primary-500 focus:ring-primary-500 text-sm font-mono"
                  placeholder='{"url": "https://..."}'
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Filters (JSON, optional)
                </label>
                <textarea
                  value={filtersJson}
                  onChange={(e) => setFiltersJson(e.target.value)}
                  rows={3}
                  className="block w-full rounded-lg border-gray-300 shadow-sm focus:border-primary-500 focus:ring-primary-500 text-sm font-mono"
                  placeholder='{"team_id": "team-123"}'
                />
              </div>
            </div>

            <div className="flex justify-end gap-3 mt-6">
              <button
                onClick={() => setShowCreate(false)}
                className="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-lg hover:bg-gray-50"
              >
                Cancel
              </button>
              <button
                onClick={handleCreate}
                disabled={!form.name || form.event_types.length === 0 || createMutation.isPending}
                className="px-4 py-2 text-sm font-medium text-white bg-primary-600 rounded-lg hover:bg-primary-700 disabled:opacity-50"
              >
                {createMutation.isPending ? 'Creating...' : 'Create'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Send Test Event Modal */}
      {showTestEvent && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-white rounded-xl shadow-xl p-6 w-full max-w-md">
            <h2 className="text-lg font-semibold mb-4">Send Test Event</h2>

            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Event Type
                </label>
                <select
                  value={testEventType}
                  onChange={(e) => setTestEventType(e.target.value)}
                  className="block w-full rounded-lg border-gray-300 shadow-sm focus:border-primary-500 focus:ring-primary-500 text-sm"
                >
                  {EVENT_TYPES.map((et) => (
                    <option key={et} value={et}>
                      {et}
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Payload (JSON)
                </label>
                <textarea
                  value={testPayloadJson}
                  onChange={(e) => setTestPayloadJson(e.target.value)}
                  rows={5}
                  className="block w-full rounded-lg border-gray-300 shadow-sm focus:border-primary-500 focus:ring-primary-500 text-sm font-mono"
                />
              </div>
            </div>

            <div className="flex justify-end gap-3 mt-6">
              <button
                onClick={() => setShowTestEvent(false)}
                className="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-lg hover:bg-gray-50"
              >
                Cancel
              </button>
              <button
                onClick={handleSendTestEvent}
                disabled={testEventMutation.isPending}
                className="inline-flex items-center px-4 py-2 text-sm font-medium text-white bg-primary-600 rounded-lg hover:bg-primary-700 disabled:opacity-50"
              >
                <PaperAirplaneIcon className="w-4 h-4 mr-2" />
                {testEventMutation.isPending ? 'Sending...' : 'Send'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
