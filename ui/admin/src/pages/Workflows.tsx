import { useWorkflows } from '../api/hooks'
import { CircleStackIcon, PlayIcon } from '@heroicons/react/24/outline'

export default function Workflows() {
  const { data: workflows, isLoading, error } = useWorkflows()

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
        Failed to load workflows
      </div>
    )
  }

  // Built-in templates
  const templates = [
    {
      type: 'research',
      name: 'Research Agent',
      description:
        'Multi-source research with web search, database queries, and report generation',
      nodes: [
        'parse_query',
        'search_web',
        'search_database',
        'analyze_results',
        'generate_report',
      ],
    },
    {
      type: 'coding',
      name: 'Coding Agent',
      description: 'Iterative code generation with analysis and refinement',
      nodes: [
        'understand_task',
        'read_code',
        'generate_code',
        'analyze_code',
        'finalize_code',
      ],
    },
    {
      type: 'data_analysis',
      name: 'Data Analysis Agent',
      description:
        'SQL query generation, data analysis, and visualization recommendations',
      nodes: [
        'parse_question',
        'query_data',
        'analyze_data',
        'generate_visualization',
        'summarize',
      ],
    },
  ]

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Workflows</h1>
        <p className="text-gray-600">
          Pre-built and custom workflow templates
        </p>
      </div>

      {/* Pre-built Templates */}
      <div>
        <h2 className="text-lg font-semibold mb-4">Pre-built Templates</h2>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {templates.map((template) => (
            <div key={template.type} className="card">
              <div className="flex items-center mb-4">
                <div className="p-2 bg-primary-100 rounded-lg mr-3">
                  <CircleStackIcon className="w-5 h-5 text-primary-600" />
                </div>
                <div>
                  <h3 className="font-semibold">{template.name}</h3>
                  <span className="text-xs text-gray-500 font-mono">
                    {template.type}
                  </span>
                </div>
              </div>

              <p className="text-sm text-gray-600 mb-4">
                {template.description}
              </p>

              <div className="mb-4">
                <p className="text-xs text-gray-500 mb-2">Workflow Steps:</p>
                <div className="flex flex-wrap gap-1">
                  {template.nodes.map((node, idx) => (
                    <span key={node} className="flex items-center">
                      <span className="px-2 py-1 bg-gray-100 rounded text-xs font-mono">
                        {node}
                      </span>
                      {idx < template.nodes.length - 1 && (
                        <span className="mx-1 text-gray-400">→</span>
                      )}
                    </span>
                  ))}
                </div>
              </div>

              <button className="btn btn-secondary w-full text-sm">
                <PlayIcon className="w-4 h-4 mr-2" />
                Test Workflow
              </button>
            </div>
          ))}
        </div>
      </div>

      {/* Custom Workflows */}
      <div>
        <h2 className="text-lg font-semibold mb-4">Custom Workflows</h2>

        {workflows && workflows.length > 0 ? (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {workflows.map((workflow: any) => (
              <div key={workflow.id} className="card">
                <div className="flex items-start justify-between mb-4">
                  <div>
                    <h3 className="font-semibold">{workflow.name}</h3>
                    {workflow.template_type && (
                      <span className="text-xs text-gray-500 font-mono">
                        Based on: {workflow.template_type}
                      </span>
                    )}
                  </div>
                  <span
                    className={`px-2 py-1 rounded text-xs ${
                      workflow.is_active
                        ? 'bg-green-100 text-green-700'
                        : 'bg-gray-100 text-gray-700'
                    }`}
                  >
                    {workflow.is_active ? 'Active' : 'Inactive'}
                  </span>
                </div>

                {workflow.description && (
                  <p className="text-sm text-gray-600 mb-4">
                    {workflow.description}
                  </p>
                )}

                <p className="text-xs text-gray-500">
                  Created:{' '}
                  {workflow.created_at
                    ? new Date(workflow.created_at).toLocaleDateString()
                    : 'Unknown'}
                </p>
              </div>
            ))}
          </div>
        ) : (
          <div className="card text-center py-8 text-gray-500">
            <p>No custom workflows defined yet.</p>
            <p className="text-sm mt-1">
              Use the Workflow Engine API to create custom workflows.
            </p>
          </div>
        )}
      </div>
    </div>
  )
}
