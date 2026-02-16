import { useState, useEffect } from 'react'
import { useSettings, useUpdateSettings } from '../api/hooks'
import { SkeletonCard } from '../components/Skeleton'
import ConfirmDialog from '../components/ConfirmDialog'
import { useToast } from '../components/Toast'
import type { PlatformSettings } from '../types'

export default function Settings() {
  const { data: settings, isLoading, error } = useSettings()
  const updateSettings = useUpdateSettings()
  const toast = useToast()
  const [form, setForm] = useState<PlatformSettings>({
    default_model: 'gpt-4o-mini',
    global_rate_limit: 1000,
    enable_caching: true,
    cache_ttl_seconds: 3600,
    enable_cost_tracking: true,
    enable_budget_enforcement: true,
    enable_routing_policies: true,
    maintenance_mode: false,
  })
  const [showMaintenanceConfirm, setShowMaintenanceConfirm] = useState(false)

  useEffect(() => {
    if (settings) {
      setForm(settings)
    }
  }, [settings])

  if (isLoading) {
    return (
      <div className="space-y-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Settings</h1>
          <p className="text-gray-600">Platform-wide configuration</p>
        </div>
        {Array.from({ length: 4 }).map((_, i) => <SkeletonCard key={i} />)}
      </div>
    )
  }

  if (error) {
    return (
      <div className="bg-red-50 text-red-700 p-4 rounded-lg">
        Failed to load settings
      </div>
    )
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    try {
      await updateSettings.mutateAsync(form)
      toast('success', 'Settings saved successfully')
    } catch {
      toast('error', 'Failed to save settings')
    }
  }

  const handleMaintenanceToggle = () => {
    if (!form.maintenance_mode) {
      setShowMaintenanceConfirm(true)
    } else {
      setForm({ ...form, maintenance_mode: false })
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Settings</h1>
        <p className="text-gray-600">Platform-wide configuration</p>
      </div>

      <ConfirmDialog
        isOpen={showMaintenanceConfirm}
        onClose={() => setShowMaintenanceConfirm(false)}
        onConfirm={() => setForm({ ...form, maintenance_mode: true })}
        title="Enable Maintenance Mode?"
        message="This will block all API requests except health checks. Make sure to save settings after confirming."
        confirmLabel="Enable Maintenance Mode"
        confirmVariant="danger"
      />

      <form onSubmit={handleSubmit} className="space-y-6">
        {/* General Settings */}
        <div className="card">
          <h2 className="text-lg font-semibold mb-4">General</h2>
          <div className="space-y-4">
            <div>
              <label className="label">Default Model</label>
              <input
                type="text"
                value={form.default_model}
                onChange={(e) =>
                  setForm({ ...form, default_model: e.target.value })
                }
                className="input"
              />
              <p className="text-sm text-gray-500 mt-1">
                Model used when no specific model is requested
              </p>
            </div>
            <div>
              <label className="label">Global Rate Limit (req/min)</label>
              <input
                type="number"
                value={form.global_rate_limit}
                onChange={(e) =>
                  setForm({
                    ...form,
                    global_rate_limit: parseInt(e.target.value),
                  })
                }
                className="input"
              />
            </div>
          </div>
        </div>

        {/* Caching Settings */}
        <div className="card">
          <h2 className="text-lg font-semibold mb-4">Caching</h2>
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <div>
                <label className="font-medium">Enable Caching</label>
                <p className="text-sm text-gray-500">
                  Cache LLM responses for identical requests
                </p>
              </div>
              <button
                type="button"
                onClick={() =>
                  setForm({ ...form, enable_caching: !form.enable_caching })
                }
                className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
                  form.enable_caching ? 'bg-primary-600' : 'bg-gray-300'
                }`}
              >
                <span
                  className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
                    form.enable_caching ? 'translate-x-6' : 'translate-x-1'
                  }`}
                />
              </button>
            </div>
            <div>
              <label className="label">Cache TTL (seconds)</label>
              <input
                type="number"
                value={form.cache_ttl_seconds}
                onChange={(e) =>
                  setForm({
                    ...form,
                    cache_ttl_seconds: parseInt(e.target.value),
                  })
                }
                className="input"
                disabled={!form.enable_caching}
              />
            </div>
          </div>
        </div>

        {/* Feature Toggles */}
        <div className="card">
          <h2 className="text-lg font-semibold mb-4">Features</h2>
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <div>
                <label className="font-medium">Cost Tracking</label>
                <p className="text-sm text-gray-500">
                  Track token usage and costs per request
                </p>
              </div>
              <button
                type="button"
                onClick={() =>
                  setForm({
                    ...form,
                    enable_cost_tracking: !form.enable_cost_tracking,
                  })
                }
                className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
                  form.enable_cost_tracking ? 'bg-primary-600' : 'bg-gray-300'
                }`}
              >
                <span
                  className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
                    form.enable_cost_tracking ? 'translate-x-6' : 'translate-x-1'
                  }`}
                />
              </button>
            </div>

            <div className="flex items-center justify-between">
              <div>
                <label className="font-medium">Budget Enforcement</label>
                <p className="text-sm text-gray-500">
                  Enforce budget limits and alerts
                </p>
              </div>
              <button
                type="button"
                onClick={() =>
                  setForm({
                    ...form,
                    enable_budget_enforcement: !form.enable_budget_enforcement,
                  })
                }
                className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
                  form.enable_budget_enforcement
                    ? 'bg-primary-600'
                    : 'bg-gray-300'
                }`}
              >
                <span
                  className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
                    form.enable_budget_enforcement
                      ? 'translate-x-6'
                      : 'translate-x-1'
                  }`}
                />
              </button>
            </div>

            <div className="flex items-center justify-between">
              <div>
                <label className="font-medium">Routing Policies</label>
                <p className="text-sm text-gray-500">
                  Enable Cedar policy-based routing
                </p>
              </div>
              <button
                type="button"
                onClick={() =>
                  setForm({
                    ...form,
                    enable_routing_policies: !form.enable_routing_policies,
                  })
                }
                className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
                  form.enable_routing_policies
                    ? 'bg-primary-600'
                    : 'bg-gray-300'
                }`}
              >
                <span
                  className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
                    form.enable_routing_policies
                      ? 'translate-x-6'
                      : 'translate-x-1'
                  }`}
                />
              </button>
            </div>
          </div>
        </div>

        {/* Maintenance Mode */}
        <div className="card border-2 border-red-200">
          <h2 className="text-lg font-semibold mb-4 text-red-700">
            Maintenance Mode
          </h2>
          <div className="flex items-center justify-between">
            <div>
              <label className="font-medium">Enable Maintenance Mode</label>
              <p className="text-sm text-gray-500">
                Block all API requests except health checks
              </p>
            </div>
            <button
              type="button"
              onClick={handleMaintenanceToggle}
              className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
                form.maintenance_mode ? 'bg-red-600' : 'bg-gray-300'
              }`}
            >
              <span
                className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
                  form.maintenance_mode ? 'translate-x-6' : 'translate-x-1'
                }`}
              />
            </button>
          </div>
        </div>

        {/* Save Button */}
        <div>
          <button type="submit" className="btn btn-primary">
            Save Settings
          </button>
        </div>
      </form>
    </div>
  )
}
