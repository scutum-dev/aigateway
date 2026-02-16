import { useState } from 'react'
import {
  useGuardrails,
  useCreateGuardrail,
  useUpdateGuardrail,
  useDeleteGuardrail,
  useGuardrailEvents,
} from '../api/hooks'
import { SkeletonCard } from '../components/Skeleton'
import ConfirmDialog from '../components/ConfirmDialog'
import { useToast } from '../components/Toast'
import type { GuardrailConfig, GuardrailConfigCreate } from '../types'

type Tab = 'profiles' | 'events'

const DEFAULT_NEW: GuardrailConfigCreate = {
  name: '',
  description: '',
  enable_prompt_injection: true,
  prompt_injection_threshold: 0.9,
  enable_pii_detection: true,
  pii_action: 'anonymize',
  pii_entities: ['PERSON', 'EMAIL_ADDRESS', 'PHONE_NUMBER', 'CREDIT_CARD', 'US_SSN', 'IBAN_CODE', 'IP_ADDRESS'],
  enable_toxicity: true,
  toxicity_threshold: 0.7,
  banned_topics: [],
  enable_secrets_detection: true,
  enable_invisible_text: true,
  enable_malicious_urls: true,
  enable_sensitive_output: true,
  mode: 'block',
  on_fail: 'block',
  is_active: true,
}

function Toggle({ enabled, onChange, label, description }: {
  enabled: boolean
  onChange: (v: boolean) => void
  label: string
  description?: string
}) {
  return (
    <div className="flex items-center justify-between py-2">
      <div>
        <span className="font-medium text-sm">{label}</span>
        {description && <p className="text-xs text-gray-500">{description}</p>}
      </div>
      <button
        type="button"
        onClick={() => onChange(!enabled)}
        className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
          enabled ? 'bg-primary-600' : 'bg-gray-300'
        }`}
      >
        <span className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
          enabled ? 'translate-x-6' : 'translate-x-1'
        }`} />
      </button>
    </div>
  )
}

function EventBadge({ type }: { type: string }) {
  const colors: Record<string, string> = {
    input_blocked: 'bg-red-100 text-red-700',
    output_blocked: 'bg-orange-100 text-orange-700',
    pii_detected: 'bg-yellow-100 text-yellow-700',
  }
  return (
    <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${colors[type] || 'bg-gray-100 text-gray-700'}`}>
      {type}
    </span>
  )
}

export default function Guardrails() {
  const [tab, setTab] = useState<Tab>('profiles')
  const { data: configs, isLoading, error } = useGuardrails()
  const { data: events } = useGuardrailEvents()
  const createGuardrail = useCreateGuardrail()
  const updateGuardrail = useUpdateGuardrail()
  const deleteGuardrail = useDeleteGuardrail()
  const toast = useToast()

  const [showCreate, setShowCreate] = useState(false)
  const [editing, setEditing] = useState<GuardrailConfig | null>(null)
  const [form, setForm] = useState<GuardrailConfigCreate>({ ...DEFAULT_NEW })
  const [deleteId, setDeleteId] = useState<string | null>(null)

  const handleCreate = async () => {
    if (!form.name) { toast('error', 'Name is required'); return }
    try {
      await createGuardrail.mutateAsync(form)
      toast('success', 'Guardrail profile created')
      setShowCreate(false)
      setForm({ ...DEFAULT_NEW })
    } catch {
      toast('error', 'Failed to create guardrail profile')
    }
  }

  const handleUpdate = async () => {
    if (!editing) return
    try {
      await updateGuardrail.mutateAsync({ id: editing.id, data: form })
      toast('success', 'Guardrail profile updated')
      setEditing(null)
      setForm({ ...DEFAULT_NEW })
    } catch {
      toast('error', 'Failed to update guardrail profile')
    }
  }

  const handleDelete = async () => {
    if (!deleteId) return
    try {
      await deleteGuardrail.mutateAsync(deleteId)
      toast('success', 'Guardrail profile deleted')
      setDeleteId(null)
    } catch {
      toast('error', 'Failed to delete guardrail profile')
    }
  }

  const openEdit = (cfg: GuardrailConfig) => {
    setEditing(cfg)
    setForm({
      name: cfg.name,
      description: cfg.description || '',
      enable_prompt_injection: cfg.enable_prompt_injection,
      prompt_injection_threshold: cfg.prompt_injection_threshold,
      enable_pii_detection: cfg.enable_pii_detection,
      pii_action: cfg.pii_action,
      pii_entities: cfg.pii_entities,
      enable_toxicity: cfg.enable_toxicity,
      toxicity_threshold: cfg.toxicity_threshold,
      banned_topics: cfg.banned_topics,
      enable_secrets_detection: cfg.enable_secrets_detection,
      enable_invisible_text: cfg.enable_invisible_text,
      enable_malicious_urls: cfg.enable_malicious_urls,
      enable_sensitive_output: cfg.enable_sensitive_output,
      mode: cfg.mode,
      on_fail: cfg.on_fail,
      is_active: cfg.is_active,
    })
    setShowCreate(true)
  }

  if (isLoading) {
    return (
      <div className="space-y-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Guardrails</h1>
          <p className="text-gray-600">Content safety scanning and PII protection</p>
        </div>
        {Array.from({ length: 3 }).map((_, i) => <SkeletonCard key={i} />)}
      </div>
    )
  }

  if (error) {
    return <div className="bg-red-50 text-red-700 p-4 rounded-lg">Failed to load guardrails</div>
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Guardrails</h1>
          <p className="text-gray-600">Content safety scanning and PII protection</p>
        </div>
      </div>

      {/* Tabs */}
      <div className="border-b border-gray-200">
        <nav className="-mb-px flex space-x-8">
          {(['profiles', 'events'] as Tab[]).map((t) => (
            <button
              key={t}
              onClick={() => setTab(t)}
              className={`py-2 px-1 border-b-2 text-sm font-medium capitalize ${
                tab === t
                  ? 'border-primary-600 text-primary-600'
                  : 'border-transparent text-gray-500 hover:text-gray-700'
              }`}
            >
              {t}
            </button>
          ))}
        </nav>
      </div>

      <ConfirmDialog
        isOpen={!!deleteId}
        onClose={() => setDeleteId(null)}
        onConfirm={handleDelete}
        title="Delete Guardrail Profile?"
        message="This will remove the profile and unassign it from all teams."
        confirmLabel="Delete"
        confirmVariant="danger"
      />

      {/* ================================================================= */}
      {/* PROFILES TAB */}
      {/* ================================================================= */}
      {tab === 'profiles' && (
        <div className="space-y-4">
          <div className="flex justify-end">
            <button
              onClick={() => { setShowCreate(true); setEditing(null); setForm({ ...DEFAULT_NEW }) }}
              className="btn btn-primary"
            >
              New Profile
            </button>
          </div>

          {/* Create / Edit modal */}
          {showCreate && (
            <div className="card space-y-4 border-2 border-primary-200">
              <h3 className="font-semibold text-lg">
                {editing ? `Edit: ${editing.name}` : 'New Guardrail Profile'}
              </h3>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <label className="label">Name</label>
                  <input
                    className="input"
                    value={form.name}
                    onChange={(e) => setForm({ ...form, name: e.target.value })}
                  />
                </div>
                <div>
                  <label className="label">Description</label>
                  <input
                    className="input"
                    value={form.description || ''}
                    onChange={(e) => setForm({ ...form, description: e.target.value })}
                  />
                </div>
              </div>

              <h4 className="font-medium text-sm text-gray-700 pt-2">Input Scanners</h4>
              <div className="space-y-1">
                <Toggle
                  label="Prompt Injection Detection"
                  description="Block prompt injection attempts"
                  enabled={form.enable_prompt_injection ?? true}
                  onChange={(v) => setForm({ ...form, enable_prompt_injection: v })}
                />
                {form.enable_prompt_injection && (
                  <div className="pl-4 flex items-center gap-2 text-sm">
                    <label>Threshold:</label>
                    <input
                      type="range" min="0.5" max="1" step="0.05"
                      value={form.prompt_injection_threshold ?? 0.9}
                      onChange={(e) => setForm({ ...form, prompt_injection_threshold: parseFloat(e.target.value) })}
                      className="w-32"
                    />
                    <span className="text-gray-600 w-10">{form.prompt_injection_threshold?.toFixed(2)}</span>
                  </div>
                )}

                <Toggle
                  label="PII Detection"
                  description="Detect and anonymize personally identifiable information"
                  enabled={form.enable_pii_detection ?? true}
                  onChange={(v) => setForm({ ...form, enable_pii_detection: v })}
                />
                {form.enable_pii_detection && (
                  <div className="pl-4">
                    <select
                      className="input text-sm"
                      value={form.pii_action ?? 'anonymize'}
                      onChange={(e) => setForm({ ...form, pii_action: e.target.value })}
                    >
                      <option value="anonymize">Anonymize (replace PII)</option>
                      <option value="detect">Detect only (log but allow)</option>
                    </select>
                  </div>
                )}

                <Toggle
                  label="Toxicity Detection"
                  description="Block toxic, hateful, or harmful content"
                  enabled={form.enable_toxicity ?? true}
                  onChange={(v) => setForm({ ...form, enable_toxicity: v })}
                />
                {form.enable_toxicity && (
                  <div className="pl-4 flex items-center gap-2 text-sm">
                    <label>Threshold:</label>
                    <input
                      type="range" min="0.3" max="1" step="0.05"
                      value={form.toxicity_threshold ?? 0.7}
                      onChange={(e) => setForm({ ...form, toxicity_threshold: parseFloat(e.target.value) })}
                      className="w-32"
                    />
                    <span className="text-gray-600 w-10">{form.toxicity_threshold?.toFixed(2)}</span>
                  </div>
                )}

                <Toggle
                  label="Secrets Detection"
                  description="Block API keys, passwords, and other secrets"
                  enabled={form.enable_secrets_detection ?? true}
                  onChange={(v) => setForm({ ...form, enable_secrets_detection: v })}
                />

                <Toggle
                  label="Invisible Text Detection"
                  description="Detect hidden Unicode characters used in attacks"
                  enabled={form.enable_invisible_text ?? true}
                  onChange={(v) => setForm({ ...form, enable_invisible_text: v })}
                />
              </div>

              <h4 className="font-medium text-sm text-gray-700 pt-2">Output Scanners</h4>
              <div className="space-y-1">
                <Toggle
                  label="Malicious URL Detection"
                  description="Block responses containing malicious URLs"
                  enabled={form.enable_malicious_urls ?? true}
                  onChange={(v) => setForm({ ...form, enable_malicious_urls: v })}
                />
                <Toggle
                  label="Sensitive Data Detection"
                  description="Detect sensitive information in model outputs"
                  enabled={form.enable_sensitive_output ?? true}
                  onChange={(v) => setForm({ ...form, enable_sensitive_output: v })}
                />
              </div>

              <h4 className="font-medium text-sm text-gray-700 pt-2">Banned Topics</h4>
              <div>
                <input
                  className="input text-sm"
                  placeholder="Enter comma-separated topics (e.g. weapons, illegal drugs)"
                  value={(form.banned_topics ?? []).join(', ')}
                  onChange={(e) => setForm({
                    ...form,
                    banned_topics: e.target.value ? e.target.value.split(',').map(s => s.trim()).filter(Boolean) : [],
                  })}
                />
              </div>

              <h4 className="font-medium text-sm text-gray-700 pt-2">Behavior</h4>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="label">On Failure</label>
                  <select
                    className="input"
                    value={form.on_fail ?? 'block'}
                    onChange={(e) => setForm({ ...form, on_fail: e.target.value })}
                  >
                    <option value="block">Block request</option>
                    <option value="log">Log only (allow)</option>
                  </select>
                </div>
                <div className="flex items-end">
                  <Toggle
                    label="Active"
                    enabled={form.is_active ?? true}
                    onChange={(v) => setForm({ ...form, is_active: v })}
                  />
                </div>
              </div>

              <div className="flex gap-2 pt-2">
                <button
                  onClick={editing ? handleUpdate : handleCreate}
                  className="btn btn-primary"
                  disabled={createGuardrail.isPending || updateGuardrail.isPending}
                >
                  {editing ? 'Update' : 'Create'}
                </button>
                <button
                  onClick={() => { setShowCreate(false); setEditing(null) }}
                  className="btn bg-gray-200 text-gray-700 hover:bg-gray-300"
                >
                  Cancel
                </button>
              </div>
            </div>
          )}

          {/* Profiles table */}
          <div className="card overflow-hidden p-0">
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Name</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Scanners</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">On Fail</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Status</th>
                  <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-200">
                {(configs ?? []).map((cfg) => {
                  const enabledScanners = [
                    cfg.enable_prompt_injection ? 'Injection' : null,
                    cfg.enable_pii_detection ? 'PII' : null,
                    cfg.enable_toxicity ? 'Toxicity' : null,
                    cfg.enable_secrets_detection ? 'Secrets' : null,
                    cfg.enable_invisible_text ? 'Invisible' : null,
                    cfg.enable_malicious_urls ? 'URLs' : null,
                    cfg.enable_sensitive_output ? 'Sensitive' : null,
                  ].filter((s): s is string => s !== null)

                  return (
                    <tr key={cfg.id} className="hover:bg-gray-50">
                      <td className="px-4 py-3">
                        <div className="font-medium text-sm">{cfg.name}</div>
                        {cfg.description && <div className="text-xs text-gray-500">{cfg.description}</div>}
                      </td>
                      <td className="px-4 py-3">
                        <div className="flex flex-wrap gap-1">
                          {enabledScanners.map((s) => (
                            <span key={s} className="px-1.5 py-0.5 bg-blue-50 text-blue-700 rounded text-xs">
                              {s}
                            </span>
                          ))}
                        </div>
                      </td>
                      <td className="px-4 py-3 text-sm capitalize">{cfg.on_fail}</td>
                      <td className="px-4 py-3">
                        <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${
                          cfg.is_active ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-500'
                        }`}>
                          {cfg.is_active ? 'Active' : 'Inactive'}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-right space-x-2">
                        <button
                          onClick={() => openEdit(cfg)}
                          className="text-sm text-primary-600 hover:text-primary-800"
                        >
                          Edit
                        </button>
                        <button
                          onClick={() => setDeleteId(cfg.id)}
                          className="text-sm text-red-600 hover:text-red-800"
                        >
                          Delete
                        </button>
                      </td>
                    </tr>
                  )
                })}
                {(configs ?? []).length === 0 && (
                  <tr>
                    <td colSpan={5} className="px-4 py-8 text-center text-gray-500">
                      No guardrail profiles configured
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* ================================================================= */}
      {/* EVENTS TAB */}
      {/* ================================================================= */}
      {tab === 'events' && (
        <div className="card overflow-hidden p-0">
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Time</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Event</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Scanner</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Model</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Risk</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200">
              {(events ?? []).map((evt) => (
                <tr key={evt.id} className="hover:bg-gray-50">
                  <td className="px-4 py-3 text-xs text-gray-500 whitespace-nowrap">
                    {evt.created_at ? new Date(evt.created_at).toLocaleString() : '-'}
                  </td>
                  <td className="px-4 py-3"><EventBadge type={evt.event_type} /></td>
                  <td className="px-4 py-3 text-sm">{evt.scanner_name}</td>
                  <td className="px-4 py-3 text-sm text-gray-600">{evt.model || '-'}</td>
                  <td className="px-4 py-3 text-sm">
                    {evt.risk_score != null ? evt.risk_score.toFixed(4) : '-'}
                  </td>
                  <td className="px-4 py-3 text-sm capitalize">{evt.action_taken}</td>
                </tr>
              ))}
              {(events ?? []).length === 0 && (
                <tr>
                  <td colSpan={6} className="px-4 py-8 text-center text-gray-500">
                    No guardrail events recorded yet
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      )}

    </div>
  )
}
