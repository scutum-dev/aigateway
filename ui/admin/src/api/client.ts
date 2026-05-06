import axios from 'axios'
import type {
  GuardrailAssignment,
  MCPServerConfig,
  MCPServerCreate,
  MCPServerUpdate,
  MCPTestResult,
  GatewaySyncResult,
  GatewayConfigPreview,
  A2AAgentConfig,
  A2AAgentCreate,
  A2AAgentUpdate,
  A2ATestResult,
  WorkflowSummary,
  WorkflowCreate,
  WorkflowExecuteRequest,
  WorkflowExecutionSummary,
  WorkflowExecutionDetail,
  PlatformSettings,
  LoginResponse,
  UserInfo,
  GuardrailConfig,
  GuardrailConfigCreate,
  GuardrailConfigUpdate,
  GuardrailEvent,
  ReportsSummary,
  ModelInfo,
  ModelCreateRequest,
  KeyInfo,
  KeyGenerateRequest,
  KeyGenerateResponse,
  TeamInfo,
  TeamCreateRequest,
  TeamUpdateRequest,
  BudgetInfo,
  BudgetCreateRequest,
  BudgetUpdateRequest,
  Organization,
  OrganizationCreate,
  OrganizationUpdate,
  BusinessUnit,
  BusinessUnitCreate,
  TeamHierarchy,
  OrgMembership,
  AuditLogEntry,
  ContentDetector,
  ContentDetectorCreate,
  TeamContentPolicy,
  SSOConfig,
  PromptTemplate,
  PromptTemplateCreate,
  PromptApproval,
  RateLimitPolicy,
  RateLimitPolicyCreate,
  RateLimitEvent,
  ModelAccessTier,
  ModelAccessTierCreate,
  ModelAccessRequest,
  ModelAccessRequestCreate,
  CostAllocationRule,
  CostAllocationRuleCreate,
  ChargebackReport,
  BudgetForecast,
  SLADefinition,
  SLADefinitionCreate,
  ProviderHealthMetric,
  SLAViolation,
  FailoverRule,
  FailoverRuleCreate,
  ABTest,
  ABTestCreate,
  ABTestSnapshot,
  CacheStats,
  CacheEntry,
  CacheSettings,
  EventSubscription,
  EventSubscriptionCreate,
  EventLogEntry,
  PlaygroundSession,
  PlaygroundSessionCreate,
  ModelDeprecation,
  ModelDeprecationCreate,
  RoutingPolicy,
  RoutingPolicyCreate,
  LiteLLMRouterStatus,
  SREIncidentSummary,
  SREIncidentDetail,
  SREStats,
  SRETriggerRequest,
  Lead,
  LeadStatus,
  LeadUpdate,
} from '../types'

// Use Vite's BASE_URL so API calls route through the admin-ui nginx proxy
// Production: BASE_URL=/admin/ → baseURL=/admin/api/v1 (hits admin-ui ingress)
// Dev: BASE_URL=/ → baseURL=/api/v1 (hits vite proxy)
const basePath = import.meta.env.BASE_URL.replace(/\/+$/, '')

const api = axios.create({
  baseURL: `${basePath}/api/v1`,
  headers: {
    'Content-Type': 'application/json',
  },
})

// Add auth token to requests
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('admin_token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// Handle 401 errors
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('admin_token')
      localStorage.removeItem('token_expires_at')
      window.location.href = basePath || '/'
    }
    return Promise.reject(error)
  }
)

export default api

// Auth API
export const authApi = {
  login: async (apiKey: string): Promise<LoginResponse> => {
    const response = await axios.post(`${basePath}/auth/login`, { api_key: apiKey })
    return response.data
  },
  // One-shot magic-link exchange used by hosted trial machines. The
  // trial-provisioner injects BOOTSTRAP_TOKEN as an env var on the trial Fly
  // machine; /try redirects the user to /admin/?bootstrap=<token>; Login.tsx
  // detects the param on mount and calls this to skip the credential form.
  bootstrap: async (token: string): Promise<LoginResponse> => {
    const response = await axios.post(`${basePath}/auth/bootstrap`, { token })
    return response.data
  },
  me: async (): Promise<UserInfo> => {
    const response = await api.get('/auth/me')
    return response.data
  },
}

// MCP Servers API
export const mcpServersApi = {
  list: async (): Promise<MCPServerConfig[]> => {
    const response = await api.get('/mcp-servers')
    return response.data
  },
  create: async (data: MCPServerCreate): Promise<MCPServerConfig> => {
    const response = await api.post('/mcp-servers', data)
    return response.data
  },
  update: async (id: string, data: MCPServerUpdate): Promise<MCPServerConfig> => {
    const response = await api.put(`/mcp-servers/${id}`, data)
    return response.data
  },
  delete: async (id: string): Promise<void> => {
    await api.delete(`/mcp-servers/${id}`)
  },
  test: async (id: string): Promise<MCPTestResult> => {
    const response = await api.post(`/mcp-servers/${id}/test`)
    return response.data
  },
  sync: async (): Promise<GatewaySyncResult> => {
    const response = await api.post('/mcp-servers/sync')
    return response.data
  },
  previewConfig: async (): Promise<GatewayConfigPreview> => {
    const response = await api.get('/mcp-servers/sync/preview')
    return response.data
  },
}

// A2A Agents API
export const agentsApi = {
  list: async (): Promise<A2AAgentConfig[]> => {
    const response = await api.get('/agents')
    return response.data
  },
  create: async (data: A2AAgentCreate): Promise<A2AAgentConfig> => {
    const response = await api.post('/agents', data)
    return response.data
  },
  get: async (id: string): Promise<A2AAgentConfig> => {
    const response = await api.get(`/agents/${id}`)
    return response.data
  },
  update: async (id: string, data: A2AAgentUpdate): Promise<A2AAgentConfig> => {
    const response = await api.put(`/agents/${id}`, data)
    return response.data
  },
  delete: async (id: string): Promise<void> => {
    await api.delete(`/agents/${id}`)
  },
  test: async (id: string): Promise<A2ATestResult> => {
    const response = await api.post(`/agents/${id}/test`)
    return response.data
  },
}

// Workflows API
export const workflowsApi = {
  list: async (): Promise<WorkflowSummary[]> => {
    const response = await api.get('/workflows')
    return response.data
  },
  create: async (data: WorkflowCreate): Promise<WorkflowSummary> => {
    const response = await api.post('/workflows', data)
    return response.data
  },
  listTemplates: async (): Promise<unknown> => {
    const response = await api.get('/workflow-templates')
    return response.data
  },
  execute: async (data: WorkflowExecuteRequest): Promise<unknown> => {
    const response = await api.post('/workflow-executions', data)
    return response.data
  },
  listExecutions: async (): Promise<WorkflowExecutionSummary[]> => {
    const response = await api.get('/workflow-executions')
    return response.data
  },
  getExecution: async (id: string): Promise<WorkflowExecutionDetail> => {
    const response = await api.get(`/workflow-executions/${id}`)
    return response.data
  },
}

// Reports API
export const reportsApi = {
  summary: async (): Promise<ReportsSummary> => {
    const response = await api.get('/reports/summary')
    return response.data
  },
}

// Guardrails API
export const guardrailsApi = {
  list: async (): Promise<GuardrailConfig[]> => {
    const response = await api.get('/guardrails')
    return response.data
  },
  create: async (data: GuardrailConfigCreate): Promise<GuardrailConfig> => {
    const response = await api.post('/guardrails', data)
    return response.data
  },
  get: async (id: string): Promise<GuardrailConfig> => {
    const response = await api.get(`/guardrails/${id}`)
    return response.data
  },
  update: async (id: string, data: GuardrailConfigUpdate): Promise<GuardrailConfig> => {
    const response = await api.put(`/guardrails/${id}`, data)
    return response.data
  },
  delete: async (id: string): Promise<void> => {
    await api.delete(`/guardrails/${id}`)
  },
  assignToTeam: async (configId: string, teamId: string, priority?: number): Promise<void> => {
    await api.post(`/guardrails/${configId}/assign/${teamId}`, null, {
      params: priority !== undefined ? { priority } : undefined,
    })
  },
  unassignFromTeam: async (configId: string, teamId: string): Promise<void> => {
    await api.delete(`/guardrails/${configId}/assign/${teamId}`)
  },
  assignments: async (): Promise<GuardrailAssignment[]> => {
    const response = await api.get('/guardrail-assignments')
    return response.data
  },
  events: async (params?: { team_id?: string; event_type?: string; limit?: number; offset?: number }): Promise<GuardrailEvent[]> => {
    const response = await api.get('/guardrail-events', { params })
    return response.data
  },
}

// Settings API
export const settingsApi = {
  get: async (): Promise<PlatformSettings> => {
    const response = await api.get('/settings')
    return response.data
  },
  update: async (data: PlatformSettings): Promise<PlatformSettings> => {
    const response = await api.put('/settings', data)
    return response.data
  },
}

// Models API
export const modelsApi = {
  list: async (): Promise<{ data: ModelInfo[] }> => {
    const response = await api.get('/models')
    return response.data
  },
  get: async (modelId: string): Promise<ModelInfo> => {
    const response = await api.get(`/models/${modelId}`)
    return response.data
  },
  create: async (data: ModelCreateRequest): Promise<unknown> => {
    const response = await api.post('/models', data)
    return response.data
  },
  delete: async (id: string): Promise<void> => {
    await api.post('/models/delete', { id })
  },
}

// API Keys API
export const keysApi = {
  list: async (): Promise<KeyInfo[]> => {
    const response = await api.get('/keys')
    return response.data
  },
  get: async (key: string): Promise<unknown> => {
    const response = await api.get(`/keys/${key}`)
    return response.data
  },
  generate: async (data: KeyGenerateRequest): Promise<KeyGenerateResponse> => {
    const response = await api.post('/keys/generate', data)
    return response.data
  },
  update: async (data: { key: string } & Partial<KeyGenerateRequest>): Promise<unknown> => {
    const response = await api.post('/keys/update', data)
    return response.data
  },
  delete: async (keys: string[]): Promise<void> => {
    await api.post('/keys/delete', { keys })
  },
}

// Teams API
export const teamsApi = {
  list: async (): Promise<TeamInfo[]> => {
    const response = await api.get('/teams')
    return response.data
  },
  get: async (teamId: string): Promise<TeamInfo> => {
    const response = await api.get(`/teams/${teamId}`)
    return response.data
  },
  create: async (data: TeamCreateRequest): Promise<TeamInfo> => {
    const response = await api.post('/teams', data)
    return response.data
  },
  update: async (data: TeamUpdateRequest): Promise<TeamInfo> => {
    const response = await api.post('/teams/update', data)
    return response.data
  },
  delete: async (teamIds: string[]): Promise<void> => {
    await api.post('/teams/delete', { team_ids: teamIds })
  },
  addMember: async (teamId: string, member: { role: string; user_id: string }): Promise<unknown> => {
    const response = await api.post(`/teams/${teamId}/members`, { member })
    return response.data
  },
  deleteMember: async (teamId: string, userId: string): Promise<void> => {
    await api.post(`/teams/${teamId}/members/delete`, { user_id: userId })
  },
}

// Budgets API
export const budgetsApi = {
  list: async (): Promise<BudgetInfo[]> => {
    const response = await api.get('/budgets')
    return response.data
  },
  get: async (budgetId: string): Promise<BudgetInfo> => {
    const response = await api.get(`/budgets/${budgetId}`)
    return response.data
  },
  create: async (data: BudgetCreateRequest): Promise<BudgetInfo> => {
    const response = await api.post('/budgets', data)
    return response.data
  },
  update: async (data: BudgetUpdateRequest): Promise<BudgetInfo> => {
    const response = await api.post('/budgets/update', data)
    return response.data
  },
  delete: async (id: string): Promise<void> => {
    await api.post('/budgets/delete', { id })
  },
}

// Organizations API
export const organizationsApi = {
  list: async (): Promise<Organization[]> => {
    const response = await api.get('/organizations')
    return response.data
  },
  get: async (id: string): Promise<Organization> => {
    const response = await api.get(`/organizations/${id}`)
    return response.data
  },
  create: async (data: OrganizationCreate): Promise<Organization> => {
    const response = await api.post('/organizations', data)
    return response.data
  },
  update: async (id: string, data: OrganizationUpdate): Promise<Organization> => {
    const response = await api.put(`/organizations/${id}`, data)
    return response.data
  },
  delete: async (id: string): Promise<void> => {
    await api.delete(`/organizations/${id}`)
  },
  listBUs: async (orgId: string): Promise<BusinessUnit[]> => {
    const response = await api.get(`/organizations/${orgId}/business-units`)
    return response.data
  },
  createBU: async (orgId: string, data: BusinessUnitCreate): Promise<BusinessUnit> => {
    const response = await api.post(`/organizations/${orgId}/business-units`, data)
    return response.data
  },
  updateBU: async (orgId: string, buId: string, data: Partial<BusinessUnitCreate>): Promise<BusinessUnit> => {
    const response = await api.put(`/organizations/${orgId}/business-units/${buId}`, data)
    return response.data
  },
  deleteBU: async (orgId: string, buId: string): Promise<void> => {
    await api.delete(`/organizations/${orgId}/business-units/${buId}`)
  },
  listTeams: async (orgId: string): Promise<TeamHierarchy[]> => {
    const response = await api.get(`/organizations/${orgId}/teams`)
    return response.data
  },
  assignTeam: async (orgId: string, teamId: string, buId?: string): Promise<void> => {
    await api.post(`/organizations/${orgId}/teams/${teamId}`, { bu_id: buId })
  },
  removeTeam: async (orgId: string, teamId: string): Promise<void> => {
    await api.delete(`/organizations/${orgId}/teams/${teamId}`)
  },
  listMembers: async (orgId: string): Promise<OrgMembership[]> => {
    const response = await api.get(`/organizations/${orgId}/members`)
    return response.data
  },
  addMember: async (orgId: string, data: { user_id: string; role: string; bu_id?: string }): Promise<OrgMembership> => {
    const response = await api.post(`/organizations/${orgId}/members`, data)
    return response.data
  },
  updateMember: async (orgId: string, userId: string, data: { role: string }): Promise<void> => {
    await api.put(`/organizations/${orgId}/members/${userId}`, data)
  },
  removeMember: async (orgId: string, userId: string): Promise<void> => {
    await api.delete(`/organizations/${orgId}/members/${userId}`)
  },
  getSSO: async (orgId: string): Promise<SSOConfig> => {
    const response = await api.get(`/organizations/${orgId}/sso`)
    return response.data
  },
  updateSSO: async (orgId: string, data: Record<string, unknown>): Promise<SSOConfig> => {
    const response = await api.post(`/organizations/${orgId}/sso`, data)
    return response.data
  },
  deleteSSO: async (orgId: string): Promise<void> => {
    await api.delete(`/organizations/${orgId}/sso`)
  },
}

// Audit API
export const auditApi = {
  list: async (params?: { actor_id?: string; resource_type?: string; action?: string; org_id?: string; limit?: number; offset?: number }): Promise<AuditLogEntry[]> => {
    const response = await api.get('/audit-logs', { params })
    return response.data
  },
  export: async (format: string = 'csv'): Promise<Blob> => {
    const response = await api.get('/audit-logs/export', { params: { format }, responseType: 'blob' })
    return response.data
  },
}

// DLP API
export const dlpApi = {
  listDetectors: async (): Promise<ContentDetector[]> => {
    const response = await api.get('/detectors')
    return response.data
  },
  createDetector: async (data: ContentDetectorCreate): Promise<ContentDetector> => {
    const response = await api.post('/detectors', data)
    return response.data
  },
  getDetector: async (id: string): Promise<ContentDetector> => {
    const response = await api.get(`/detectors/${id}`)
    return response.data
  },
  updateDetector: async (id: string, data: Partial<ContentDetectorCreate>): Promise<ContentDetector> => {
    const response = await api.put(`/detectors/${id}`, data)
    return response.data
  },
  deleteDetector: async (id: string): Promise<void> => {
    await api.delete(`/detectors/${id}`)
  },
  testDetector: async (id: string, text: string): Promise<{ matches: unknown[] }> => {
    const response = await api.post(`/detectors/${id}/test`, { text })
    return response.data
  },
  attachDetector: async (guardrailId: string, detectorId: string): Promise<void> => {
    await api.post(`/guardrails/${guardrailId}/detectors/${detectorId}`)
  },
  detachDetector: async (guardrailId: string, detectorId: string): Promise<void> => {
    await api.delete(`/guardrails/${guardrailId}/detectors/${detectorId}`)
  },
  getContentPolicies: async (teamId: string): Promise<TeamContentPolicy[]> => {
    const response = await api.get(`/teams/${teamId}/content-policies`)
    return response.data
  },
  updateContentPolicy: async (teamId: string, data: { policy_type: string; config: Record<string, unknown> }): Promise<TeamContentPolicy> => {
    const response = await api.put(`/teams/${teamId}/content-policies`, data)
    return response.data
  },
}

// Prompts API
export const promptsApi = {
  list: async (params?: { category?: string; status?: string }): Promise<PromptTemplate[]> => {
    const response = await api.get('/prompts', { params })
    return response.data
  },
  get: async (slug: string): Promise<PromptTemplate> => {
    const response = await api.get(`/prompts/${slug}`)
    return response.data
  },
  create: async (data: PromptTemplateCreate): Promise<PromptTemplate> => {
    const response = await api.post('/prompts', data)
    return response.data
  },
  update: async (id: string, data: Partial<PromptTemplateCreate>): Promise<PromptTemplate> => {
    const response = await api.put(`/prompts/${id}`, data)
    return response.data
  },
  delete: async (id: string): Promise<void> => {
    await api.delete(`/prompts/${id}`)
  },
  getVersions: async (slug: string): Promise<PromptTemplate[]> => {
    const response = await api.get(`/prompts/${slug}/versions`)
    return response.data
  },
  createVersion: async (slug: string, data: { template_text: string; variables?: unknown[] }): Promise<PromptTemplate> => {
    const response = await api.post(`/prompts/${slug}/versions`, data)
    return response.data
  },
  render: async (slug: string, variables: Record<string, string>): Promise<{ rendered: string }> => {
    const response = await api.post(`/prompts/${slug}/render`, { variables })
    return response.data
  },
  submitReview: async (id: string): Promise<PromptApproval> => {
    const response = await api.post(`/prompts/${id}/submit-review`)
    return response.data
  },
  listApprovals: async (): Promise<PromptApproval[]> => {
    const response = await api.get('/prompt-approvals')
    return response.data
  },
  approve: async (id: string, comment?: string): Promise<void> => {
    await api.post(`/prompt-approvals/${id}/approve`, { comment })
  },
  reject: async (id: string, comment?: string): Promise<void> => {
    await api.post(`/prompt-approvals/${id}/reject`, { comment })
  },
  analytics: async (slug: string): Promise<unknown> => {
    const response = await api.get(`/prompts/${slug}/analytics`)
    return response.data
  },
}

// Rate Limits API
export const rateLimitsApi = {
  list: async (): Promise<RateLimitPolicy[]> => {
    const response = await api.get('/rate-limits')
    return response.data
  },
  create: async (data: RateLimitPolicyCreate): Promise<RateLimitPolicy> => {
    const response = await api.post('/rate-limits', data)
    return response.data
  },
  get: async (id: string): Promise<RateLimitPolicy> => {
    const response = await api.get(`/rate-limits/${id}`)
    return response.data
  },
  update: async (id: string, data: Partial<RateLimitPolicyCreate>): Promise<RateLimitPolicy> => {
    const response = await api.put(`/rate-limits/${id}`, data)
    return response.data
  },
  delete: async (id: string): Promise<void> => {
    await api.delete(`/rate-limits/${id}`)
  },
  status: async (): Promise<unknown> => {
    const response = await api.get('/rate-limits/status')
    return response.data
  },
  events: async (params?: { limit?: number }): Promise<RateLimitEvent[]> => {
    const response = await api.get('/rate-limit-events', { params })
    return response.data
  },
}

// Model Access API
export const modelAccessApi = {
  listTiers: async (): Promise<ModelAccessTier[]> => {
    const response = await api.get('/model-access/tiers')
    return response.data
  },
  createTier: async (data: ModelAccessTierCreate): Promise<ModelAccessTier> => {
    const response = await api.post('/model-access/tiers', data)
    return response.data
  },
  updateTier: async (id: string, data: Partial<ModelAccessTierCreate>): Promise<ModelAccessTier> => {
    const response = await api.put(`/model-access/tiers/${id}`, data)
    return response.data
  },
  deleteTier: async (id: string): Promise<void> => {
    await api.delete(`/model-access/tiers/${id}`)
  },
  listRequests: async (params?: { status?: string }): Promise<ModelAccessRequest[]> => {
    const response = await api.get('/model-access/requests', { params })
    return response.data
  },
  createRequest: async (data: ModelAccessRequestCreate): Promise<ModelAccessRequest> => {
    const response = await api.post('/model-access/requests', data)
    return response.data
  },
  approveRequest: async (id: string, comment?: string): Promise<void> => {
    await api.post(`/model-access/requests/${id}/approve`, { comment })
  },
  rejectRequest: async (id: string, comment?: string): Promise<void> => {
    await api.post(`/model-access/requests/${id}/reject`, { comment })
  },
  myAccess: async (): Promise<ModelAccessRequest[]> => {
    const response = await api.get('/model-access/my-access')
    return response.data
  },
}

// Chargeback API
export const chargebackApi = {
  listRules: async (): Promise<CostAllocationRule[]> => {
    const response = await api.get('/cost-allocation/rules')
    return response.data
  },
  createRule: async (data: CostAllocationRuleCreate): Promise<CostAllocationRule> => {
    const response = await api.post('/cost-allocation/rules', data)
    return response.data
  },
  updateRule: async (id: string, data: Partial<CostAllocationRuleCreate>): Promise<CostAllocationRule> => {
    const response = await api.put(`/cost-allocation/rules/${id}`, data)
    return response.data
  },
  deleteRule: async (id: string): Promise<void> => {
    await api.delete(`/cost-allocation/rules/${id}`)
  },
  generateReport: async (period: string): Promise<ChargebackReport> => {
    const response = await api.post('/chargeback/reports/generate', { period })
    return response.data
  },
  listReports: async (): Promise<ChargebackReport[]> => {
    const response = await api.get('/chargeback/reports')
    return response.data
  },
  getReport: async (id: string): Promise<ChargebackReport> => {
    const response = await api.get(`/chargeback/reports/${id}`)
    return response.data
  },
  exportReport: async (id: string, format: string = 'csv'): Promise<Blob> => {
    const response = await api.get(`/chargeback/reports/${id}/export`, { params: { format }, responseType: 'blob' })
    return response.data
  },
  finalizeReport: async (id: string): Promise<void> => {
    await api.post(`/chargeback/reports/${id}/finalize`)
  },
  getForecasts: async (): Promise<BudgetForecast[]> => {
    const response = await api.get('/reports/forecast')
    return response.data
  },
  generateForecast: async (params?: { team_id?: string }): Promise<BudgetForecast[]> => {
    const response = await api.post('/reports/forecast/generate', params)
    return response.data
  },
}

// SLA API
export const slaApi = {
  listDefinitions: async (): Promise<SLADefinition[]> => {
    const response = await api.get('/sla/definitions')
    return response.data
  },
  createDefinition: async (data: SLADefinitionCreate): Promise<SLADefinition> => {
    const response = await api.post('/sla/definitions', data)
    return response.data
  },
  updateDefinition: async (id: string, data: Partial<SLADefinitionCreate>): Promise<SLADefinition> => {
    const response = await api.put(`/sla/definitions/${id}`, data)
    return response.data
  },
  deleteDefinition: async (id: string): Promise<void> => {
    await api.delete(`/sla/definitions/${id}`)
  },
  getHealth: async (): Promise<ProviderHealthMetric[]> => {
    const response = await api.get('/sla/health')
    return response.data
  },
  getHealthHistory: async (params?: { provider?: string; model?: string; hours?: number }): Promise<ProviderHealthMetric[]> => {
    const response = await api.get('/sla/health/history', { params })
    return response.data
  },
  listViolations: async (params?: { resolved?: boolean }): Promise<SLAViolation[]> => {
    const response = await api.get('/sla/violations', { params })
    return response.data
  },
  activeViolations: async (): Promise<SLAViolation[]> => {
    const response = await api.get('/sla/violations/active')
    return response.data
  },
  resolveViolation: async (id: string): Promise<void> => {
    await api.post(`/sla/violations/${id}/resolve`)
  },
  listFailoverRules: async (): Promise<FailoverRule[]> => {
    const response = await api.get('/sla/failover-rules')
    return response.data
  },
  createFailoverRule: async (data: FailoverRuleCreate): Promise<FailoverRule> => {
    const response = await api.post('/sla/failover-rules', data)
    return response.data
  },
  updateFailoverRule: async (id: string, data: Partial<FailoverRuleCreate>): Promise<FailoverRule> => {
    const response = await api.put(`/sla/failover-rules/${id}`, data)
    return response.data
  },
  deleteFailoverRule: async (id: string): Promise<void> => {
    await api.delete(`/sla/failover-rules/${id}`)
  },
  triggerFailover: async (id: string): Promise<void> => {
    await api.post(`/sla/failover-rules/${id}/trigger`)
  },
  getCompliance: async (): Promise<unknown> => {
    const response = await api.get('/sla/compliance')
    return response.data
  },
}

// A/B Tests API
export const abTestsApi = {
  list: async (): Promise<ABTest[]> => {
    const response = await api.get('/ab-tests')
    return response.data
  },
  get: async (id: string): Promise<ABTest & { latest_snapshot?: ABTestSnapshot }> => {
    const response = await api.get(`/ab-tests/${id}`)
    return response.data
  },
  create: async (data: ABTestCreate): Promise<ABTest> => {
    const response = await api.post('/ab-tests', data)
    return response.data
  },
  update: async (id: string, data: Partial<ABTestCreate>): Promise<ABTest> => {
    const response = await api.put(`/ab-tests/${id}`, data)
    return response.data
  },
  delete: async (id: string): Promise<void> => {
    await api.delete(`/ab-tests/${id}`)
  },
  start: async (id: string): Promise<void> => {
    await api.post(`/ab-tests/${id}/start`)
  },
  stop: async (id: string): Promise<void> => {
    await api.post(`/ab-tests/${id}/stop`)
  },
  promote: async (id: string): Promise<void> => {
    await api.post(`/ab-tests/${id}/promote`)
  },
  snapshots: async (id: string): Promise<ABTestSnapshot[]> => {
    const response = await api.get(`/ab-tests/${id}/snapshots`)
    return response.data
  },
}

// Cache API
export const cacheApi = {
  stats: async (): Promise<CacheStats> => {
    const response = await api.get('/cache/stats')
    return response.data
  },
  clear: async (): Promise<void> => {
    await api.post('/cache/clear')
  },
  settings: async (data: CacheSettings): Promise<CacheSettings> => {
    const response = await api.put('/cache/settings', data)
    return response.data
  },
  entries: async (params?: { limit?: number; offset?: number }): Promise<CacheEntry[]> => {
    const response = await api.get('/cache/entries', { params })
    return response.data
  },
  deleteEntry: async (id: string): Promise<void> => {
    await api.delete(`/cache/entries/${id}`)
  },
}

// Events API
export const eventsApi = {
  listSubscriptions: async (): Promise<EventSubscription[]> => {
    const response = await api.get('/events/subscriptions')
    return response.data
  },
  createSubscription: async (data: EventSubscriptionCreate): Promise<EventSubscription> => {
    const response = await api.post('/events/subscriptions', data)
    return response.data
  },
  getSubscription: async (id: string): Promise<EventSubscription> => {
    const response = await api.get(`/events/subscriptions/${id}`)
    return response.data
  },
  updateSubscription: async (id: string, data: Partial<EventSubscriptionCreate>): Promise<EventSubscription> => {
    const response = await api.put(`/events/subscriptions/${id}`, data)
    return response.data
  },
  deleteSubscription: async (id: string): Promise<void> => {
    await api.delete(`/events/subscriptions/${id}`)
  },
  listEvents: async (params?: { event_type?: string; limit?: number; offset?: number }): Promise<EventLogEntry[]> => {
    const response = await api.get('/events/log', { params })
    return response.data
  },
  sendTestEvent: async (data: { event_type: string; payload: Record<string, unknown> }): Promise<void> => {
    await api.post('/events/test', data)
  },
}

// Playground API
export const playgroundApi = {
  listSessions: async (params?: { is_public?: boolean }): Promise<PlaygroundSession[]> => {
    const response = await api.get('/playground/sessions', { params })
    return response.data
  },
  createSession: async (data: PlaygroundSessionCreate): Promise<PlaygroundSession> => {
    const response = await api.post('/playground/sessions', data)
    return response.data
  },
  getSession: async (id: string): Promise<PlaygroundSession> => {
    const response = await api.get(`/playground/sessions/${id}`)
    return response.data
  },
  updateSession: async (id: string, data: Partial<PlaygroundSessionCreate>): Promise<PlaygroundSession> => {
    const response = await api.put(`/playground/sessions/${id}`, data)
    return response.data
  },
  deleteSession: async (id: string): Promise<void> => {
    await api.delete(`/playground/sessions/${id}`)
  },
}

// Deprecations API
export const deprecationsApi = {
  list: async (): Promise<ModelDeprecation[]> => {
    const response = await api.get('/model-deprecations')
    return response.data
  },
  create: async (data: ModelDeprecationCreate): Promise<ModelDeprecation> => {
    const response = await api.post('/model-deprecations', data)
    return response.data
  },
  get: async (id: string): Promise<ModelDeprecation> => {
    const response = await api.get(`/model-deprecations/${id}`)
    return response.data
  },
  update: async (id: string, data: Partial<ModelDeprecationCreate>): Promise<ModelDeprecation> => {
    const response = await api.put(`/model-deprecations/${id}`, data)
    return response.data
  },
  delete: async (id: string): Promise<void> => {
    await api.delete(`/model-deprecations/${id}`)
  },
  check: async (modelName: string): Promise<{ deprecated: boolean; deprecation?: ModelDeprecation }> => {
    const response = await api.get(`/model-deprecations/check/${modelName}`)
    return response.data
  },
}

export const routingApi = {
  list: async (params?: { policy_type?: string; is_active?: boolean }): Promise<RoutingPolicy[]> => {
    const response = await api.get('/routing-policies', { params })
    return response.data
  },
  create: async (data: RoutingPolicyCreate): Promise<RoutingPolicy> => {
    const response = await api.post('/routing-policies', data)
    return response.data
  },
  get: async (id: string): Promise<RoutingPolicy> => {
    const response = await api.get(`/routing-policies/${id}`)
    return response.data
  },
  update: async (id: string, data: RoutingPolicyCreate): Promise<RoutingPolicy> => {
    const response = await api.put(`/routing-policies/${id}`, data)
    return response.data
  },
  delete: async (id: string): Promise<void> => {
    await api.delete(`/routing-policies/${id}`)
  },
  syncAll: async (): Promise<{ status: string; synced: number; errors: unknown[] }> => {
    const response = await api.post('/routing-policies/sync')
    return response.data
  },
  getLiteLLMStatus: async (): Promise<LiteLLMRouterStatus> => {
    const response = await api.get('/routing-policies/litellm-status')
    return response.data
  },
}

// SRE Agent API
export const sreApi = {
  listIncidents: async (params?: { status?: string; limit?: number }): Promise<SREIncidentSummary[]> => {
    const response = await api.get('/sre/incidents', { params })
    return response.data
  },
  getIncident: async (id: string): Promise<SREIncidentDetail> => {
    const response = await api.get(`/sre/incidents/${id}`)
    return response.data
  },
  approve: async (id: string): Promise<{ ok: boolean; status: string; executed: unknown[] }> => {
    const response = await api.post(`/sre/incidents/${id}/approve`)
    return response.data
  },
  reject: async (id: string, reason?: string): Promise<{ ok: boolean; status: string }> => {
    const response = await api.post(`/sre/incidents/${id}/reject`, { reason })
    return response.data
  },
  trigger: async (data: SRETriggerRequest): Promise<{ incident_id: string; status: string }> => {
    const response = await api.post('/sre/trigger', data)
    return response.data
  },
  stats: async (): Promise<SREStats> => {
    const response = await api.get('/sre/stats')
    return response.data
  },
}

// Leads (demo requests) API
export const leadsApi = {
  list: async (params?: { status?: LeadStatus; limit?: number }): Promise<Lead[]> => {
    const response = await api.get('/leads', { params })
    return response.data
  },
  get: async (id: string): Promise<Lead> => {
    const response = await api.get(`/leads/${id}`)
    return response.data
  },
  update: async (id: string, data: LeadUpdate): Promise<Lead> => {
    const response = await api.patch(`/leads/${id}`, data)
    return response.data
  },
}
