import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useModels, useBudgets, useTeams, useRealtimeMetrics } from '../api/hooks'
import {
  CheckCircleIcon,
  XMarkIcon,
} from '@heroicons/react/24/outline'

const DISMISS_KEY = 'onboarding_dismissed'

export default function Onboarding() {
  const [dismissed, setDismissed] = useState(
    () => localStorage.getItem(DISMISS_KEY) === '1'
  )
  const { data: models } = useModels()
  const { data: budgets } = useBudgets()
  const { data: teams } = useTeams()
  const { data: metrics } = useRealtimeMetrics()

  if (dismissed) return null

  const providerStatus = metrics?.provider_status || {}
  const hasApiKeys = Object.values(providerStatus).some(Boolean)
  const hasModels = (models?.length || 0) > 0
  const hasBudget = (budgets?.length || 0) > 0
  const hasTeam = (teams?.length || 0) > 0

  const steps = [
    { label: 'API keys configured', done: hasApiKeys, href: '/api-keys' },
    { label: 'Models available', done: hasModels, href: '/models' },
    { label: 'First budget set', done: hasBudget, href: '/budgets' },
    { label: 'Team created', done: hasTeam, href: '/teams' },
    { label: 'Settings reviewed', done: false, href: '/settings' },
  ]

  const completed = steps.filter((s) => s.done).length
  const progress = (completed / steps.length) * 100

  const handleDismiss = () => {
    localStorage.setItem(DISMISS_KEY, '1')
    setDismissed(true)
  }

  return (
    <div className="card border border-indigo-200 bg-indigo-50/50">
      <div className="flex items-start justify-between mb-4">
        <div>
          <h3 className="font-semibold text-gray-900">Getting Started</h3>
          <p className="text-sm text-gray-600">
            Complete these steps to set up your gateway
          </p>
        </div>
        <button
          onClick={handleDismiss}
          className="text-gray-400 hover:text-gray-600"
          title="Dismiss"
        >
          <XMarkIcon className="w-5 h-5" />
        </button>
      </div>

      <div className="mb-4">
        <div className="flex justify-between text-sm mb-1">
          <span className="text-gray-600">
            {completed} of {steps.length} complete
          </span>
          <span className="text-gray-500">{Math.round(progress)}%</span>
        </div>
        <div className="w-full bg-gray-200 rounded-full h-2">
          <div
            className="h-2 rounded-full bg-indigo-500 transition-all duration-500"
            style={{ width: `${progress}%` }}
          />
        </div>
      </div>

      <ul className="space-y-2">
        {steps.map((step) => (
          <li key={step.label}>
            <Link
              to={step.href}
              className="flex items-center gap-3 px-3 py-2 rounded-lg hover:bg-white/60 transition-colors"
            >
              <CheckCircleIcon
                className={`w-5 h-5 flex-shrink-0 ${
                  step.done ? 'text-green-500' : 'text-gray-300'
                }`}
              />
              <span
                className={`text-sm ${
                  step.done ? 'text-gray-500 line-through' : 'text-gray-800'
                }`}
              >
                {step.label}
              </span>
            </Link>
          </li>
        ))}
      </ul>
    </div>
  )
}
