import { useState } from 'react'
import {
  useCostAllocationRules,
  useCreateCostAllocationRule,
  useDeleteCostAllocationRule,
  useChargebackReports,
  useBudgetForecasts,
} from '../api/hooks'
import { chargebackApi } from '../api/client'
import type { CostAllocationRuleCreate } from '../types'
import { PlusIcon, TrashIcon, ArrowDownTrayIcon, CheckCircleIcon, ArrowPathIcon } from '@heroicons/react/24/outline'
import { SkeletonCard } from '../components/Skeleton'
import { useToast } from '../components/Toast'

type TabId = 'rules' | 'reports' | 'forecasts'

const statusColors: Record<string, string> = {
  draft: 'bg-yellow-100 text-yellow-800',
  finalized: 'bg-green-100 text-green-800',
}

export default function Chargeback() {
  const toast = useToast()
  const [activeTab, setActiveTab] = useState<TabId>('rules')
  const [showCreateRule, setShowCreateRule] = useState(false)
  const [showGenerateReport, setShowGenerateReport] = useState(false)
  const [reportPeriod, setReportPeriod] = useState('')
  const [generating, setGenerating] = useState(false)
  const [forecastGenerating, setForecastGenerating] = useState(false)

  const { data: rules, isLoading: rulesLoading } = useCostAllocationRules()
  const { data: reports, isLoading: reportsLoading } = useChargebackReports()
  const { data: forecasts, isLoading: forecastsLoading } = useBudgetForecasts()
  const createRuleMutation = useCreateCostAllocationRule()
  const deleteRuleMutation = useDeleteCostAllocationRule()

  const [ruleForm, setRuleForm] = useState<CostAllocationRuleCreate>({
    name: '',
    allocation_type: 'department',
    allocation_target: '',
    allocation_percent: 100,
  })

  const handleCreateRule = async () => {
    try {
      await createRuleMutation.mutateAsync(ruleForm)
      toast('success', 'Allocation rule created')
      setShowCreateRule(false)
      setRuleForm({ name: '', allocation_type: 'department', allocation_target: '', allocation_percent: 100 })
    } catch {
      toast('error', 'Failed to create rule')
    }
  }

  const handleDeleteRule = async (id: string) => {
    if (!confirm('Delete this allocation rule?')) return
    try {
      await deleteRuleMutation.mutateAsync(id)
      toast('success', 'Rule deleted')
    } catch {
      toast('error', 'Failed to delete rule')
    }
  }

  const handleGenerateReport = async () => {
    if (!reportPeriod) return
    setGenerating(true)
    try {
      await chargebackApi.generateReport(reportPeriod)
      toast('success', 'Chargeback report generated')
      setShowGenerateReport(false)
      setReportPeriod('')
      window.location.reload()
    } catch {
      toast('error', 'Failed to generate report')
    } finally {
      setGenerating(false)
    }
  }

  const handleExport = async (id: string, format: string) => {
    try {
      const blob = await chargebackApi.exportReport(id, format)
      const url = window.URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `chargeback_report.${format}`
      a.click()
      window.URL.revokeObjectURL(url)
      toast('success', `Report exported as ${format.toUpperCase()}`)
    } catch {
      toast('error', 'Failed to export report')
    }
  }

  const handleFinalize = async (id: string) => {
    if (!confirm('Finalize this report? This cannot be undone.')) return
    try {
      await chargebackApi.finalizeReport(id)
      toast('success', 'Report finalized')
      window.location.reload()
    } catch {
      toast('error', 'Failed to finalize report')
    }
  }

  const handleGenerateForecast = async () => {
    setForecastGenerating(true)
    try {
      await chargebackApi.generateForecast()
      toast('success', 'Forecast generated')
      window.location.reload()
    } catch {
      toast('error', 'Failed to generate forecast')
    } finally {
      setForecastGenerating(false)
    }
  }

  const ruleList = Array.isArray(rules) ? rules : []
  const reportList = Array.isArray(reports) ? reports : []
  const forecastList = Array.isArray(forecasts) ? forecasts : []

  const tabs: { id: TabId; label: string; count: number }[] = [
    { id: 'rules', label: 'Allocation Rules', count: ruleList.length },
    { id: 'reports', label: 'Reports', count: reportList.length },
    { id: 'forecasts', label: 'Forecasts', count: forecastList.length },
  ]

  const isLoading = rulesLoading || reportsLoading || forecastsLoading

  if (isLoading) {
    return (
      <div className="space-y-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Chargeback</h1>
          <p className="text-gray-600">Cost allocation, chargeback reports, and budget forecasts</p>
        </div>
        <SkeletonCard />
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Chargeback</h1>
          <p className="text-gray-600">Cost allocation, chargeback reports, and budget forecasts</p>
        </div>
        <div className="flex gap-2">
          {activeTab === 'rules' && (
            <button onClick={() => setShowCreateRule(true)} className="btn btn-primary">
              <PlusIcon className="w-4 h-4 mr-1" />
              New Rule
            </button>
          )}
          {activeTab === 'reports' && (
            <button onClick={() => setShowGenerateReport(true)} className="btn btn-primary">
              <PlusIcon className="w-4 h-4 mr-1" />
              Generate Report
            </button>
          )}
          {activeTab === 'forecasts' && (
            <button onClick={handleGenerateForecast} disabled={forecastGenerating} className="btn btn-primary">
              <ArrowPathIcon className={`w-4 h-4 mr-1 ${forecastGenerating ? 'animate-spin' : ''}`} />
              {forecastGenerating ? 'Generating...' : 'Generate Forecast'}
            </button>
          )}
        </div>
      </div>

      {/* Tabs */}
      <div className="border-b border-gray-200">
        <nav className="flex space-x-8">
          {tabs.map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`pb-3 px-1 border-b-2 text-sm font-medium ${
                activeTab === tab.id
                  ? 'border-primary-600 text-primary-600'
                  : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
              }`}
            >
              {tab.label}
              {tab.count > 0 && (
                <span className={`ml-2 px-2 py-0.5 rounded-full text-xs ${
                  activeTab === tab.id ? 'bg-primary-100 text-primary-800' : 'bg-gray-100 text-gray-600'
                }`}>
                  {tab.count}
                </span>
              )}
            </button>
          ))}
        </nav>
      </div>

      {/* Create Rule Modal */}
      {showCreateRule && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg p-6 w-full max-w-lg">
            <h2 className="text-xl font-bold mb-4">Create Allocation Rule</h2>
            <div className="space-y-4">
              <div>
                <label className="label">Name</label>
                <input
                  type="text"
                  value={ruleForm.name}
                  onChange={(e) => setRuleForm({ ...ruleForm, name: e.target.value })}
                  className="input"
                  placeholder="e.g. Engineering Team Split"
                />
              </div>
              <div>
                <label className="label">Team ID (optional)</label>
                <input
                  type="text"
                  value={ruleForm.team_id || ''}
                  onChange={(e) => setRuleForm({ ...ruleForm, team_id: e.target.value || undefined })}
                  className="input"
                  placeholder="UUID of the team"
                />
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="label">Allocation Type</label>
                  <select
                    value={ruleForm.allocation_type}
                    onChange={(e) => setRuleForm({ ...ruleForm, allocation_type: e.target.value })}
                    className="input"
                  >
                    <option value="department">Department</option>
                    <option value="project">Project</option>
                    <option value="cost_center">Cost Center</option>
                    <option value="direct">Direct</option>
                  </select>
                </div>
                <div>
                  <label className="label">Allocation Target</label>
                  <input
                    type="text"
                    value={ruleForm.allocation_target}
                    onChange={(e) => setRuleForm({ ...ruleForm, allocation_target: e.target.value })}
                    className="input"
                    placeholder="e.g. engineering, marketing"
                  />
                </div>
              </div>
              <div>
                <label className="label">Allocation Percent</label>
                <input
                  type="number"
                  min="0"
                  max="100"
                  step="0.01"
                  value={ruleForm.allocation_percent ?? 100}
                  onChange={(e) => setRuleForm({ ...ruleForm, allocation_percent: Number(e.target.value) })}
                  className="input"
                />
              </div>
              <div className="flex justify-end gap-2">
                <button onClick={() => setShowCreateRule(false)} className="btn btn-secondary">Cancel</button>
                <button
                  onClick={handleCreateRule}
                  className="btn btn-primary"
                  disabled={!ruleForm.name || !ruleForm.allocation_target}
                >
                  Create
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Generate Report Modal */}
      {showGenerateReport && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg p-6 w-full max-w-md">
            <h2 className="text-xl font-bold mb-4">Generate Chargeback Report</h2>
            <div className="space-y-4">
              <div>
                <label className="label">Report Period (YYYY-MM)</label>
                <input
                  type="month"
                  value={reportPeriod}
                  onChange={(e) => setReportPeriod(e.target.value)}
                  className="input"
                />
              </div>
              <div className="flex justify-end gap-2">
                <button onClick={() => setShowGenerateReport(false)} className="btn btn-secondary">Cancel</button>
                <button
                  onClick={handleGenerateReport}
                  className="btn btn-primary"
                  disabled={!reportPeriod || generating}
                >
                  {generating ? 'Generating...' : 'Generate'}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Rules Tab */}
      {activeTab === 'rules' && (
        <>
          {ruleList.length === 0 ? (
            <div className="card text-center text-gray-500 py-12">
              <p className="text-lg font-medium">No allocation rules defined</p>
              <p className="text-sm mt-1">Create rules to allocate costs across departments or projects.</p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-gray-200">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Name</th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Team ID</th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Type</th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Target</th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Percent</th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Actions</th>
                  </tr>
                </thead>
                <tbody className="bg-white divide-y divide-gray-200">
                  {ruleList.map((rule) => (
                    <tr key={rule.id} className="hover:bg-gray-50">
                      <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">{rule.name}</td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                        {rule.team_id ? <code className="bg-gray-100 px-2 py-0.5 rounded text-xs">{rule.team_id}</code> : '--'}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap">
                        <span className="px-2 py-0.5 text-xs rounded-full bg-blue-100 text-blue-800">{rule.allocation_type}</span>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-600">{rule.allocation_target}</td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-600">{rule.allocation_percent}%</td>
                      <td className="px-6 py-4 whitespace-nowrap">
                        <button
                          onClick={() => handleDeleteRule(rule.id)}
                          className="p-1 text-gray-400 hover:text-red-600"
                          title="Delete rule"
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

      {/* Reports Tab */}
      {activeTab === 'reports' && (
        <>
          {reportList.length === 0 ? (
            <div className="card text-center text-gray-500 py-12">
              <p className="text-lg font-medium">No chargeback reports</p>
              <p className="text-sm mt-1">Generate a report for a billing period to see cost breakdowns.</p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-gray-200">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Period</th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Status</th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Total Cost</th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Generated By</th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Created</th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Actions</th>
                  </tr>
                </thead>
                <tbody className="bg-white divide-y divide-gray-200">
                  {reportList.map((report) => (
                    <tr key={report.id} className="hover:bg-gray-50">
                      <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">{report.report_period}</td>
                      <td className="px-6 py-4 whitespace-nowrap">
                        <span className={`px-2 py-1 text-xs font-medium rounded-full ${statusColors[report.status] || 'bg-gray-100 text-gray-800'}`}>
                          {report.status}
                        </span>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-600">${report.total_cost.toFixed(4)}</td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">{report.generated_by || '--'}</td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                        {report.created_at ? new Date(report.created_at).toLocaleString() : '--'}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap">
                        <div className="flex gap-1">
                          <button
                            onClick={() => handleExport(report.id, 'csv')}
                            className="p-1 text-gray-500 hover:text-blue-600"
                            title="Export CSV"
                          >
                            <ArrowDownTrayIcon className="w-4 h-4" />
                          </button>
                          {report.status === 'draft' && (
                            <button
                              onClick={() => handleFinalize(report.id)}
                              className="p-1 text-gray-500 hover:text-green-600"
                              title="Finalize report"
                            >
                              <CheckCircleIcon className="w-4 h-4" />
                            </button>
                          )}
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </>
      )}

      {/* Forecasts Tab */}
      {activeTab === 'forecasts' && (
        <>
          {forecastList.length === 0 ? (
            <div className="card text-center text-gray-500 py-12">
              <p className="text-lg font-medium">No forecasts generated</p>
              <p className="text-sm mt-1">Generate a forecast based on historical spending patterns.</p>
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {forecastList.map((forecast) => (
                <div key={forecast.id} className="card">
                  <div className="flex justify-between items-start">
                    <div>
                      <h3 className="text-lg font-semibold">{forecast.forecast_period}</h3>
                      <p className="text-sm text-gray-500">
                        {forecast.team_id ? `Team: ${forecast.team_id}` : 'All Teams'}
                      </p>
                    </div>
                    <span className="px-2 py-0.5 text-xs rounded-full bg-purple-100 text-purple-800">
                      {forecast.forecast_type}
                    </span>
                  </div>
                  <div className="mt-4 space-y-2">
                    <div className="flex justify-between">
                      <span className="text-sm text-gray-600">Forecasted</span>
                      <span className="text-sm font-semibold">${forecast.forecasted_cost.toFixed(4)}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-sm text-gray-600">Confidence Range</span>
                      <span className="text-sm text-gray-500">
                        ${forecast.confidence_low.toFixed(2)} - ${forecast.confidence_high.toFixed(2)}
                      </span>
                    </div>
                    {forecast.actual_cost !== null && (
                      <div className="flex justify-between">
                        <span className="text-sm text-gray-600">Actual</span>
                        <span className="text-sm font-semibold text-green-600">${forecast.actual_cost.toFixed(4)}</span>
                      </div>
                    )}
                    <div className="mt-2 bg-gray-100 rounded-full h-2">
                      <div
                        className="bg-primary-600 h-2 rounded-full"
                        style={{
                          width: `${Math.min(100, (forecast.forecasted_cost / Math.max(forecast.confidence_high, 0.01)) * 100)}%`,
                        }}
                      />
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </>
      )}
    </div>
  )
}
