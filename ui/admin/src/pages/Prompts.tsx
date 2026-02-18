import { useState } from 'react'
import {
  usePromptTemplates,
  useCreatePromptTemplate,
  useDeletePromptTemplate,
  usePromptApprovals,
} from '../api/hooks'
import { promptsApi } from '../api/client'
import type { PromptTemplate, PromptTemplateCreate, PromptApproval } from '../types'
import { PlusIcon, TrashIcon, EyeIcon, PaperAirplaneIcon, CheckIcon, XMarkIcon } from '@heroicons/react/24/outline'
import { SkeletonCard } from '../components/Skeleton'
import { useToast } from '../components/Toast'

const statusColors: Record<string, string> = {
  draft: 'bg-gray-100 text-gray-800',
  pending_review: 'bg-yellow-100 text-yellow-800',
  approved: 'bg-green-100 text-green-800',
  deprecated: 'bg-red-100 text-red-800',
}

export default function Prompts() {
  const toast = useToast()
  const [showCreate, setShowCreate] = useState(false)
  const [showPreview, setShowPreview] = useState<PromptTemplate | null>(null)
  const [showVersions, setShowVersions] = useState<string | null>(null)
  const [showApprovals, setShowApprovals] = useState(false)
  const [filterCategory, setFilterCategory] = useState('')
  const [filterStatus, setFilterStatus] = useState('')
  const [versions, setVersions] = useState<PromptTemplate[]>([])
  const [renderResult, setRenderResult] = useState<string | null>(null)
  const [renderVars, setRenderVars] = useState<Record<string, string>>({})

  const params: Record<string, string> = {}
  if (filterCategory) params.category = filterCategory
  if (filterStatus) params.status = filterStatus

  const { data: templates, isLoading, error } = usePromptTemplates(Object.keys(params).length > 0 ? params : undefined)
  const { data: approvals } = usePromptApprovals()
  const createMutation = useCreatePromptTemplate()
  const deleteMutation = useDeletePromptTemplate()

  const [form, setForm] = useState<PromptTemplateCreate>({
    name: '',
    slug: '',
    template_text: '',
    category: '',
    description: '',
    model_hint: '',
    tags: [],
    variables: [],
  })
  const [tagInput, setTagInput] = useState('')

  const handleCreate = async () => {
    try {
      await createMutation.mutateAsync(form)
      toast('success', 'Prompt template created')
      setShowCreate(false)
      setForm({ name: '', slug: '', template_text: '', category: '', description: '', model_hint: '', tags: [], variables: [] })
      setTagInput('')
    } catch {
      toast('error', 'Failed to create prompt template')
    }
  }

  const handleDelete = async (id: string) => {
    if (!confirm('Delete this prompt template?')) return
    try {
      await deleteMutation.mutateAsync(id)
      toast('success', 'Prompt template deleted')
    } catch {
      toast('error', 'Failed to delete prompt template')
    }
  }

  const handleSubmitReview = async (id: string) => {
    try {
      await promptsApi.submitReview(id)
      toast('success', 'Submitted for review')
    } catch {
      toast('error', 'Failed to submit for review')
    }
  }

  const handleLoadVersions = async (slug: string) => {
    try {
      const v = await promptsApi.getVersions(slug)
      setVersions(v)
      setShowVersions(slug)
    } catch {
      toast('error', 'Failed to load versions')
    }
  }

  const handleRender = async (slug: string) => {
    try {
      const result = await promptsApi.render(slug, renderVars)
      setRenderResult(result.rendered)
    } catch {
      toast('error', 'Failed to render template')
    }
  }

  const handleApprove = async (id: string) => {
    try {
      await promptsApi.approve(id)
      toast('success', 'Prompt approved')
      window.location.reload()
    } catch {
      toast('error', 'Failed to approve prompt')
    }
  }

  const handleReject = async (id: string) => {
    try {
      await promptsApi.reject(id)
      toast('success', 'Prompt rejected')
      window.location.reload()
    } catch {
      toast('error', 'Failed to reject prompt')
    }
  }

  // Highlight {{variables}} in template text
  const highlightTemplate = (text: string) => {
    return text.replace(/\{\{(\w+)\}\}/g, '<span class="bg-blue-100 text-blue-800 px-1 rounded font-mono text-sm">{{$1}}</span>')
  }

  if (isLoading) {
    return (
      <div className="space-y-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Prompt Registry</h1>
          <p className="text-gray-600">Manage versioned prompt templates</p>
        </div>
        <SkeletonCard />
      </div>
    )
  }

  if (error) {
    return <div className="bg-red-50 text-red-700 p-4 rounded-lg">Failed to load prompt templates</div>
  }

  const templateList = Array.isArray(templates) ? templates : []
  const approvalList = Array.isArray(approvals) ? approvals : []

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Prompt Registry</h1>
          <p className="text-gray-600">
            {templateList.length} template{templateList.length !== 1 ? 's' : ''}
            {approvalList.length > 0 && (
              <span className="ml-2 text-yellow-600 font-medium">
                ({approvalList.length} pending approval{approvalList.length !== 1 ? 's' : ''})
              </span>
            )}
          </p>
        </div>
        <div className="flex gap-2">
          <button onClick={() => setShowApprovals(!showApprovals)} className="btn btn-secondary">
            Approvals ({approvalList.length})
          </button>
          <button onClick={() => setShowCreate(true)} className="btn btn-primary">
            <PlusIcon className="w-4 h-4 mr-1" />
            New Template
          </button>
        </div>
      </div>

      {/* Filters */}
      <div className="flex gap-4">
        <div>
          <select
            value={filterCategory}
            onChange={(e) => setFilterCategory(e.target.value)}
            className="input"
          >
            <option value="">All Categories</option>
            <option value="system">System</option>
            <option value="chat">Chat</option>
            <option value="analysis">Analysis</option>
            <option value="coding">Coding</option>
            <option value="writing">Writing</option>
          </select>
        </div>
        <div>
          <select
            value={filterStatus}
            onChange={(e) => setFilterStatus(e.target.value)}
            className="input"
          >
            <option value="">All Statuses</option>
            <option value="draft">Draft</option>
            <option value="pending_review">Pending Review</option>
            <option value="approved">Approved</option>
            <option value="deprecated">Deprecated</option>
          </select>
        </div>
      </div>

      {/* Approvals Panel */}
      {showApprovals && approvalList.length > 0 && (
        <div className="card border-yellow-200 bg-yellow-50">
          <h3 className="text-lg font-semibold mb-3">Pending Approvals</h3>
          <div className="space-y-3">
            {approvalList.map((approval: PromptApproval) => (
              <div key={approval.id} className="flex items-center justify-between bg-white p-3 rounded-lg border">
                <div>
                  <p className="text-sm font-medium">Template: {approval.template_id.substring(0, 8)}...</p>
                  <p className="text-xs text-gray-500">Version {approval.template_version} | Requested by {approval.requested_by}</p>
                  <p className="text-xs text-gray-400">{approval.requested_at ? new Date(approval.requested_at).toLocaleString() : ''}</p>
                </div>
                <div className="flex gap-2">
                  <button
                    onClick={() => handleApprove(approval.id)}
                    className="btn btn-primary text-xs px-3 py-1"
                  >
                    <CheckIcon className="w-3 h-3 mr-1" />
                    Approve
                  </button>
                  <button
                    onClick={() => handleReject(approval.id)}
                    className="btn btn-secondary text-xs px-3 py-1 text-red-600 border-red-300"
                  >
                    <XMarkIcon className="w-3 h-3 mr-1" />
                    Reject
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Create Modal */}
      {showCreate && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg p-6 w-full max-w-2xl max-h-[90vh] overflow-y-auto">
            <h2 className="text-xl font-bold mb-4">Create Prompt Template</h2>
            <div className="space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="label">Name</label>
                  <input
                    type="text"
                    value={form.name}
                    onChange={(e) => setForm({ ...form, name: e.target.value })}
                    className="input"
                    placeholder="My Prompt"
                  />
                </div>
                <div>
                  <label className="label">Slug</label>
                  <input
                    type="text"
                    value={form.slug}
                    onChange={(e) => setForm({ ...form, slug: e.target.value })}
                    className="input"
                    placeholder="my-prompt"
                  />
                </div>
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="label">Category</label>
                  <select
                    value={form.category || ''}
                    onChange={(e) => setForm({ ...form, category: e.target.value || undefined })}
                    className="input"
                  >
                    <option value="">Select category</option>
                    <option value="system">System</option>
                    <option value="chat">Chat</option>
                    <option value="analysis">Analysis</option>
                    <option value="coding">Coding</option>
                    <option value="writing">Writing</option>
                  </select>
                </div>
                <div>
                  <label className="label">Model Hint</label>
                  <input
                    type="text"
                    value={form.model_hint || ''}
                    onChange={(e) => setForm({ ...form, model_hint: e.target.value || undefined })}
                    className="input"
                    placeholder="gpt-4o"
                  />
                </div>
              </div>
              <div>
                <label className="label">Description</label>
                <input
                  type="text"
                  value={form.description || ''}
                  onChange={(e) => setForm({ ...form, description: e.target.value || undefined })}
                  className="input"
                  placeholder="What does this prompt do?"
                />
              </div>
              <div>
                <label className="label">Template Text</label>
                <textarea
                  value={form.template_text}
                  onChange={(e) => setForm({ ...form, template_text: e.target.value })}
                  className="input font-mono"
                  rows={6}
                  placeholder="You are a helpful assistant. The user's name is {{name}} and they want help with {{topic}}."
                />
                <p className="text-xs text-gray-500 mt-1">Use {"{{variable}}"} syntax for template variables</p>
              </div>
              <div>
                <label className="label">Tags</label>
                <div className="flex gap-2">
                  <input
                    type="text"
                    value={tagInput}
                    onChange={(e) => setTagInput(e.target.value)}
                    className="input flex-1"
                    placeholder="Add a tag"
                    onKeyDown={(e) => {
                      if (e.key === 'Enter' && tagInput.trim()) {
                        e.preventDefault()
                        setForm({ ...form, tags: [...(form.tags || []), tagInput.trim()] })
                        setTagInput('')
                      }
                    }}
                  />
                  <button
                    onClick={() => {
                      if (tagInput.trim()) {
                        setForm({ ...form, tags: [...(form.tags || []), tagInput.trim()] })
                        setTagInput('')
                      }
                    }}
                    className="btn btn-secondary"
                  >
                    Add
                  </button>
                </div>
                {form.tags && form.tags.length > 0 && (
                  <div className="flex flex-wrap gap-1 mt-2">
                    {form.tags.map((tag, i) => (
                      <span key={i} className="bg-blue-100 text-blue-800 text-xs px-2 py-1 rounded-full flex items-center gap-1">
                        {tag}
                        <button
                          onClick={() => setForm({ ...form, tags: form.tags?.filter((_, idx) => idx !== i) })}
                          className="hover:text-blue-600"
                        >
                          <XMarkIcon className="w-3 h-3" />
                        </button>
                      </span>
                    ))}
                  </div>
                )}
              </div>
              <div className="flex justify-end gap-2">
                <button onClick={() => setShowCreate(false)} className="btn btn-secondary">Cancel</button>
                <button
                  onClick={handleCreate}
                  className="btn btn-primary"
                  disabled={!form.name || !form.slug || !form.template_text}
                >
                  Create
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Preview Modal */}
      {showPreview && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg p-6 w-full max-w-2xl max-h-[90vh] overflow-y-auto">
            <h2 className="text-xl font-bold mb-4">Preview: {showPreview.name}</h2>
            <div className="space-y-4">
              <div className="grid grid-cols-2 gap-4 text-sm">
                <div><span className="font-medium">Slug:</span> {showPreview.slug}</div>
                <div><span className="font-medium">Version:</span> {showPreview.version}</div>
                <div><span className="font-medium">Category:</span> {showPreview.category || '--'}</div>
                <div><span className="font-medium">Status:</span>
                  <span className={`ml-1 px-2 py-0.5 text-xs rounded-full ${statusColors[showPreview.status] || 'bg-gray-100 text-gray-800'}`}>
                    {showPreview.status}
                  </span>
                </div>
              </div>
              <div>
                <label className="label">Template</label>
                <div
                  className="bg-gray-50 p-4 rounded-lg border font-mono text-sm whitespace-pre-wrap"
                  dangerouslySetInnerHTML={{ __html: highlightTemplate(showPreview.template_text) }}
                />
              </div>

              {/* Render Section */}
              {showPreview.variables && showPreview.variables.length > 0 && (
                <div>
                  <label className="label">Render with Variables</label>
                  <div className="space-y-2">
                    {showPreview.variables.map((v) => (
                      <div key={v.name} className="flex gap-2 items-center">
                        <span className="text-sm font-mono w-32">{v.name}:</span>
                        <input
                          type="text"
                          value={renderVars[v.name] || ''}
                          onChange={(e) => setRenderVars({ ...renderVars, [v.name]: e.target.value })}
                          className="input flex-1"
                          placeholder={v.default || `Enter ${v.name}`}
                        />
                      </div>
                    ))}
                  </div>
                  <button
                    onClick={() => handleRender(showPreview.slug)}
                    className="btn btn-primary mt-2"
                  >
                    Render
                  </button>
                  {renderResult && (
                    <div className="bg-green-50 p-4 rounded-lg border border-green-200 mt-2">
                      <label className="label text-green-800">Rendered Output</label>
                      <pre className="text-sm whitespace-pre-wrap">{renderResult}</pre>
                    </div>
                  )}
                </div>
              )}

              {showPreview.tags.length > 0 && (
                <div className="flex flex-wrap gap-1">
                  {showPreview.tags.map((tag, i) => (
                    <span key={i} className="bg-blue-100 text-blue-800 text-xs px-2 py-1 rounded-full">{tag}</span>
                  ))}
                </div>
              )}
              <div className="flex justify-end">
                <button
                  onClick={() => {
                    setShowPreview(null)
                    setRenderResult(null)
                    setRenderVars({})
                  }}
                  className="btn btn-secondary"
                >
                  Close
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Versions Modal */}
      {showVersions && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg p-6 w-full max-w-2xl max-h-[90vh] overflow-y-auto">
            <h2 className="text-xl font-bold mb-4">Version History: {showVersions}</h2>
            <div className="space-y-3">
              {versions.map((v) => (
                <div key={v.id} className={`p-3 rounded-lg border ${v.is_current ? 'border-blue-300 bg-blue-50' : ''}`}>
                  <div className="flex justify-between items-center">
                    <div>
                      <span className="font-medium">Version {v.version}</span>
                      {v.is_current && <span className="ml-2 text-xs bg-blue-200 text-blue-800 px-2 py-0.5 rounded-full">Current</span>}
                      <span className={`ml-2 px-2 py-0.5 text-xs rounded-full ${statusColors[v.status] || 'bg-gray-100 text-gray-800'}`}>
                        {v.status}
                      </span>
                    </div>
                    <span className="text-xs text-gray-500">
                      {v.created_at ? new Date(v.created_at).toLocaleString() : ''}
                    </span>
                  </div>
                  <pre className="text-xs mt-2 bg-gray-50 p-2 rounded overflow-x-auto">
                    {v.template_text.substring(0, 200)}{v.template_text.length > 200 ? '...' : ''}
                  </pre>
                </div>
              ))}
            </div>
            <div className="flex justify-end mt-4">
              <button onClick={() => setShowVersions(null)} className="btn btn-secondary">Close</button>
            </div>
          </div>
        </div>
      )}

      {/* Templates Table */}
      {templateList.length === 0 ? (
        <div className="card text-center text-gray-500 py-12">
          <p className="text-lg font-medium">No prompt templates found</p>
          <p className="text-sm mt-1">Create your first prompt template to get started.</p>
        </div>
      ) : (
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Name</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Slug</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Category</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Status</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Version</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Tags</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Actions</th>
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-200">
              {templateList.map((t) => (
                <tr key={t.id} className="hover:bg-gray-50">
                  <td className="px-6 py-4 whitespace-nowrap">
                    <div className="text-sm font-medium text-gray-900">{t.name}</div>
                    {t.description && <div className="text-xs text-gray-500 truncate max-w-xs">{t.description}</div>}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap">
                    <code className="text-sm text-gray-600 bg-gray-100 px-2 py-0.5 rounded">{t.slug}</code>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-600">{t.category || '--'}</td>
                  <td className="px-6 py-4 whitespace-nowrap">
                    <span className={`px-2 py-1 text-xs font-medium rounded-full ${statusColors[t.status] || 'bg-gray-100 text-gray-800'}`}>
                      {t.status}
                    </span>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap">
                    <button
                      onClick={() => handleLoadVersions(t.slug)}
                      className="text-sm text-blue-600 hover:underline"
                    >
                      v{t.version}
                    </button>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap">
                    <div className="flex flex-wrap gap-1">
                      {t.tags.slice(0, 3).map((tag, i) => (
                        <span key={i} className="bg-blue-100 text-blue-800 text-xs px-2 py-0.5 rounded-full">{tag}</span>
                      ))}
                      {t.tags.length > 3 && <span className="text-xs text-gray-500">+{t.tags.length - 3}</span>}
                    </div>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap">
                    <div className="flex gap-1">
                      <button
                        onClick={() => setShowPreview(t)}
                        className="p-1 text-gray-500 hover:text-blue-600"
                        title="Preview"
                      >
                        <EyeIcon className="w-4 h-4" />
                      </button>
                      {t.status === 'draft' && (
                        <button
                          onClick={() => handleSubmitReview(t.id)}
                          className="p-1 text-gray-500 hover:text-yellow-600"
                          title="Submit for review"
                        >
                          <PaperAirplaneIcon className="w-4 h-4" />
                        </button>
                      )}
                      <button
                        onClick={() => handleDelete(t.id)}
                        className="p-1 text-gray-500 hover:text-red-600"
                        title="Delete"
                      >
                        <TrashIcon className="w-4 h-4" />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
