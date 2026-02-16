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
  WorkflowSummary,
  RealtimeMetrics,
  PlatformSettings,
  LoginResponse,
  RoutingPolicy,
  RoutingPolicyCreate,
  UserInfo,
} from '../types'

const api = axios.create({
  baseURL: '/api/v1',
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
      window.location.href = '/'
    }
    return Promise.reject(error)
  }
)

export default api

// Auth API
export const authApi = {
  login: async (apiKey: string): Promise<LoginResponse> => {
    const response = await axios.post('/auth/login', { api_key: apiKey })
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
}

// Workflows API
export const workflowsApi = {
  list: async (): Promise<WorkflowSummary[]> => {
    const response = await api.get('/workflows')
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
