import { useRealtimeMetrics } from '../api/hooks'
import {
  ChartBarIcon,
  CurrencyDollarIcon,
  BoltIcon,
  ExclamationCircleIcon,
} from '@heroicons/react/24/outline'

export default function Dashboard() {
  const { data: metrics, isLoading, error } = useRealtimeMetrics()

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-t-2 border-b-2 border-primary-600"></div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="bg-red-50 text-red-700 p-4 rounded-lg">
        Failed to load metrics
      </div>
    )
  }

  const stats = [
    {
      name: 'Requests/min',
      value: metrics?.requests_per_minute || 0,
      icon: ChartBarIcon,
      color: 'bg-blue-500',
    },
    {
      name: 'Cost Today',
      value: `$${(metrics?.total_cost_today || 0).toFixed(2)}`,
      icon: CurrencyDollarIcon,
      color: 'bg-green-500',
    },
    {
      name: 'Tokens Today',
      value: (metrics?.total_tokens_today || 0).toLocaleString(),
      icon: BoltIcon,
      color: 'bg-purple-500',
    },
    {
      name: 'Error Rate',
      value: `${((metrics?.error_rate || 0) * 100).toFixed(1)}%`,
      icon: ExclamationCircleIcon,
      color: 'bg-red-500',
    },
  ]

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Dashboard</h1>
        <p className="text-gray-600">Platform overview and real-time metrics</p>
      </div>

      {/* Stats Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        {stats.map((stat) => (
          <div key={stat.name} className="card flex items-center">
            <div className={`p-3 rounded-lg ${stat.color}`}>
              <stat.icon className="w-6 h-6 text-white" />
            </div>
            <div className="ml-4">
              <p className="text-sm text-gray-500">{stat.name}</p>
              <p className="text-2xl font-semibold">{stat.value}</p>
            </div>
          </div>
        ))}
      </div>

      {/* Provider Status */}
      <div className="card">
        <h2 className="text-lg font-semibold mb-4">Provider Status</h2>
        <div className="space-y-3">
          {metrics?.provider_status &&
            Object.entries(metrics.provider_status).map(([provider, status]) => (
              <div key={provider} className="flex items-center justify-between">
                <span className="font-medium capitalize">{provider}</span>
                <span
                  className={`px-3 py-1 rounded-full text-sm ${
                    status
                      ? 'bg-green-100 text-green-700'
                      : 'bg-red-100 text-red-700'
                  }`}
                >
                  {status ? 'Online' : 'Offline'}
                </span>
              </div>
            ))}
        </div>
      </div>

      {/* Model Usage */}
      <div className="card">
        <h2 className="text-lg font-semibold mb-4">Model Usage Today</h2>
        {metrics?.model_usage && Object.keys(metrics.model_usage).length > 0 ? (
          <div className="space-y-3">
            {Object.entries(metrics.model_usage)
              .sort(([, a], [, b]) => (b as number) - (a as number))
              .map(([model, count]) => (
                <div key={model} className="flex items-center justify-between">
                  <span className="font-mono text-sm">{model}</span>
                  <span className="text-gray-600">{String(count)} requests</span>
                </div>
              ))}
          </div>
        ) : (
          <p className="text-gray-500">No usage data available</p>
        )}
      </div>
    </div>
  )
}
