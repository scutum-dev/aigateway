import axios from 'axios'
import type {
  ModelConfig,
  ModelUpdate,
  Budget,
  BudgetCreate,
  BudgetUpdate,
  Team,
  TeamCreate,
  TeamMemberAdd,
  MCPServerConfig,
  MCPServerCreate,
  MCPServerUpdate,
  MCPTestResult,
  GatewaySyncResult,
  GatewayConfigPreview,
  WorkflowSummary,
  WorkflowCreate,
  WorkflowExecuteRequest,
  WorkflowExecutionSummary,
  WorkflowExecutionDetail,
  KeyGenerateRequest,
  KeyGenerateResponse,
  KeyUpdateRequest,
  KeyDeleteRequest,
  RealtimeMetrics,
  PlatformSettings,
  LoginResponse,
  RoutingPolicy,
  RoutingPolicyCreate,
  UserInfo,
  GuardrailConfig,
  GuardrailConfigCreate,
  GuardrailConfigUpdate,
  GuardrailEvent,
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

// Models API
export const modelsApi = {
  list: async (): Promise<ModelConfig[]> => {
    const response = await api.get('/models')
    return response.data
  },
  update: async (modelId: string, data: ModelUpdate): Promise<ModelConfig> => {
    const response = await api.put(`/models/${modelId}`, data)
    return response.data
  },
}

// Routing Policies API
export const policiesApi = {
  list: async (): Promise<RoutingPolicy[]> => {
    const response = await api.get('/routing-policies')
    return response.data
  },
  create: async (data: RoutingPolicyCreate): Promise<RoutingPolicy> => {
    const response = await api.post('/routing-policies', data)
    return response.data
  },
  delete: async (id: string): Promise<void> => {
    const response = await api.delete(`/routing-policies/${id}`)
    return response.data
  },
}

// Budgets API
export const budgetsApi = {
  list: async (): Promise<Budget[]> => {
    const response = await api.get('/budgets')
    return response.data
  },
  create: async (data: BudgetCreate): Promise<Budget> => {
    const response = await api.post('/budgets', data)
    return response.data
  },
  update: async (id: string, data: BudgetUpdate): Promise<Budget> => {
    const response = await api.put(`/budgets/${id}`, data)
    return response.data
  },
}

// Teams API
export const teamsApi = {
  list: async (): Promise<Team[]> => {
    const response = await api.get('/teams')
    return response.data
  },
  create: async (data: TeamCreate): Promise<Team> => {
    const response = await api.post('/teams', data)
    return response.data
  },
  addMember: async (teamId: string, data: TeamMemberAdd): Promise<Team> => {
    const response = await api.post(`/teams/${teamId}/members`, data)
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

// API Keys API (proxy to LiteLLM)
export const keysApi = {
  list: async (): Promise<unknown> => {
    const response = await api.get('/keys')
    return response.data
  },
  generate: async (data: KeyGenerateRequest): Promise<KeyGenerateResponse> => {
    const response = await api.post('/keys/generate', data)
    return response.data
  },
  getInfo: async (key: string): Promise<unknown> => {
    const response = await api.get(`/keys/${encodeURIComponent(key)}`)
    return response.data
  },
  update: async (data: KeyUpdateRequest): Promise<unknown> => {
    const response = await api.post('/keys/update', data)
    return response.data
  },
  delete: async (data: KeyDeleteRequest): Promise<unknown> => {
    const response = await api.post('/keys/delete', data)
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

// Metrics API
export const metricsApi = {
  realtime: async (): Promise<RealtimeMetrics> => {
    const response = await api.get('/metrics/realtime')
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
