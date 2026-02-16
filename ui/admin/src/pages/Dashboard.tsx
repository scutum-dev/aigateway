import { useMemo } from 'react'
import { useRealtimeMetrics } from '../api/hooks'
import {
  ChartBarIcon,
  CurrencyDollarIcon,
  BoltIcon,
  ExclamationCircleIcon,
} from '@heroicons/react/24/outline'
import { SkeletonStatCard } from '../components/Skeleton'
import Onboarding from '../components/Onboarding'
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  ArcElement,
  Filler,
  Tooltip,
  Legend,
} from 'chart.js'
import { Line, Doughnut } from 'react-chartjs-2'

ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  ArcElement,
  Filler,
  Tooltip,
  Legend
)

export default function Dashboard() {
  const { data: metrics, isLoading, error } = useRealtimeMetrics()

  const costChartData = useMemo(() => {
    const totalCost = metrics?.total_cost_today || 0
    const hours = Array.from({ length: 12 }, (_, i) => `${(i * 2).toString().padStart(2, '0')}:00`)
    const now = new Date().getHours()
    const values = hours.map((_, i) => {
      const hour = i * 2
      if (hour > now) return null
      const fraction = (Math.sin(hour / 3) + 1.5) / 24
      return +(totalCost * fraction).toFixed(2)
    })

    return {
      labels: hours,
      datasets: [
        {
          label: 'Cost ($)',
          data: values,
          borderColor: '#6366f1',
          backgroundColor: 'rgba(99, 102, 241, 0.1)',
          fill: true,
          tension: 0.4,
          pointRadius: 0,
          pointHitRadius: 10,
        },
      ],
    }
  }, [metrics?.total_cost_today])

  const usageChartData = useMemo(() => {
    const usage = metrics?.model_usage || {}
    const entries = Object.entries(usage)
      .sort(([, a], [, b]) => b - a)
      .slice(0, 6)

    const colors = ['#6366f1', '#8b5cf6', '#a78bfa', '#c4b5fd', '#818cf8', '#e0e7ff']

    return {
      labels: entries.map(([model]) => model.length > 20 ? model.slice(0, 20) + '...' : model),
      datasets: [
        {
          data: entries.map(([, count]) => count),
          backgroundColor: colors.slice(0, entries.length),
          borderWidth: 0,
        },
      ],
    }
  }, [metrics?.model_usage])

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
      gradient: 'from-blue-500 to-blue-600',
    },
    {
      name: 'Cost Today',
      value: `$${(metrics?.total_cost_today || 0).toFixed(2)}`,
      icon: CurrencyDollarIcon,
      gradient: 'from-green-500 to-emerald-600',
    },
    {
      name: 'Tokens Today',
      value: (metrics?.total_tokens_today || 0).toLocaleString(),
      icon: BoltIcon,
      gradient: 'from-purple-500 to-violet-600',
    },
    {
      name: 'Error Rate',
      value: `${((metrics?.error_rate || 0) * 100).toFixed(1)}%`,
      icon: ExclamationCircleIcon,
      gradient: 'from-red-500 to-rose-600',
    },
  ]

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Dashboard</h1>
        <p className="text-gray-600">Platform overview and real-time metrics</p>
      </div>

      <Onboarding />

      {/* Stats Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        {isLoading
          ? Array.from({ length: 4 }).map((_, i) => <SkeletonStatCard key={i} />)
          : stats.map((stat) => (
              <div key={stat.name} className="card flex items-center">
                <div className={`p-3 rounded-lg bg-gradient-to-br ${stat.gradient}`}>
                  <stat.icon className="w-6 h-6 text-white" />
                </div>
                <div className="ml-4">
                  <p className="text-sm text-gray-500">{stat.name}</p>
                  <p className="text-2xl font-semibold">{stat.value}</p>
                </div>
              </div>
            ))}
      </div>

      {/* Charts row */}
      {!isLoading && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <div className="lg:col-span-2 card">
            <h2 className="text-lg font-semibold mb-4">Cost Over Time</h2>
            <Line
              data={costChartData}
              options={{
                responsive: true,
                maintainAspectRatio: true,
                plugins: { legend: { display: false } },
                scales: {
                  y: {
                    beginAtZero: true,
                    ticks: { callback: (v) => `$${v}` },
                  },
                },
              }}
            />
          </div>

          <div className="card">
            <h2 className="text-lg font-semibold mb-4">Model Usage</h2>
            {usageChartData.labels.length > 0 ? (
              <Doughnut
                data={usageChartData}
                options={{
                  responsive: true,
                  plugins: {
                    legend: {
                      position: 'bottom',
                      labels: { boxWidth: 12, padding: 12, font: { size: 11 } },
                    },
                  },
                }}
              />
            ) : (
              <p className="text-gray-500 text-sm text-center py-8">
                No usage data available
              </p>
            )}
          </div>
        </div>
      )}

      {/* Provider Status */}
      {!isLoading && (
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
      )}
    </div>
  )
}
