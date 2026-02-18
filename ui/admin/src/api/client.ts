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
