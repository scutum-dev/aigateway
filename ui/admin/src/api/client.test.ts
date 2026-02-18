import { describe, it, expect, vi, beforeEach, type Mock } from 'vitest'
import type { AxiosInstance, InternalAxiosRequestConfig, AxiosResponse } from 'axios'

// ---------------------------------------------------------------------------
// Mock axios BEFORE importing the module under test.
// vi.hoisted() runs before vi.mock() hoisting, so the variables are available.
// ---------------------------------------------------------------------------
const {
  mockGet,
  mockPost,
  mockPut,
  mockDelete,
  mockInstance,
  interceptors,
} = vi.hoisted(() => {
  const mockGet = vi.fn()
  const mockPost = vi.fn()
  const mockPut = vi.fn()
  const mockDelete = vi.fn()

  // Capture interceptors so we can invoke them in tests
  const interceptors = {
    requestFulfilled: undefined as unknown as (config: InternalAxiosRequestConfig) => InternalAxiosRequestConfig,
    responseFulfilled: undefined as unknown as (response: AxiosResponse) => AxiosResponse,
    responseRejected: undefined as unknown as (error: unknown) => unknown,
  }

  const mockInstance = {
    get: mockGet,
    post: mockPost,
    put: mockPut,
    delete: mockDelete,
    interceptors: {
      request: {
        use: vi.fn((fulfilled: (config: InternalAxiosRequestConfig) => InternalAxiosRequestConfig) => {
          interceptors.requestFulfilled = fulfilled
        }),
      },
      response: {
        use: vi.fn(
          (
            fulfilled: (response: AxiosResponse) => AxiosResponse,
            rejected: (error: unknown) => unknown,
          ) => {
            interceptors.responseFulfilled = fulfilled
            interceptors.responseRejected = rejected
          },
        ),
      },
    },
  } as unknown as AxiosInstance

  return { mockGet, mockPost, mockPut, mockDelete, mockInstance, interceptors }
})

vi.mock('axios', () => {
  return {
    default: {
      create: vi.fn(() => mockInstance),
      post: vi.fn(),
    },
  }
})

// Now import everything that depends on axios
import axios from 'axios'
import api, {
  authApi,
  mcpServersApi,
  agentsApi,
  workflowsApi,
  reportsApi,
  guardrailsApi,
  settingsApi,
  modelsApi,
  keysApi,
  teamsApi,
  budgetsApi,
  organizationsApi,
  auditApi,
  dlpApi,
  promptsApi,
  rateLimitsApi,
  modelAccessApi,
  chargebackApi,
  slaApi,
  abTestsApi,
  cacheApi,
  eventsApi,
  playgroundApi,
  deprecationsApi,
} from './client'

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------
/** Build a minimal fake Axios response wrapping `data`. */
function fakeResponse<T>(data: T) {
  return { data, status: 200, statusText: 'OK', headers: {}, config: {} }
}

// ---------------------------------------------------------------------------
// Reset all mocks between tests
// ---------------------------------------------------------------------------
beforeEach(() => {
  vi.clearAllMocks()
  localStorage.clear()
})

// ===================================================================
// axios instance & interceptors
// ===================================================================
describe('api instance', () => {
  it('exports the api instance with expected methods', () => {
    expect(api.get).toBeDefined()
    expect(api.post).toBeDefined()
    expect(api.put).toBeDefined()
    expect(api.delete).toBeDefined()
  })

  it('exports the created axios instance as default', () => {
    expect(api).toBe(mockInstance)
  })
})

describe('request interceptor – auth token', () => {
  it('attaches Authorization header when token exists in localStorage', () => {
    localStorage.setItem('admin_token', 'test-jwt-token')
    const config = { headers: {} } as InternalAxiosRequestConfig
    const result = interceptors.requestFulfilled(config)
    expect(result.headers.Authorization).toBe('Bearer test-jwt-token')
  })

  it('does not attach Authorization header when no token', () => {
    const config = { headers: {} } as InternalAxiosRequestConfig
    const result = interceptors.requestFulfilled(config)
    expect(result.headers.Authorization).toBeUndefined()
  })
})

describe('response interceptor – 401 handling', () => {
  it('passes through successful responses', () => {
    const response = fakeResponse({ ok: true })
    expect(interceptors.responseFulfilled(response as unknown as AxiosResponse)).toBe(response)
  })

  it('clears tokens and redirects on 401', async () => {
    localStorage.setItem('admin_token', 'tok')
    localStorage.setItem('token_expires_at', '12345')

    // window.location is readonly in jsdom but href is settable
    const originalHref = window.location.href
    const error = { response: { status: 401 } }

    await expect(interceptors.responseRejected(error)).rejects.toBe(error)
    expect(localStorage.getItem('admin_token')).toBeNull()
    expect(localStorage.getItem('token_expires_at')).toBeNull()
  })

  it('rejects non-401 errors without clearing tokens', async () => {
    localStorage.setItem('admin_token', 'tok')
    const error = { response: { status: 500 } }

    await expect(interceptors.responseRejected(error)).rejects.toBe(error)
    expect(localStorage.getItem('admin_token')).toBe('tok')
  })
})

// ===================================================================
// authApi
// ===================================================================
describe('authApi', () => {
  it('login posts to /auth/login with api_key and uses raw axios', async () => {
    const data = { token: 'jwt', expires_at: 'x' }
    ;(axios.post as Mock).mockResolvedValue(fakeResponse(data))

    const result = await authApi.login('my-key')
    expect(axios.post).toHaveBeenCalledWith('/auth/login', { api_key: 'my-key' })
    expect(result).toEqual(data)
  })

  it('me calls GET /auth/me on the api instance', async () => {
    const user = { user_id: 'u1', role: 'admin' }
    mockGet.mockResolvedValue(fakeResponse(user))

    const result = await authApi.me()
    expect(mockGet).toHaveBeenCalledWith('/auth/me')
    expect(result).toEqual(user)
  })
})

// ===================================================================
// mcpServersApi
// ===================================================================
describe('mcpServersApi', () => {
  it('list calls GET /mcp-servers', async () => {
    mockGet.mockResolvedValue(fakeResponse([]))
    expect(await mcpServersApi.list()).toEqual([])
    expect(mockGet).toHaveBeenCalledWith('/mcp-servers')
  })

  it('create posts to /mcp-servers', async () => {
    const body = { name: 's1', url: 'http://x' } as any
    mockPost.mockResolvedValue(fakeResponse({ id: '1', ...body }))
    const result = await mcpServersApi.create(body)
    expect(mockPost).toHaveBeenCalledWith('/mcp-servers', body)
    expect(result.id).toBe('1')
  })

  it('update puts to /mcp-servers/:id', async () => {
    const body = { name: 'updated' } as any
    mockPut.mockResolvedValue(fakeResponse({ id: '1', ...body }))
    await mcpServersApi.update('1', body)
    expect(mockPut).toHaveBeenCalledWith('/mcp-servers/1', body)
  })

  it('delete calls DELETE /mcp-servers/:id', async () => {
    mockDelete.mockResolvedValue(fakeResponse(null))
    await mcpServersApi.delete('1')
    expect(mockDelete).toHaveBeenCalledWith('/mcp-servers/1')
  })

  it('test posts to /mcp-servers/:id/test', async () => {
    mockPost.mockResolvedValue(fakeResponse({ success: true }))
    const result = await mcpServersApi.test('1')
    expect(mockPost).toHaveBeenCalledWith('/mcp-servers/1/test')
    expect(result.success).toBe(true)
  })

  it('sync posts to /mcp-servers/sync', async () => {
    mockPost.mockResolvedValue(fakeResponse({ synced: 3 }))
    await mcpServersApi.sync()
    expect(mockPost).toHaveBeenCalledWith('/mcp-servers/sync')
  })

  it('previewConfig calls GET /mcp-servers/sync/preview', async () => {
    mockGet.mockResolvedValue(fakeResponse({ config: {} }))
    await mcpServersApi.previewConfig()
    expect(mockGet).toHaveBeenCalledWith('/mcp-servers/sync/preview')
  })
})

// ===================================================================
// agentsApi
// ===================================================================
describe('agentsApi', () => {
  it('list calls GET /agents', async () => {
    mockGet.mockResolvedValue(fakeResponse([]))
    expect(await agentsApi.list()).toEqual([])
    expect(mockGet).toHaveBeenCalledWith('/agents')
  })

  it('create posts to /agents', async () => {
    const body = { name: 'a1' } as any
    mockPost.mockResolvedValue(fakeResponse({ id: '1' }))
    await agentsApi.create(body)
    expect(mockPost).toHaveBeenCalledWith('/agents', body)
  })

  it('get calls GET /agents/:id', async () => {
    mockGet.mockResolvedValue(fakeResponse({ id: '1' }))
    const result = await agentsApi.get('1')
    expect(mockGet).toHaveBeenCalledWith('/agents/1')
    expect(result.id).toBe('1')
  })

  it('update puts to /agents/:id', async () => {
    const body = { name: 'updated' } as any
    mockPut.mockResolvedValue(fakeResponse({ id: '1' }))
    await agentsApi.update('1', body)
    expect(mockPut).toHaveBeenCalledWith('/agents/1', body)
  })

  it('delete calls DELETE /agents/:id', async () => {
    mockDelete.mockResolvedValue(fakeResponse(null))
    await agentsApi.delete('1')
    expect(mockDelete).toHaveBeenCalledWith('/agents/1')
  })

  it('test posts to /agents/:id/test', async () => {
    mockPost.mockResolvedValue(fakeResponse({ success: true }))
    await agentsApi.test('1')
    expect(mockPost).toHaveBeenCalledWith('/agents/1/test')
  })
})

// ===================================================================
// workflowsApi
// ===================================================================
describe('workflowsApi', () => {
  it('list calls GET /workflows', async () => {
    mockGet.mockResolvedValue(fakeResponse([]))
    expect(await workflowsApi.list()).toEqual([])
    expect(mockGet).toHaveBeenCalledWith('/workflows')
  })

  it('create posts to /workflows', async () => {
    const body = { name: 'w1' } as any
    mockPost.mockResolvedValue(fakeResponse({ id: '1' }))
    await workflowsApi.create(body)
    expect(mockPost).toHaveBeenCalledWith('/workflows', body)
  })

  it('listTemplates calls GET /workflow-templates', async () => {
    mockGet.mockResolvedValue(fakeResponse([]))
    await workflowsApi.listTemplates()
    expect(mockGet).toHaveBeenCalledWith('/workflow-templates')
  })

  it('execute posts to /workflow-executions', async () => {
    const body = { workflow_id: 'w1', input: {} } as any
    mockPost.mockResolvedValue(fakeResponse({ execution_id: 'e1' }))
    await workflowsApi.execute(body)
    expect(mockPost).toHaveBeenCalledWith('/workflow-executions', body)
  })

  it('listExecutions calls GET /workflow-executions', async () => {
    mockGet.mockResolvedValue(fakeResponse([]))
    await workflowsApi.listExecutions()
    expect(mockGet).toHaveBeenCalledWith('/workflow-executions')
  })

  it('getExecution calls GET /workflow-executions/:id', async () => {
    mockGet.mockResolvedValue(fakeResponse({ id: 'e1' }))
    const result = await workflowsApi.getExecution('e1')
    expect(mockGet).toHaveBeenCalledWith('/workflow-executions/e1')
    expect(result.id).toBe('e1')
  })
})

// ===================================================================
// reportsApi
// ===================================================================
describe('reportsApi', () => {
  it('summary calls GET /reports/summary', async () => {
    const data = { total_cost: 100 }
    mockGet.mockResolvedValue(fakeResponse(data))
    const result = await reportsApi.summary()
    expect(mockGet).toHaveBeenCalledWith('/reports/summary')
    expect(result).toEqual(data)
  })
})

// ===================================================================
// guardrailsApi
// ===================================================================
describe('guardrailsApi', () => {
  it('list calls GET /guardrails', async () => {
    mockGet.mockResolvedValue(fakeResponse([]))
    expect(await guardrailsApi.list()).toEqual([])
    expect(mockGet).toHaveBeenCalledWith('/guardrails')
  })

  it('create posts to /guardrails', async () => {
    const body = { name: 'g1' } as any
    mockPost.mockResolvedValue(fakeResponse({ id: '1' }))
    await guardrailsApi.create(body)
    expect(mockPost).toHaveBeenCalledWith('/guardrails', body)
  })

  it('get calls GET /guardrails/:id', async () => {
    mockGet.mockResolvedValue(fakeResponse({ id: '1' }))
    await guardrailsApi.get('1')
    expect(mockGet).toHaveBeenCalledWith('/guardrails/1')
  })

  it('update puts to /guardrails/:id', async () => {
    const body = { name: 'updated' } as any
    mockPut.mockResolvedValue(fakeResponse({ id: '1' }))
    await guardrailsApi.update('1', body)
    expect(mockPut).toHaveBeenCalledWith('/guardrails/1', body)
  })

  it('delete calls DELETE /guardrails/:id', async () => {
    mockDelete.mockResolvedValue(fakeResponse(null))
    await guardrailsApi.delete('1')
    expect(mockDelete).toHaveBeenCalledWith('/guardrails/1')
  })

  it('assignToTeam posts with priority param', async () => {
    mockPost.mockResolvedValue(fakeResponse(null))
    await guardrailsApi.assignToTeam('g1', 't1', 5)
    expect(mockPost).toHaveBeenCalledWith('/guardrails/g1/assign/t1', null, {
      params: { priority: 5 },
    })
  })

  it('assignToTeam posts without priority param when undefined', async () => {
    mockPost.mockResolvedValue(fakeResponse(null))
    await guardrailsApi.assignToTeam('g1', 't1')
    expect(mockPost).toHaveBeenCalledWith('/guardrails/g1/assign/t1', null, {
      params: undefined,
    })
  })

  it('unassignFromTeam calls DELETE /guardrails/:configId/assign/:teamId', async () => {
    mockDelete.mockResolvedValue(fakeResponse(null))
    await guardrailsApi.unassignFromTeam('g1', 't1')
    expect(mockDelete).toHaveBeenCalledWith('/guardrails/g1/assign/t1')
  })

  it('assignments calls GET /guardrail-assignments', async () => {
    mockGet.mockResolvedValue(fakeResponse([]))
    await guardrailsApi.assignments()
    expect(mockGet).toHaveBeenCalledWith('/guardrail-assignments')
  })

  it('events calls GET /guardrail-events with params', async () => {
    const params = { team_id: 't1', limit: 10 }
    mockGet.mockResolvedValue(fakeResponse([]))
    await guardrailsApi.events(params)
    expect(mockGet).toHaveBeenCalledWith('/guardrail-events', { params })
  })

  it('events works without params', async () => {
    mockGet.mockResolvedValue(fakeResponse([]))
    await guardrailsApi.events()
    expect(mockGet).toHaveBeenCalledWith('/guardrail-events', { params: undefined })
  })
})

// ===================================================================
// settingsApi
// ===================================================================
describe('settingsApi', () => {
  it('get calls GET /settings', async () => {
    mockGet.mockResolvedValue(fakeResponse({ theme: 'dark' }))
    const result = await settingsApi.get()
    expect(mockGet).toHaveBeenCalledWith('/settings')
    expect(result.theme).toBe('dark')
  })

  it('update puts to /settings', async () => {
    const body = { theme: 'light' } as any
    mockPut.mockResolvedValue(fakeResponse(body))
    await settingsApi.update(body)
    expect(mockPut).toHaveBeenCalledWith('/settings', body)
  })
})

// ===================================================================
// modelsApi
// ===================================================================
describe('modelsApi', () => {
  it('list calls GET /models', async () => {
    mockGet.mockResolvedValue(fakeResponse({ data: [] }))
    const result = await modelsApi.list()
    expect(mockGet).toHaveBeenCalledWith('/models')
    expect(result).toEqual({ data: [] })
  })

  it('get calls GET /models/:modelId', async () => {
    mockGet.mockResolvedValue(fakeResponse({ model_name: 'gpt-4' }))
    const result = await modelsApi.get('gpt-4')
    expect(mockGet).toHaveBeenCalledWith('/models/gpt-4')
    expect(result.model_name).toBe('gpt-4')
  })

  it('create posts to /models', async () => {
    const body = { model_name: 'gpt-4' } as any
    mockPost.mockResolvedValue(fakeResponse({ id: '1' }))
    await modelsApi.create(body)
    expect(mockPost).toHaveBeenCalledWith('/models', body)
  })

  it('delete posts to /models/delete with { id }', async () => {
    mockPost.mockResolvedValue(fakeResponse(null))
    await modelsApi.delete('m1')
    expect(mockPost).toHaveBeenCalledWith('/models/delete', { id: 'm1' })
  })
})

// ===================================================================
// keysApi
// ===================================================================
describe('keysApi', () => {
  it('list calls GET /keys', async () => {
    mockGet.mockResolvedValue(fakeResponse([]))
    expect(await keysApi.list()).toEqual([])
    expect(mockGet).toHaveBeenCalledWith('/keys')
  })

  it('get calls GET /keys/:key', async () => {
    mockGet.mockResolvedValue(fakeResponse({ key: 'sk-xxx' }))
    await keysApi.get('sk-xxx')
    expect(mockGet).toHaveBeenCalledWith('/keys/sk-xxx')
  })

  it('generate posts to /keys/generate', async () => {
    const body = { key_alias: 'test' } as any
    mockPost.mockResolvedValue(fakeResponse({ key: 'sk-new' }))
    const result = await keysApi.generate(body)
    expect(mockPost).toHaveBeenCalledWith('/keys/generate', body)
    expect(result.key).toBe('sk-new')
  })

  it('update posts to /keys/update', async () => {
    const body = { key: 'sk-xxx', key_alias: 'renamed' }
    mockPost.mockResolvedValue(fakeResponse({ ok: true }))
    await keysApi.update(body)
    expect(mockPost).toHaveBeenCalledWith('/keys/update', body)
  })

  it('delete posts to /keys/delete with { keys }', async () => {
    mockPost.mockResolvedValue(fakeResponse(null))
    await keysApi.delete(['k1', 'k2'])
    expect(mockPost).toHaveBeenCalledWith('/keys/delete', { keys: ['k1', 'k2'] })
  })
})

// ===================================================================
// teamsApi
// ===================================================================
describe('teamsApi', () => {
  it('list calls GET /teams', async () => {
    mockGet.mockResolvedValue(fakeResponse([]))
    await teamsApi.list()
    expect(mockGet).toHaveBeenCalledWith('/teams')
  })

  it('get calls GET /teams/:teamId', async () => {
    mockGet.mockResolvedValue(fakeResponse({ team_id: 't1' }))
    await teamsApi.get('t1')
    expect(mockGet).toHaveBeenCalledWith('/teams/t1')
  })

  it('create posts to /teams', async () => {
    const body = { team_alias: 'eng' } as any
    mockPost.mockResolvedValue(fakeResponse({ team_id: 't1' }))
    await teamsApi.create(body)
    expect(mockPost).toHaveBeenCalledWith('/teams', body)
  })

  it('update posts to /teams/update', async () => {
    const body = { team_id: 't1', team_alias: 'eng2' } as any
    mockPost.mockResolvedValue(fakeResponse({ team_id: 't1' }))
    await teamsApi.update(body)
    expect(mockPost).toHaveBeenCalledWith('/teams/update', body)
  })

  it('delete posts to /teams/delete with { team_ids }', async () => {
    mockPost.mockResolvedValue(fakeResponse(null))
    await teamsApi.delete(['t1', 't2'])
    expect(mockPost).toHaveBeenCalledWith('/teams/delete', { team_ids: ['t1', 't2'] })
  })

  it('addMember posts to /teams/:teamId/members', async () => {
    const member = { role: 'admin', user_id: 'u1' }
    mockPost.mockResolvedValue(fakeResponse({ ok: true }))
    await teamsApi.addMember('t1', member)
    expect(mockPost).toHaveBeenCalledWith('/teams/t1/members', { member })
  })

  it('deleteMember posts to /teams/:teamId/members/delete', async () => {
    mockPost.mockResolvedValue(fakeResponse(null))
    await teamsApi.deleteMember('t1', 'u1')
    expect(mockPost).toHaveBeenCalledWith('/teams/t1/members/delete', { user_id: 'u1' })
  })
})

// ===================================================================
// budgetsApi
// ===================================================================
describe('budgetsApi', () => {
  it('list calls GET /budgets', async () => {
    mockGet.mockResolvedValue(fakeResponse([]))
    await budgetsApi.list()
    expect(mockGet).toHaveBeenCalledWith('/budgets')
  })

  it('get calls GET /budgets/:budgetId', async () => {
    mockGet.mockResolvedValue(fakeResponse({ budget_id: 'b1' }))
    await budgetsApi.get('b1')
    expect(mockGet).toHaveBeenCalledWith('/budgets/b1')
  })

  it('create posts to /budgets', async () => {
    const body = { max_budget: 100 } as any
    mockPost.mockResolvedValue(fakeResponse({ budget_id: 'b1' }))
    await budgetsApi.create(body)
    expect(mockPost).toHaveBeenCalledWith('/budgets', body)
  })

  it('update posts to /budgets/update', async () => {
    const body = { budget_id: 'b1', max_budget: 200 } as any
    mockPost.mockResolvedValue(fakeResponse(body))
    await budgetsApi.update(body)
    expect(mockPost).toHaveBeenCalledWith('/budgets/update', body)
  })

  it('delete posts to /budgets/delete with { id }', async () => {
    mockPost.mockResolvedValue(fakeResponse(null))
    await budgetsApi.delete('b1')
    expect(mockPost).toHaveBeenCalledWith('/budgets/delete', { id: 'b1' })
  })
})

// ===================================================================
// organizationsApi
// ===================================================================
describe('organizationsApi', () => {
  it('list calls GET /organizations', async () => {
    mockGet.mockResolvedValue(fakeResponse([]))
    await organizationsApi.list()
    expect(mockGet).toHaveBeenCalledWith('/organizations')
  })

  it('get calls GET /organizations/:id', async () => {
    mockGet.mockResolvedValue(fakeResponse({ id: 'o1' }))
    await organizationsApi.get('o1')
    expect(mockGet).toHaveBeenCalledWith('/organizations/o1')
  })

  it('create posts to /organizations', async () => {
    const body = { name: 'Acme' } as any
    mockPost.mockResolvedValue(fakeResponse({ id: 'o1' }))
    await organizationsApi.create(body)
    expect(mockPost).toHaveBeenCalledWith('/organizations', body)
  })

  it('update puts to /organizations/:id', async () => {
    const body = { name: 'Acme2' } as any
    mockPut.mockResolvedValue(fakeResponse({ id: 'o1' }))
    await organizationsApi.update('o1', body)
    expect(mockPut).toHaveBeenCalledWith('/organizations/o1', body)
  })

  it('delete calls DELETE /organizations/:id', async () => {
    mockDelete.mockResolvedValue(fakeResponse(null))
    await organizationsApi.delete('o1')
    expect(mockDelete).toHaveBeenCalledWith('/organizations/o1')
  })

  it('listBUs calls GET /organizations/:orgId/business-units', async () => {
    mockGet.mockResolvedValue(fakeResponse([]))
    await organizationsApi.listBUs('o1')
    expect(mockGet).toHaveBeenCalledWith('/organizations/o1/business-units')
  })

  it('createBU posts to /organizations/:orgId/business-units', async () => {
    const body = { name: 'BU1' } as any
    mockPost.mockResolvedValue(fakeResponse({ id: 'bu1' }))
    await organizationsApi.createBU('o1', body)
    expect(mockPost).toHaveBeenCalledWith('/organizations/o1/business-units', body)
  })

  it('updateBU puts to /organizations/:orgId/business-units/:buId', async () => {
    const body = { name: 'BU2' } as any
    mockPut.mockResolvedValue(fakeResponse({ id: 'bu1' }))
    await organizationsApi.updateBU('o1', 'bu1', body)
    expect(mockPut).toHaveBeenCalledWith('/organizations/o1/business-units/bu1', body)
  })

  it('deleteBU calls DELETE /organizations/:orgId/business-units/:buId', async () => {
    mockDelete.mockResolvedValue(fakeResponse(null))
    await organizationsApi.deleteBU('o1', 'bu1')
    expect(mockDelete).toHaveBeenCalledWith('/organizations/o1/business-units/bu1')
  })

  it('listTeams calls GET /organizations/:orgId/teams', async () => {
    mockGet.mockResolvedValue(fakeResponse([]))
    await organizationsApi.listTeams('o1')
    expect(mockGet).toHaveBeenCalledWith('/organizations/o1/teams')
  })

  it('assignTeam posts to /organizations/:orgId/teams/:teamId', async () => {
    mockPost.mockResolvedValue(fakeResponse(null))
    await organizationsApi.assignTeam('o1', 't1', 'bu1')
    expect(mockPost).toHaveBeenCalledWith('/organizations/o1/teams/t1', { bu_id: 'bu1' })
  })

  it('assignTeam sends undefined bu_id when not provided', async () => {
    mockPost.mockResolvedValue(fakeResponse(null))
    await organizationsApi.assignTeam('o1', 't1')
    expect(mockPost).toHaveBeenCalledWith('/organizations/o1/teams/t1', { bu_id: undefined })
  })

  it('removeTeam calls DELETE /organizations/:orgId/teams/:teamId', async () => {
    mockDelete.mockResolvedValue(fakeResponse(null))
    await organizationsApi.removeTeam('o1', 't1')
    expect(mockDelete).toHaveBeenCalledWith('/organizations/o1/teams/t1')
  })

  it('listMembers calls GET /organizations/:orgId/members', async () => {
    mockGet.mockResolvedValue(fakeResponse([]))
    await organizationsApi.listMembers('o1')
    expect(mockGet).toHaveBeenCalledWith('/organizations/o1/members')
  })

  it('addMember posts to /organizations/:orgId/members', async () => {
    const body = { user_id: 'u1', role: 'admin' }
    mockPost.mockResolvedValue(fakeResponse({ id: 'm1' }))
    await organizationsApi.addMember('o1', body)
    expect(mockPost).toHaveBeenCalledWith('/organizations/o1/members', body)
  })

  it('updateMember puts to /organizations/:orgId/members/:userId', async () => {
    mockPut.mockResolvedValue(fakeResponse(null))
    await organizationsApi.updateMember('o1', 'u1', { role: 'viewer' })
    expect(mockPut).toHaveBeenCalledWith('/organizations/o1/members/u1', { role: 'viewer' })
  })

  it('removeMember calls DELETE /organizations/:orgId/members/:userId', async () => {
    mockDelete.mockResolvedValue(fakeResponse(null))
    await organizationsApi.removeMember('o1', 'u1')
    expect(mockDelete).toHaveBeenCalledWith('/organizations/o1/members/u1')
  })

  it('getSSO calls GET /organizations/:orgId/sso', async () => {
    mockGet.mockResolvedValue(fakeResponse({ provider: 'okta' }))
    await organizationsApi.getSSO('o1')
    expect(mockGet).toHaveBeenCalledWith('/organizations/o1/sso')
  })

  it('updateSSO posts to /organizations/:orgId/sso', async () => {
    const body = { provider: 'okta', client_id: 'xxx' }
    mockPost.mockResolvedValue(fakeResponse(body))
    await organizationsApi.updateSSO('o1', body)
    expect(mockPost).toHaveBeenCalledWith('/organizations/o1/sso', body)
  })

  it('deleteSSO calls DELETE /organizations/:orgId/sso', async () => {
    mockDelete.mockResolvedValue(fakeResponse(null))
    await organizationsApi.deleteSSO('o1')
    expect(mockDelete).toHaveBeenCalledWith('/organizations/o1/sso')
  })
})

// ===================================================================
// auditApi
// ===================================================================
describe('auditApi', () => {
  it('list calls GET /audit-logs with params', async () => {
    const params = { actor_id: 'u1', limit: 50 }
    mockGet.mockResolvedValue(fakeResponse([]))
    await auditApi.list(params)
    expect(mockGet).toHaveBeenCalledWith('/audit-logs', { params })
  })

  it('list works without params', async () => {
    mockGet.mockResolvedValue(fakeResponse([]))
    await auditApi.list()
    expect(mockGet).toHaveBeenCalledWith('/audit-logs', { params: undefined })
  })

  it('export calls GET /audit-logs/export with format and responseType', async () => {
    mockGet.mockResolvedValue(fakeResponse(new Blob()))
    await auditApi.export('json')
    expect(mockGet).toHaveBeenCalledWith('/audit-logs/export', {
      params: { format: 'json' },
      responseType: 'blob',
    })
  })

  it('export defaults to csv format', async () => {
    mockGet.mockResolvedValue(fakeResponse(new Blob()))
    await auditApi.export()
    expect(mockGet).toHaveBeenCalledWith('/audit-logs/export', {
      params: { format: 'csv' },
      responseType: 'blob',
    })
  })
})

// ===================================================================
// dlpApi
// ===================================================================
describe('dlpApi', () => {
  it('listDetectors calls GET /detectors', async () => {
    mockGet.mockResolvedValue(fakeResponse([]))
    await dlpApi.listDetectors()
    expect(mockGet).toHaveBeenCalledWith('/detectors')
  })

  it('createDetector posts to /detectors', async () => {
    const body = { name: 'd1' } as any
    mockPost.mockResolvedValue(fakeResponse({ id: '1' }))
    await dlpApi.createDetector(body)
    expect(mockPost).toHaveBeenCalledWith('/detectors', body)
  })

  it('getDetector calls GET /detectors/:id', async () => {
    mockGet.mockResolvedValue(fakeResponse({ id: '1' }))
    await dlpApi.getDetector('1')
    expect(mockGet).toHaveBeenCalledWith('/detectors/1')
  })

  it('updateDetector puts to /detectors/:id', async () => {
    const body = { name: 'updated' } as any
    mockPut.mockResolvedValue(fakeResponse({ id: '1' }))
    await dlpApi.updateDetector('1', body)
    expect(mockPut).toHaveBeenCalledWith('/detectors/1', body)
  })

  it('deleteDetector calls DELETE /detectors/:id', async () => {
    mockDelete.mockResolvedValue(fakeResponse(null))
    await dlpApi.deleteDetector('1')
    expect(mockDelete).toHaveBeenCalledWith('/detectors/1')
  })

  it('testDetector posts to /detectors/:id/test with { text }', async () => {
    mockPost.mockResolvedValue(fakeResponse({ matches: [] }))
    const result = await dlpApi.testDetector('1', 'sensitive data')
    expect(mockPost).toHaveBeenCalledWith('/detectors/1/test', { text: 'sensitive data' })
    expect(result.matches).toEqual([])
  })

  it('attachDetector posts to /guardrails/:guardrailId/detectors/:detectorId', async () => {
    mockPost.mockResolvedValue(fakeResponse(null))
    await dlpApi.attachDetector('g1', 'd1')
    expect(mockPost).toHaveBeenCalledWith('/guardrails/g1/detectors/d1')
  })

  it('detachDetector calls DELETE /guardrails/:guardrailId/detectors/:detectorId', async () => {
    mockDelete.mockResolvedValue(fakeResponse(null))
    await dlpApi.detachDetector('g1', 'd1')
    expect(mockDelete).toHaveBeenCalledWith('/guardrails/g1/detectors/d1')
  })

  it('getContentPolicies calls GET /teams/:teamId/content-policies', async () => {
    mockGet.mockResolvedValue(fakeResponse([]))
    await dlpApi.getContentPolicies('t1')
    expect(mockGet).toHaveBeenCalledWith('/teams/t1/content-policies')
  })

  it('updateContentPolicy puts to /teams/:teamId/content-policies', async () => {
    const body = { policy_type: 'block', config: {} }
    mockPut.mockResolvedValue(fakeResponse(body))
    await dlpApi.updateContentPolicy('t1', body)
    expect(mockPut).toHaveBeenCalledWith('/teams/t1/content-policies', body)
  })
})

// ===================================================================
// promptsApi
// ===================================================================
describe('promptsApi', () => {
  it('list calls GET /prompts with params', async () => {
    const params = { category: 'system', status: 'active' }
    mockGet.mockResolvedValue(fakeResponse([]))
    await promptsApi.list(params)
    expect(mockGet).toHaveBeenCalledWith('/prompts', { params })
  })

  it('get calls GET /prompts/:slug', async () => {
    mockGet.mockResolvedValue(fakeResponse({ slug: 'my-prompt' }))
    await promptsApi.get('my-prompt')
    expect(mockGet).toHaveBeenCalledWith('/prompts/my-prompt')
  })

  it('create posts to /prompts', async () => {
    const body = { slug: 'new', template_text: 'hi' } as any
    mockPost.mockResolvedValue(fakeResponse({ id: '1' }))
    await promptsApi.create(body)
    expect(mockPost).toHaveBeenCalledWith('/prompts', body)
  })

  it('update puts to /prompts/:id', async () => {
    const body = { template_text: 'updated' } as any
    mockPut.mockResolvedValue(fakeResponse({ id: '1' }))
    await promptsApi.update('1', body)
    expect(mockPut).toHaveBeenCalledWith('/prompts/1', body)
  })

  it('delete calls DELETE /prompts/:id', async () => {
    mockDelete.mockResolvedValue(fakeResponse(null))
    await promptsApi.delete('1')
    expect(mockDelete).toHaveBeenCalledWith('/prompts/1')
  })

  it('getVersions calls GET /prompts/:slug/versions', async () => {
    mockGet.mockResolvedValue(fakeResponse([]))
    await promptsApi.getVersions('my-prompt')
    expect(mockGet).toHaveBeenCalledWith('/prompts/my-prompt/versions')
  })

  it('createVersion posts to /prompts/:slug/versions', async () => {
    const body = { template_text: 'v2' }
    mockPost.mockResolvedValue(fakeResponse({ version: 2 }))
    await promptsApi.createVersion('my-prompt', body)
    expect(mockPost).toHaveBeenCalledWith('/prompts/my-prompt/versions', body)
  })

  it('render posts to /prompts/:slug/render', async () => {
    const variables = { name: 'World' }
    mockPost.mockResolvedValue(fakeResponse({ rendered: 'Hello World' }))
    const result = await promptsApi.render('my-prompt', variables)
    expect(mockPost).toHaveBeenCalledWith('/prompts/my-prompt/render', { variables })
    expect(result.rendered).toBe('Hello World')
  })

  it('submitReview posts to /prompts/:id/submit-review', async () => {
    mockPost.mockResolvedValue(fakeResponse({ id: 'a1', status: 'pending' }))
    await promptsApi.submitReview('1')
    expect(mockPost).toHaveBeenCalledWith('/prompts/1/submit-review')
  })

  it('listApprovals calls GET /prompt-approvals', async () => {
    mockGet.mockResolvedValue(fakeResponse([]))
    await promptsApi.listApprovals()
    expect(mockGet).toHaveBeenCalledWith('/prompt-approvals')
  })

  it('approve posts to /prompt-approvals/:id/approve', async () => {
    mockPost.mockResolvedValue(fakeResponse(null))
    await promptsApi.approve('a1', 'looks good')
    expect(mockPost).toHaveBeenCalledWith('/prompt-approvals/a1/approve', { comment: 'looks good' })
  })

  it('reject posts to /prompt-approvals/:id/reject', async () => {
    mockPost.mockResolvedValue(fakeResponse(null))
    await promptsApi.reject('a1', 'needs work')
    expect(mockPost).toHaveBeenCalledWith('/prompt-approvals/a1/reject', { comment: 'needs work' })
  })

  it('analytics calls GET /prompts/:slug/analytics', async () => {
    mockGet.mockResolvedValue(fakeResponse({ usage_count: 42 }))
    await promptsApi.analytics('my-prompt')
    expect(mockGet).toHaveBeenCalledWith('/prompts/my-prompt/analytics')
  })
})

// ===================================================================
// rateLimitsApi
// ===================================================================
describe('rateLimitsApi', () => {
  it('list calls GET /rate-limits', async () => {
    mockGet.mockResolvedValue(fakeResponse([]))
    await rateLimitsApi.list()
    expect(mockGet).toHaveBeenCalledWith('/rate-limits')
  })

  it('create posts to /rate-limits', async () => {
    const body = { name: 'rl1' } as any
    mockPost.mockResolvedValue(fakeResponse({ id: '1' }))
    await rateLimitsApi.create(body)
    expect(mockPost).toHaveBeenCalledWith('/rate-limits', body)
  })

  it('get calls GET /rate-limits/:id', async () => {
    mockGet.mockResolvedValue(fakeResponse({ id: '1' }))
    await rateLimitsApi.get('1')
    expect(mockGet).toHaveBeenCalledWith('/rate-limits/1')
  })

  it('update puts to /rate-limits/:id', async () => {
    const body = { name: 'updated' } as any
    mockPut.mockResolvedValue(fakeResponse({ id: '1' }))
    await rateLimitsApi.update('1', body)
    expect(mockPut).toHaveBeenCalledWith('/rate-limits/1', body)
  })

  it('delete calls DELETE /rate-limits/:id', async () => {
    mockDelete.mockResolvedValue(fakeResponse(null))
    await rateLimitsApi.delete('1')
    expect(mockDelete).toHaveBeenCalledWith('/rate-limits/1')
  })

  it('status calls GET /rate-limits/status', async () => {
    mockGet.mockResolvedValue(fakeResponse({ active: 5 }))
    await rateLimitsApi.status()
    expect(mockGet).toHaveBeenCalledWith('/rate-limits/status')
  })

  it('events calls GET /rate-limit-events with params', async () => {
    const params = { limit: 10 }
    mockGet.mockResolvedValue(fakeResponse([]))
    await rateLimitsApi.events(params)
    expect(mockGet).toHaveBeenCalledWith('/rate-limit-events', { params })
  })
})

// ===================================================================
// modelAccessApi
// ===================================================================
describe('modelAccessApi', () => {
  it('listTiers calls GET /model-access/tiers', async () => {
    mockGet.mockResolvedValue(fakeResponse([]))
    await modelAccessApi.listTiers()
    expect(mockGet).toHaveBeenCalledWith('/model-access/tiers')
  })

  it('createTier posts to /model-access/tiers', async () => {
    const body = { name: 'gold' } as any
    mockPost.mockResolvedValue(fakeResponse({ id: '1' }))
    await modelAccessApi.createTier(body)
    expect(mockPost).toHaveBeenCalledWith('/model-access/tiers', body)
  })

  it('updateTier puts to /model-access/tiers/:id', async () => {
    const body = { name: 'platinum' } as any
    mockPut.mockResolvedValue(fakeResponse({ id: '1' }))
    await modelAccessApi.updateTier('1', body)
    expect(mockPut).toHaveBeenCalledWith('/model-access/tiers/1', body)
  })

  it('deleteTier calls DELETE /model-access/tiers/:id', async () => {
    mockDelete.mockResolvedValue(fakeResponse(null))
    await modelAccessApi.deleteTier('1')
    expect(mockDelete).toHaveBeenCalledWith('/model-access/tiers/1')
  })

  it('listRequests calls GET /model-access/requests with params', async () => {
    const params = { status: 'pending' }
    mockGet.mockResolvedValue(fakeResponse([]))
    await modelAccessApi.listRequests(params)
    expect(mockGet).toHaveBeenCalledWith('/model-access/requests', { params })
  })

  it('createRequest posts to /model-access/requests', async () => {
    const body = { model: 'gpt-4', reason: 'need it' } as any
    mockPost.mockResolvedValue(fakeResponse({ id: 'r1' }))
    await modelAccessApi.createRequest(body)
    expect(mockPost).toHaveBeenCalledWith('/model-access/requests', body)
  })

  it('approveRequest posts to /model-access/requests/:id/approve', async () => {
    mockPost.mockResolvedValue(fakeResponse(null))
    await modelAccessApi.approveRequest('r1', 'approved')
    expect(mockPost).toHaveBeenCalledWith('/model-access/requests/r1/approve', { comment: 'approved' })
  })

  it('rejectRequest posts to /model-access/requests/:id/reject', async () => {
    mockPost.mockResolvedValue(fakeResponse(null))
    await modelAccessApi.rejectRequest('r1', 'denied')
    expect(mockPost).toHaveBeenCalledWith('/model-access/requests/r1/reject', { comment: 'denied' })
  })

  it('myAccess calls GET /model-access/my-access', async () => {
    mockGet.mockResolvedValue(fakeResponse([]))
    await modelAccessApi.myAccess()
    expect(mockGet).toHaveBeenCalledWith('/model-access/my-access')
  })
})

// ===================================================================
// chargebackApi
// ===================================================================
describe('chargebackApi', () => {
  it('listRules calls GET /cost-allocation/rules', async () => {
    mockGet.mockResolvedValue(fakeResponse([]))
    await chargebackApi.listRules()
    expect(mockGet).toHaveBeenCalledWith('/cost-allocation/rules')
  })

  it('createRule posts to /cost-allocation/rules', async () => {
    const body = { name: 'rule1' } as any
    mockPost.mockResolvedValue(fakeResponse({ id: '1' }))
    await chargebackApi.createRule(body)
    expect(mockPost).toHaveBeenCalledWith('/cost-allocation/rules', body)
  })

  it('updateRule puts to /cost-allocation/rules/:id', async () => {
    const body = { name: 'updated' } as any
    mockPut.mockResolvedValue(fakeResponse({ id: '1' }))
    await chargebackApi.updateRule('1', body)
    expect(mockPut).toHaveBeenCalledWith('/cost-allocation/rules/1', body)
  })

  it('deleteRule calls DELETE /cost-allocation/rules/:id', async () => {
    mockDelete.mockResolvedValue(fakeResponse(null))
    await chargebackApi.deleteRule('1')
    expect(mockDelete).toHaveBeenCalledWith('/cost-allocation/rules/1')
  })

  it('generateReport posts to /chargeback/reports/generate', async () => {
    mockPost.mockResolvedValue(fakeResponse({ id: 'r1' }))
    await chargebackApi.generateReport('2024-01')
    expect(mockPost).toHaveBeenCalledWith('/chargeback/reports/generate', { period: '2024-01' })
  })

  it('listReports calls GET /chargeback/reports', async () => {
    mockGet.mockResolvedValue(fakeResponse([]))
    await chargebackApi.listReports()
    expect(mockGet).toHaveBeenCalledWith('/chargeback/reports')
  })

  it('getReport calls GET /chargeback/reports/:id', async () => {
    mockGet.mockResolvedValue(fakeResponse({ id: 'r1' }))
    await chargebackApi.getReport('r1')
    expect(mockGet).toHaveBeenCalledWith('/chargeback/reports/r1')
  })

  it('exportReport calls GET /chargeback/reports/:id/export with params and responseType', async () => {
    mockGet.mockResolvedValue(fakeResponse(new Blob()))
    await chargebackApi.exportReport('r1', 'json')
    expect(mockGet).toHaveBeenCalledWith('/chargeback/reports/r1/export', {
      params: { format: 'json' },
      responseType: 'blob',
    })
  })

  it('exportReport defaults to csv format', async () => {
    mockGet.mockResolvedValue(fakeResponse(new Blob()))
    await chargebackApi.exportReport('r1')
    expect(mockGet).toHaveBeenCalledWith('/chargeback/reports/r1/export', {
      params: { format: 'csv' },
      responseType: 'blob',
    })
  })

  it('finalizeReport posts to /chargeback/reports/:id/finalize', async () => {
    mockPost.mockResolvedValue(fakeResponse(null))
    await chargebackApi.finalizeReport('r1')
    expect(mockPost).toHaveBeenCalledWith('/chargeback/reports/r1/finalize')
  })

  it('getForecasts calls GET /reports/forecast', async () => {
    mockGet.mockResolvedValue(fakeResponse([]))
    await chargebackApi.getForecasts()
    expect(mockGet).toHaveBeenCalledWith('/reports/forecast')
  })

  it('generateForecast posts to /reports/forecast/generate', async () => {
    const params = { team_id: 't1' }
    mockPost.mockResolvedValue(fakeResponse([]))
    await chargebackApi.generateForecast(params)
    expect(mockPost).toHaveBeenCalledWith('/reports/forecast/generate', params)
  })
})

// ===================================================================
// slaApi
// ===================================================================
describe('slaApi', () => {
  it('listDefinitions calls GET /sla/definitions', async () => {
    mockGet.mockResolvedValue(fakeResponse([]))
    await slaApi.listDefinitions()
    expect(mockGet).toHaveBeenCalledWith('/sla/definitions')
  })

  it('createDefinition posts to /sla/definitions', async () => {
    const body = { name: 'sla1' } as any
    mockPost.mockResolvedValue(fakeResponse({ id: '1' }))
    await slaApi.createDefinition(body)
    expect(mockPost).toHaveBeenCalledWith('/sla/definitions', body)
  })

  it('updateDefinition puts to /sla/definitions/:id', async () => {
    const body = { name: 'updated' } as any
    mockPut.mockResolvedValue(fakeResponse({ id: '1' }))
    await slaApi.updateDefinition('1', body)
    expect(mockPut).toHaveBeenCalledWith('/sla/definitions/1', body)
  })

  it('deleteDefinition calls DELETE /sla/definitions/:id', async () => {
    mockDelete.mockResolvedValue(fakeResponse(null))
    await slaApi.deleteDefinition('1')
    expect(mockDelete).toHaveBeenCalledWith('/sla/definitions/1')
  })

  it('getHealth calls GET /sla/health', async () => {
    mockGet.mockResolvedValue(fakeResponse([]))
    await slaApi.getHealth()
    expect(mockGet).toHaveBeenCalledWith('/sla/health')
  })

  it('getHealthHistory calls GET /sla/health/history with params', async () => {
    const params = { provider: 'openai', hours: 24 }
    mockGet.mockResolvedValue(fakeResponse([]))
    await slaApi.getHealthHistory(params)
    expect(mockGet).toHaveBeenCalledWith('/sla/health/history', { params })
  })

  it('listViolations calls GET /sla/violations with params', async () => {
    const params = { resolved: false }
    mockGet.mockResolvedValue(fakeResponse([]))
    await slaApi.listViolations(params)
    expect(mockGet).toHaveBeenCalledWith('/sla/violations', { params })
  })

  it('activeViolations calls GET /sla/violations/active', async () => {
    mockGet.mockResolvedValue(fakeResponse([]))
    await slaApi.activeViolations()
    expect(mockGet).toHaveBeenCalledWith('/sla/violations/active')
  })

  it('resolveViolation posts to /sla/violations/:id/resolve', async () => {
    mockPost.mockResolvedValue(fakeResponse(null))
    await slaApi.resolveViolation('v1')
    expect(mockPost).toHaveBeenCalledWith('/sla/violations/v1/resolve')
  })

  it('listFailoverRules calls GET /sla/failover-rules', async () => {
    mockGet.mockResolvedValue(fakeResponse([]))
    await slaApi.listFailoverRules()
    expect(mockGet).toHaveBeenCalledWith('/sla/failover-rules')
  })

  it('createFailoverRule posts to /sla/failover-rules', async () => {
    const body = { name: 'fr1' } as any
    mockPost.mockResolvedValue(fakeResponse({ id: '1' }))
    await slaApi.createFailoverRule(body)
    expect(mockPost).toHaveBeenCalledWith('/sla/failover-rules', body)
  })

  it('updateFailoverRule puts to /sla/failover-rules/:id', async () => {
    const body = { name: 'updated' } as any
    mockPut.mockResolvedValue(fakeResponse({ id: '1' }))
    await slaApi.updateFailoverRule('1', body)
    expect(mockPut).toHaveBeenCalledWith('/sla/failover-rules/1', body)
  })

  it('deleteFailoverRule calls DELETE /sla/failover-rules/:id', async () => {
    mockDelete.mockResolvedValue(fakeResponse(null))
    await slaApi.deleteFailoverRule('1')
    expect(mockDelete).toHaveBeenCalledWith('/sla/failover-rules/1')
  })

  it('triggerFailover posts to /sla/failover-rules/:id/trigger', async () => {
    mockPost.mockResolvedValue(fakeResponse(null))
    await slaApi.triggerFailover('1')
    expect(mockPost).toHaveBeenCalledWith('/sla/failover-rules/1/trigger')
  })

  it('getCompliance calls GET /sla/compliance', async () => {
    mockGet.mockResolvedValue(fakeResponse({ score: 99 }))
    await slaApi.getCompliance()
    expect(mockGet).toHaveBeenCalledWith('/sla/compliance')
  })
})

// ===================================================================
// abTestsApi
// ===================================================================
describe('abTestsApi', () => {
  it('list calls GET /ab-tests', async () => {
    mockGet.mockResolvedValue(fakeResponse([]))
    await abTestsApi.list()
    expect(mockGet).toHaveBeenCalledWith('/ab-tests')
  })

  it('get calls GET /ab-tests/:id', async () => {
    mockGet.mockResolvedValue(fakeResponse({ id: '1' }))
    await abTestsApi.get('1')
    expect(mockGet).toHaveBeenCalledWith('/ab-tests/1')
  })

  it('create posts to /ab-tests', async () => {
    const body = { name: 'test1' } as any
    mockPost.mockResolvedValue(fakeResponse({ id: '1' }))
    await abTestsApi.create(body)
    expect(mockPost).toHaveBeenCalledWith('/ab-tests', body)
  })

  it('update puts to /ab-tests/:id', async () => {
    const body = { name: 'updated' } as any
    mockPut.mockResolvedValue(fakeResponse({ id: '1' }))
    await abTestsApi.update('1', body)
    expect(mockPut).toHaveBeenCalledWith('/ab-tests/1', body)
  })

  it('delete calls DELETE /ab-tests/:id', async () => {
    mockDelete.mockResolvedValue(fakeResponse(null))
    await abTestsApi.delete('1')
    expect(mockDelete).toHaveBeenCalledWith('/ab-tests/1')
  })

  it('start posts to /ab-tests/:id/start', async () => {
    mockPost.mockResolvedValue(fakeResponse(null))
    await abTestsApi.start('1')
    expect(mockPost).toHaveBeenCalledWith('/ab-tests/1/start')
  })

  it('stop posts to /ab-tests/:id/stop', async () => {
    mockPost.mockResolvedValue(fakeResponse(null))
    await abTestsApi.stop('1')
    expect(mockPost).toHaveBeenCalledWith('/ab-tests/1/stop')
  })

  it('promote posts to /ab-tests/:id/promote', async () => {
    mockPost.mockResolvedValue(fakeResponse(null))
    await abTestsApi.promote('1')
    expect(mockPost).toHaveBeenCalledWith('/ab-tests/1/promote')
  })

  it('snapshots calls GET /ab-tests/:id/snapshots', async () => {
    mockGet.mockResolvedValue(fakeResponse([]))
    await abTestsApi.snapshots('1')
    expect(mockGet).toHaveBeenCalledWith('/ab-tests/1/snapshots')
  })
})

// ===================================================================
// cacheApi
// ===================================================================
describe('cacheApi', () => {
  it('stats calls GET /cache/stats', async () => {
    mockGet.mockResolvedValue(fakeResponse({ hit_rate: 0.85 }))
    const result = await cacheApi.stats()
    expect(mockGet).toHaveBeenCalledWith('/cache/stats')
    expect(result.hit_rate).toBe(0.85)
  })

  it('clear posts to /cache/clear', async () => {
    mockPost.mockResolvedValue(fakeResponse(null))
    await cacheApi.clear()
    expect(mockPost).toHaveBeenCalledWith('/cache/clear')
  })

  it('settings puts to /cache/settings', async () => {
    const body = { ttl: 3600 } as any
    mockPut.mockResolvedValue(fakeResponse(body))
    await cacheApi.settings(body)
    expect(mockPut).toHaveBeenCalledWith('/cache/settings', body)
  })

  it('entries calls GET /cache/entries with params', async () => {
    const params = { limit: 20, offset: 0 }
    mockGet.mockResolvedValue(fakeResponse([]))
    await cacheApi.entries(params)
    expect(mockGet).toHaveBeenCalledWith('/cache/entries', { params })
  })

  it('deleteEntry calls DELETE /cache/entries/:id', async () => {
    mockDelete.mockResolvedValue(fakeResponse(null))
    await cacheApi.deleteEntry('e1')
    expect(mockDelete).toHaveBeenCalledWith('/cache/entries/e1')
  })
})

// ===================================================================
// eventsApi
// ===================================================================
describe('eventsApi', () => {
  it('listSubscriptions calls GET /events/subscriptions', async () => {
    mockGet.mockResolvedValue(fakeResponse([]))
    await eventsApi.listSubscriptions()
    expect(mockGet).toHaveBeenCalledWith('/events/subscriptions')
  })

  it('createSubscription posts to /events/subscriptions', async () => {
    const body = { event_type: 'request', url: 'http://hook' } as any
    mockPost.mockResolvedValue(fakeResponse({ id: '1' }))
    await eventsApi.createSubscription(body)
    expect(mockPost).toHaveBeenCalledWith('/events/subscriptions', body)
  })

  it('getSubscription calls GET /events/subscriptions/:id', async () => {
    mockGet.mockResolvedValue(fakeResponse({ id: '1' }))
    await eventsApi.getSubscription('1')
    expect(mockGet).toHaveBeenCalledWith('/events/subscriptions/1')
  })

  it('updateSubscription puts to /events/subscriptions/:id', async () => {
    const body = { url: 'http://new-hook' } as any
    mockPut.mockResolvedValue(fakeResponse({ id: '1' }))
    await eventsApi.updateSubscription('1', body)
    expect(mockPut).toHaveBeenCalledWith('/events/subscriptions/1', body)
  })

  it('deleteSubscription calls DELETE /events/subscriptions/:id', async () => {
    mockDelete.mockResolvedValue(fakeResponse(null))
    await eventsApi.deleteSubscription('1')
    expect(mockDelete).toHaveBeenCalledWith('/events/subscriptions/1')
  })

  it('listEvents calls GET /events/log with params', async () => {
    const params = { event_type: 'request', limit: 50 }
    mockGet.mockResolvedValue(fakeResponse([]))
    await eventsApi.listEvents(params)
    expect(mockGet).toHaveBeenCalledWith('/events/log', { params })
  })

  it('sendTestEvent posts to /events/test', async () => {
    const body = { event_type: 'test', payload: { key: 'value' } }
    mockPost.mockResolvedValue(fakeResponse(null))
    await eventsApi.sendTestEvent(body)
    expect(mockPost).toHaveBeenCalledWith('/events/test', body)
  })
})

// ===================================================================
// playgroundApi
// ===================================================================
describe('playgroundApi', () => {
  it('listSessions calls GET /playground/sessions with params', async () => {
    const params = { is_public: true }
    mockGet.mockResolvedValue(fakeResponse([]))
    await playgroundApi.listSessions(params)
    expect(mockGet).toHaveBeenCalledWith('/playground/sessions', { params })
  })

  it('createSession posts to /playground/sessions', async () => {
    const body = { name: 'sess1' } as any
    mockPost.mockResolvedValue(fakeResponse({ id: '1' }))
    await playgroundApi.createSession(body)
    expect(mockPost).toHaveBeenCalledWith('/playground/sessions', body)
  })

  it('getSession calls GET /playground/sessions/:id', async () => {
    mockGet.mockResolvedValue(fakeResponse({ id: '1' }))
    await playgroundApi.getSession('1')
    expect(mockGet).toHaveBeenCalledWith('/playground/sessions/1')
  })

  it('updateSession puts to /playground/sessions/:id', async () => {
    const body = { name: 'updated' } as any
    mockPut.mockResolvedValue(fakeResponse({ id: '1' }))
    await playgroundApi.updateSession('1', body)
    expect(mockPut).toHaveBeenCalledWith('/playground/sessions/1', body)
  })

  it('deleteSession calls DELETE /playground/sessions/:id', async () => {
    mockDelete.mockResolvedValue(fakeResponse(null))
    await playgroundApi.deleteSession('1')
    expect(mockDelete).toHaveBeenCalledWith('/playground/sessions/1')
  })
})

// ===================================================================
// deprecationsApi
// ===================================================================
describe('deprecationsApi', () => {
  it('list calls GET /model-deprecations', async () => {
    mockGet.mockResolvedValue(fakeResponse([]))
    await deprecationsApi.list()
    expect(mockGet).toHaveBeenCalledWith('/model-deprecations')
  })

  it('create posts to /model-deprecations', async () => {
    const body = { model: 'gpt-3', sunset_date: '2025-01-01' } as any
    mockPost.mockResolvedValue(fakeResponse({ id: '1' }))
    await deprecationsApi.create(body)
    expect(mockPost).toHaveBeenCalledWith('/model-deprecations', body)
  })

  it('get calls GET /model-deprecations/:id', async () => {
    mockGet.mockResolvedValue(fakeResponse({ id: '1' }))
    await deprecationsApi.get('1')
    expect(mockGet).toHaveBeenCalledWith('/model-deprecations/1')
  })

  it('update puts to /model-deprecations/:id', async () => {
    const body = { sunset_date: '2025-06-01' } as any
    mockPut.mockResolvedValue(fakeResponse({ id: '1' }))
    await deprecationsApi.update('1', body)
    expect(mockPut).toHaveBeenCalledWith('/model-deprecations/1', body)
  })

  it('delete calls DELETE /model-deprecations/:id', async () => {
    mockDelete.mockResolvedValue(fakeResponse(null))
    await deprecationsApi.delete('1')
    expect(mockDelete).toHaveBeenCalledWith('/model-deprecations/1')
  })

  it('check calls GET /model-deprecations/check/:modelName', async () => {
    mockGet.mockResolvedValue(fakeResponse({ deprecated: true }))
    const result = await deprecationsApi.check('gpt-3')
    expect(mockGet).toHaveBeenCalledWith('/model-deprecations/check/gpt-3')
    expect(result.deprecated).toBe(true)
  })
})
