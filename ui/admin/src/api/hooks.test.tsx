import { renderHook, waitFor, act } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import type { ReactNode } from 'react'

// ---- Mock every API module imported by hooks.ts ----
vi.mock('./client', () => ({
  default: { get: vi.fn(), post: vi.fn(), put: vi.fn(), delete: vi.fn() },

  mcpServersApi: {
    list: vi.fn(),
    create: vi.fn(),
    update: vi.fn(),
    delete: vi.fn(),
    test: vi.fn(),
    sync: vi.fn(),
    previewConfig: vi.fn(),
  },
  agentsApi: {
    list: vi.fn(),
    create: vi.fn(),
    update: vi.fn(),
    delete: vi.fn(),
    test: vi.fn(),
  },
  workflowsApi: {
    list: vi.fn(),
    create: vi.fn(),
    execute: vi.fn(),
    listExecutions: vi.fn(),
    getExecution: vi.fn(),
  },
  reportsApi: {
    summary: vi.fn(),
  },
  guardrailsApi: {
    list: vi.fn(),
    create: vi.fn(),
    update: vi.fn(),
    delete: vi.fn(),
    events: vi.fn(),
    assignments: vi.fn(),
    assignToTeam: vi.fn(),
    unassignFromTeam: vi.fn(),
  },
  settingsApi: {
    get: vi.fn(),
    update: vi.fn(),
  },
  modelsApi: {
    list: vi.fn(),
    create: vi.fn(),
    delete: vi.fn(),
  },
  keysApi: {
    list: vi.fn(),
    generate: vi.fn(),
    delete: vi.fn(),
  },
  teamsApi: {
    list: vi.fn(),
    create: vi.fn(),
    update: vi.fn(),
    delete: vi.fn(),
    addMember: vi.fn(),
    deleteMember: vi.fn(),
  },
  budgetsApi: {
    list: vi.fn(),
    create: vi.fn(),
    update: vi.fn(),
    delete: vi.fn(),
  },
  organizationsApi: {
    list: vi.fn(),
    get: vi.fn(),
    create: vi.fn(),
    update: vi.fn(),
    delete: vi.fn(),
    listBUs: vi.fn(),
    createBU: vi.fn(),
    listMembers: vi.fn(),
  },
  auditApi: {
    list: vi.fn(),
  },
  dlpApi: {
    listDetectors: vi.fn(),
    createDetector: vi.fn(),
    deleteDetector: vi.fn(),
  },
  promptsApi: {
    list: vi.fn(),
    get: vi.fn(),
    create: vi.fn(),
    update: vi.fn(),
    delete: vi.fn(),
    listApprovals: vi.fn(),
  },
  rateLimitsApi: {
    list: vi.fn(),
    create: vi.fn(),
    update: vi.fn(),
    delete: vi.fn(),
    events: vi.fn(),
  },
  modelAccessApi: {
    listTiers: vi.fn(),
    createTier: vi.fn(),
    listRequests: vi.fn(),
    createRequest: vi.fn(),
    myAccess: vi.fn(),
  },
  chargebackApi: {
    listRules: vi.fn(),
    createRule: vi.fn(),
    deleteRule: vi.fn(),
    listReports: vi.fn(),
    getForecasts: vi.fn(),
  },
  slaApi: {
    listDefinitions: vi.fn(),
    createDefinition: vi.fn(),
    getHealth: vi.fn(),
    listViolations: vi.fn(),
    activeViolations: vi.fn(),
    listFailoverRules: vi.fn(),
    createFailoverRule: vi.fn(),
  },
  abTestsApi: {
    list: vi.fn(),
    get: vi.fn(),
    create: vi.fn(),
    delete: vi.fn(),
    start: vi.fn(),
    stop: vi.fn(),
    promote: vi.fn(),
    snapshots: vi.fn(),
  },
  cacheApi: {
    stats: vi.fn(),
    entries: vi.fn(),
    clear: vi.fn(),
    deleteEntry: vi.fn(),
  },
  eventsApi: {
    listSubscriptions: vi.fn(),
    createSubscription: vi.fn(),
    updateSubscription: vi.fn(),
    deleteSubscription: vi.fn(),
    listEvents: vi.fn(),
    sendTestEvent: vi.fn(),
  },
  playgroundApi: {
    listSessions: vi.fn(),
    createSession: vi.fn(),
    deleteSession: vi.fn(),
  },
  deprecationsApi: {
    list: vi.fn(),
    create: vi.fn(),
    update: vi.fn(),
    delete: vi.fn(),
  },
}))

// Import mocks after vi.mock so we can reference them
import {
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

// Import all hooks under test
import {
  useMCPServers,
  useCreateMCPServer,
  useUpdateMCPServer,
  useDeleteMCPServer,
  useTestMCPServer,
  useSyncMCPToGateway,
  useGatewayConfigPreview,
  useAgents,
  useCreateAgent,
  useUpdateAgent,
  useDeleteAgent,
  useTestAgent,
  useWorkflows,
  useCreateWorkflow,
  useWorkflowExecutions,
  useWorkflowExecution,
  useExecuteWorkflow,
  useReportsSummary,
  useGuardrails,
  useCreateGuardrail,
  useUpdateGuardrail,
  useDeleteGuardrail,
  useGuardrailEvents,
  useGuardrailAssignments,
  useAssignGuardrail,
  useUnassignGuardrail,
  useSettings,
  useUpdateSettings,
  useModels,
  useCreateModel,
  useDeleteModel,
  useAPIKeys,
  useGenerateKey,
  useDeleteKey,
  useTeams,
  useCreateTeam,
  useUpdateTeam,
  useDeleteTeam,
  useAddTeamMember,
  useDeleteTeamMember,
  useBudgets,
  useCreateBudget,
  useUpdateBudget,
  useDeleteBudget,
  useOrganizations,
  useOrganization,
  useCreateOrganization,
  useUpdateOrganization,
  useDeleteOrganization,
  useBusinessUnits,
  useCreateBusinessUnit,
  useOrgMembers,
  useAuditLogs,
  useContentDetectors,
  useCreateDetector,
  useDeleteDetector,
  usePromptTemplates,
  usePromptTemplate,
  useCreatePromptTemplate,
  useUpdatePromptTemplate,
  useDeletePromptTemplate,
  usePromptApprovals,
  useRateLimitPolicies,
  useCreateRateLimitPolicy,
  useUpdateRateLimitPolicy,
  useDeleteRateLimitPolicy,
  useRateLimitEvents,
  useModelAccessTiers,
  useCreateModelAccessTier,
  useModelAccessRequests,
  useCreateModelAccessRequest,
  useMyModelAccess,
  useCostAllocationRules,
  useCreateCostAllocationRule,
  useDeleteCostAllocationRule,
  useChargebackReports,
  useBudgetForecasts,
  useSLADefinitions,
  useCreateSLADefinition,
  useProviderHealth,
  useSLAViolations,
  useActiveViolations,
  useFailoverRules,
  useCreateFailoverRule,
  useABTests,
  useABTest,
  useCreateABTest,
  useDeleteABTest,
  useStartABTest,
  useStopABTest,
  usePromoteABTest,
  useABTestSnapshots,
  useCacheStats,
  useCacheEntries,
  useClearCache,
  useDeleteCacheEntry,
  useEventSubscriptions,
  useCreateEventSubscription,
  useUpdateEventSubscription,
  useDeleteEventSubscription,
  useEventLog,
  useSendTestEvent,
  usePlaygroundSessions,
  useCreatePlaygroundSession,
  useDeletePlaygroundSession,
  useModelDeprecations,
  useCreateModelDeprecation,
  useUpdateModelDeprecation,
  useDeleteModelDeprecation,
} from './hooks'

// ---- Helpers ----

let queryClient: QueryClient

function createWrapper() {
  queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false, gcTime: 0 },
      mutations: { retry: false },
    },
  })
  return function Wrapper({ children }: { children: ReactNode }) {
    return (
      <QueryClientProvider client={queryClient}>
        {children}
      </QueryClientProvider>
    )
  }
}

beforeEach(() => {
  vi.clearAllMocks()
})

// ================================================================
// MCP Servers
// ================================================================
describe('MCP Servers hooks', () => {
  it('useMCPServers calls mcpServersApi.list and returns data', async () => {
    const data = [{ id: '1', name: 'mcp-1' }]
    vi.mocked(mcpServersApi.list).mockResolvedValue(data as any)
    const { result } = renderHook(() => useMCPServers(), { wrapper: createWrapper() })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(mcpServersApi.list).toHaveBeenCalledOnce()
    expect(result.current.data).toEqual(data)
  })

  it('useCreateMCPServer calls create and invalidates mcp-servers', async () => {
    vi.mocked(mcpServersApi.create).mockResolvedValue({ id: '2' } as any)
    const wrapper = createWrapper()
    const { result } = renderHook(() => useCreateMCPServer(), { wrapper })

    await act(async () => {
      result.current.mutate({ name: 'new-server' } as any)
    })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(mcpServersApi.create).toHaveBeenCalled()
    expect(vi.mocked(mcpServersApi.create).mock.calls[0][0]).toEqual({ name: 'new-server' })
  })

  it('useUpdateMCPServer calls update with id and data', async () => {
    vi.mocked(mcpServersApi.update).mockResolvedValue({ id: '1' } as any)
    const wrapper = createWrapper()
    const { result } = renderHook(() => useUpdateMCPServer(), { wrapper })

    await act(async () => {
      result.current.mutate({ id: '1', data: { name: 'updated' } as any })
    })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(mcpServersApi.update).toHaveBeenCalledWith('1', { name: 'updated' })
  })

  it('useDeleteMCPServer calls delete and invalidates mcp-servers', async () => {
    vi.mocked(mcpServersApi.delete).mockResolvedValue(undefined)
    const wrapper = createWrapper()
    const { result } = renderHook(() => useDeleteMCPServer(), { wrapper })

    await act(async () => {
      result.current.mutate('server-1')
    })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(mcpServersApi.delete).toHaveBeenCalled()
    expect(vi.mocked(mcpServersApi.delete).mock.calls[0][0]).toEqual('server-1')
  })

  it('useTestMCPServer calls test (no cache invalidation)', async () => {
    vi.mocked(mcpServersApi.test).mockResolvedValue({ success: true } as any)
    const wrapper = createWrapper()
    const { result } = renderHook(() => useTestMCPServer(), { wrapper })

    await act(async () => {
      result.current.mutate('server-1')
    })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(mcpServersApi.test).toHaveBeenCalled()
    expect(vi.mocked(mcpServersApi.test).mock.calls[0][0]).toEqual('server-1')
  })

  it('useSyncMCPToGateway calls sync and invalidates mcp-servers', async () => {
    vi.mocked(mcpServersApi.sync).mockResolvedValue({ synced: 3 } as any)
    const wrapper = createWrapper()
    const { result } = renderHook(() => useSyncMCPToGateway(), { wrapper })

    await act(async () => {
      result.current.mutate()
    })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(mcpServersApi.sync).toHaveBeenCalledOnce()
  })

  it('useGatewayConfigPreview is disabled by default', () => {
    vi.mocked(mcpServersApi.previewConfig).mockResolvedValue({ config: {} } as any)
    const { result } = renderHook(() => useGatewayConfigPreview(), { wrapper: createWrapper() })
    expect(result.current.isFetching).toBe(false)
    expect(mcpServersApi.previewConfig).not.toHaveBeenCalled()
  })
})

// ================================================================
// A2A Agents
// ================================================================
describe('Agents hooks', () => {
  it('useAgents calls agentsApi.list and returns data', async () => {
    const data = [{ id: 'a1', name: 'agent-1' }]
    vi.mocked(agentsApi.list).mockResolvedValue(data as any)
    const { result } = renderHook(() => useAgents(), { wrapper: createWrapper() })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(agentsApi.list).toHaveBeenCalledOnce()
    expect(result.current.data).toEqual(data)
  })

  it('useCreateAgent calls create and invalidates agents', async () => {
    vi.mocked(agentsApi.create).mockResolvedValue({ id: 'a2' } as any)
    const wrapper = createWrapper()
    const { result } = renderHook(() => useCreateAgent(), { wrapper })

    await act(async () => {
      result.current.mutate({ name: 'new-agent' } as any)
    })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(agentsApi.create).toHaveBeenCalled()
    expect(vi.mocked(agentsApi.create).mock.calls[0][0]).toEqual({ name: 'new-agent' })
  })

  it('useUpdateAgent calls update with id and data', async () => {
    vi.mocked(agentsApi.update).mockResolvedValue({ id: 'a1' } as any)
    const wrapper = createWrapper()
    const { result } = renderHook(() => useUpdateAgent(), { wrapper })

    await act(async () => {
      result.current.mutate({ id: 'a1', data: { name: 'updated' } as any })
    })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(agentsApi.update).toHaveBeenCalledWith('a1', { name: 'updated' })
  })

  it('useDeleteAgent calls delete and invalidates agents', async () => {
    vi.mocked(agentsApi.delete).mockResolvedValue(undefined)
    const wrapper = createWrapper()
    const { result } = renderHook(() => useDeleteAgent(), { wrapper })

    await act(async () => {
      result.current.mutate('a1')
    })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(agentsApi.delete).toHaveBeenCalled()
    expect(vi.mocked(agentsApi.delete).mock.calls[0][0]).toEqual('a1')
  })

  it('useTestAgent calls test (no cache invalidation)', async () => {
    vi.mocked(agentsApi.test).mockResolvedValue({ success: true } as any)
    const wrapper = createWrapper()
    const { result } = renderHook(() => useTestAgent(), { wrapper })

    await act(async () => {
      result.current.mutate('a1')
    })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(agentsApi.test).toHaveBeenCalled()
    expect(vi.mocked(agentsApi.test).mock.calls[0][0]).toEqual('a1')
  })
})

// ================================================================
// Workflows
// ================================================================
describe('Workflows hooks', () => {
  it('useWorkflows calls workflowsApi.list', async () => {
    const data = [{ id: 'w1', name: 'wf-1' }]
    vi.mocked(workflowsApi.list).mockResolvedValue(data as any)
    const { result } = renderHook(() => useWorkflows(), { wrapper: createWrapper() })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(result.current.data).toEqual(data)
  })

  it('useCreateWorkflow calls create and invalidates workflows', async () => {
    vi.mocked(workflowsApi.create).mockResolvedValue({ id: 'w2' } as any)
    const wrapper = createWrapper()
    const { result } = renderHook(() => useCreateWorkflow(), { wrapper })

    await act(async () => {
      result.current.mutate({ name: 'new-wf' } as any)
    })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(workflowsApi.create).toHaveBeenCalled()
    expect(vi.mocked(workflowsApi.create).mock.calls[0][0]).toEqual({ name: 'new-wf' })
  })

  it('useWorkflowExecutions polls with refetchInterval 10000', async () => {
    vi.mocked(workflowsApi.listExecutions).mockResolvedValue([])
    const { result } = renderHook(() => useWorkflowExecutions(), { wrapper: createWrapper() })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(workflowsApi.listExecutions).toHaveBeenCalled()
  })

  it('useWorkflowExecution is disabled when executionId is null', () => {
    const { result } = renderHook(() => useWorkflowExecution(null), { wrapper: createWrapper() })
    expect(result.current.isFetching).toBe(false)
    expect(workflowsApi.getExecution).not.toHaveBeenCalled()
  })

  it('useWorkflowExecution is enabled when executionId is provided', async () => {
    vi.mocked(workflowsApi.getExecution).mockResolvedValue({ id: 'ex1', status: 'completed' } as any)
    const { result } = renderHook(() => useWorkflowExecution('ex1'), { wrapper: createWrapper() })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(workflowsApi.getExecution).toHaveBeenCalled()
    expect(vi.mocked(workflowsApi.getExecution).mock.calls[0][0]).toEqual('ex1')
  })

  it('useExecuteWorkflow calls execute and invalidates workflow-executions', async () => {
    vi.mocked(workflowsApi.execute).mockResolvedValue({ id: 'ex2' })
    const wrapper = createWrapper()
    const { result } = renderHook(() => useExecuteWorkflow(), { wrapper })

    await act(async () => {
      result.current.mutate({ workflow_id: 'w1', input: {} } as any)
    })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(workflowsApi.execute).toHaveBeenCalled()
  })
})

// ================================================================
// Reports
// ================================================================
describe('Reports hooks', () => {
  it('useReportsSummary calls reportsApi.summary with refetchInterval 30000', async () => {
    const data = { total_spend: 100 }
    vi.mocked(reportsApi.summary).mockResolvedValue(data as any)
    const { result } = renderHook(() => useReportsSummary(), { wrapper: createWrapper() })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(reportsApi.summary).toHaveBeenCalledOnce()
    expect(result.current.data).toEqual(data)
  })
})

// ================================================================
// Guardrails
// ================================================================
describe('Guardrails hooks', () => {
  it('useGuardrails calls guardrailsApi.list', async () => {
    const data = [{ id: 'g1' }]
    vi.mocked(guardrailsApi.list).mockResolvedValue(data as any)
    const { result } = renderHook(() => useGuardrails(), { wrapper: createWrapper() })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(result.current.data).toEqual(data)
  })

  it('useCreateGuardrail calls create and invalidates guardrails', async () => {
    vi.mocked(guardrailsApi.create).mockResolvedValue({ id: 'g2' } as any)
    const wrapper = createWrapper()
    const { result } = renderHook(() => useCreateGuardrail(), { wrapper })

    await act(async () => {
      result.current.mutate({ name: 'new-guardrail' } as any)
    })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(guardrailsApi.create).toHaveBeenCalled()
    expect(vi.mocked(guardrailsApi.create).mock.calls[0][0]).toEqual({ name: 'new-guardrail' })
  })

  it('useUpdateGuardrail calls update with id and data', async () => {
    vi.mocked(guardrailsApi.update).mockResolvedValue({ id: 'g1' } as any)
    const wrapper = createWrapper()
    const { result } = renderHook(() => useUpdateGuardrail(), { wrapper })

    await act(async () => {
      result.current.mutate({ id: 'g1', data: { name: 'updated' } as any })
    })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(guardrailsApi.update).toHaveBeenCalledWith('g1', { name: 'updated' })
  })

  it('useDeleteGuardrail calls delete and invalidates guardrails + guardrail-assignments', async () => {
    vi.mocked(guardrailsApi.delete).mockResolvedValue(undefined)
    const wrapper = createWrapper()
    const invalidateSpy = vi.spyOn(queryClient, 'invalidateQueries')
    const { result } = renderHook(() => useDeleteGuardrail(), { wrapper })

    await act(async () => {
      result.current.mutate('g1')
    })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(guardrailsApi.delete).toHaveBeenCalled()
    expect(vi.mocked(guardrailsApi.delete).mock.calls[0][0]).toEqual('g1')
    expect(invalidateSpy).toHaveBeenCalledTimes(2)
    expect(vi.mocked(invalidateSpy).mock.calls[0][0]).toEqual({ queryKey: ['guardrails'] })
    expect(vi.mocked(invalidateSpy).mock.calls[1][0]).toEqual({ queryKey: ['guardrail-assignments'] })
  })

  it('useGuardrailEvents calls events with params and polls at 30000ms', async () => {
    vi.mocked(guardrailsApi.events).mockResolvedValue([])
    const params = { team_id: 't1' }
    const { result } = renderHook(() => useGuardrailEvents(params), { wrapper: createWrapper() })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(guardrailsApi.events).toHaveBeenCalled()
    expect(vi.mocked(guardrailsApi.events).mock.calls[0][0]).toEqual(params)
  })

  it('useGuardrailAssignments calls guardrailsApi.assignments', async () => {
    vi.mocked(guardrailsApi.assignments).mockResolvedValue([{ config_id: 'g1', team_id: 't1' }] as any)
    const { result } = renderHook(() => useGuardrailAssignments(), { wrapper: createWrapper() })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(guardrailsApi.assignments).toHaveBeenCalledOnce()
  })

  it('useAssignGuardrail calls assignToTeam and invalidates guardrail-assignments', async () => {
    vi.mocked(guardrailsApi.assignToTeam).mockResolvedValue(undefined)
    const wrapper = createWrapper()
    const { result } = renderHook(() => useAssignGuardrail(), { wrapper })

    await act(async () => {
      result.current.mutate({ configId: 'g1', teamId: 't1', priority: 1 })
    })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(guardrailsApi.assignToTeam).toHaveBeenCalledWith('g1', 't1', 1)
  })

  it('useUnassignGuardrail calls unassignFromTeam and invalidates guardrail-assignments', async () => {
    vi.mocked(guardrailsApi.unassignFromTeam).mockResolvedValue(undefined)
    const wrapper = createWrapper()
    const { result } = renderHook(() => useUnassignGuardrail(), { wrapper })

    await act(async () => {
      result.current.mutate({ configId: 'g1', teamId: 't1' })
    })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(guardrailsApi.unassignFromTeam).toHaveBeenCalledWith('g1', 't1')
  })
})

// ================================================================
// Settings
// ================================================================
describe('Settings hooks', () => {
  it('useSettings calls settingsApi.get', async () => {
    const data = { platform_name: 'Gateway' }
    vi.mocked(settingsApi.get).mockResolvedValue(data as any)
    const { result } = renderHook(() => useSettings(), { wrapper: createWrapper() })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(result.current.data).toEqual(data)
  })

  it('useUpdateSettings calls update and invalidates settings', async () => {
    vi.mocked(settingsApi.update).mockResolvedValue({ platform_name: 'New' } as any)
    const wrapper = createWrapper()
    const { result } = renderHook(() => useUpdateSettings(), { wrapper })

    await act(async () => {
      result.current.mutate({ platform_name: 'New' } as any)
    })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(settingsApi.update).toHaveBeenCalled()
    expect(vi.mocked(settingsApi.update).mock.calls[0][0]).toEqual({ platform_name: 'New' })
  })
})

// ================================================================
// Models
// ================================================================
describe('Models hooks', () => {
  it('useModels calls modelsApi.list', async () => {
    const data = { data: [{ model_name: 'gpt-4' }] }
    vi.mocked(modelsApi.list).mockResolvedValue(data as any)
    const { result } = renderHook(() => useModels(), { wrapper: createWrapper() })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(result.current.data).toEqual(data)
  })

  it('useCreateModel calls create and invalidates models', async () => {
    vi.mocked(modelsApi.create).mockResolvedValue({ id: 'm1' })
    const wrapper = createWrapper()
    const { result } = renderHook(() => useCreateModel(), { wrapper })

    await act(async () => {
      result.current.mutate({ model_name: 'gpt-4' } as any)
    })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(modelsApi.create).toHaveBeenCalled()
    expect(vi.mocked(modelsApi.create).mock.calls[0][0]).toEqual({ model_name: 'gpt-4' })
  })

  it('useDeleteModel calls delete and invalidates models', async () => {
    vi.mocked(modelsApi.delete).mockResolvedValue(undefined)
    const wrapper = createWrapper()
    const { result } = renderHook(() => useDeleteModel(), { wrapper })

    await act(async () => {
      result.current.mutate('model-id')
    })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(modelsApi.delete).toHaveBeenCalled()
    expect(vi.mocked(modelsApi.delete).mock.calls[0][0]).toEqual('model-id')
  })
})

// ================================================================
// API Keys
// ================================================================
describe('API Keys hooks', () => {
  it('useAPIKeys calls keysApi.list', async () => {
    const data = [{ token: 'sk-xxx' }]
    vi.mocked(keysApi.list).mockResolvedValue(data as any)
    const { result } = renderHook(() => useAPIKeys(), { wrapper: createWrapper() })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(result.current.data).toEqual(data)
  })

  it('useGenerateKey calls generate and invalidates keys', async () => {
    vi.mocked(keysApi.generate).mockResolvedValue({ key: 'sk-new' } as any)
    const wrapper = createWrapper()
    const { result } = renderHook(() => useGenerateKey(), { wrapper })

    await act(async () => {
      result.current.mutate({ key_alias: 'test-key' } as any)
    })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(keysApi.generate).toHaveBeenCalled()
    expect(vi.mocked(keysApi.generate).mock.calls[0][0]).toEqual({ key_alias: 'test-key' })
  })

  it('useDeleteKey calls delete with key array and invalidates keys', async () => {
    vi.mocked(keysApi.delete).mockResolvedValue(undefined)
    const wrapper = createWrapper()
    const { result } = renderHook(() => useDeleteKey(), { wrapper })

    await act(async () => {
      result.current.mutate(['sk-1', 'sk-2'])
    })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(keysApi.delete).toHaveBeenCalled()
    expect(vi.mocked(keysApi.delete).mock.calls[0][0]).toEqual(['sk-1', 'sk-2'])
  })
})

// ================================================================
// Teams
// ================================================================
describe('Teams hooks', () => {
  it('useTeams calls teamsApi.list', async () => {
    const data = [{ team_id: 't1' }]
    vi.mocked(teamsApi.list).mockResolvedValue(data as any)
    const { result } = renderHook(() => useTeams(), { wrapper: createWrapper() })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(result.current.data).toEqual(data)
  })

  it('useCreateTeam calls create and invalidates teams', async () => {
    vi.mocked(teamsApi.create).mockResolvedValue({ team_id: 't2' } as any)
    const wrapper = createWrapper()
    const { result } = renderHook(() => useCreateTeam(), { wrapper })

    await act(async () => {
      result.current.mutate({ team_alias: 'new-team' } as any)
    })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(teamsApi.create).toHaveBeenCalled()
    expect(vi.mocked(teamsApi.create).mock.calls[0][0]).toEqual({ team_alias: 'new-team' })
  })

  it('useUpdateTeam calls update and invalidates teams', async () => {
    vi.mocked(teamsApi.update).mockResolvedValue({ team_id: 't1' } as any)
    const wrapper = createWrapper()
    const { result } = renderHook(() => useUpdateTeam(), { wrapper })

    await act(async () => {
      result.current.mutate({ team_id: 't1', team_alias: 'renamed' } as any)
    })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(teamsApi.update).toHaveBeenCalled()
    expect(vi.mocked(teamsApi.update).mock.calls[0][0]).toEqual({ team_id: 't1', team_alias: 'renamed' })
  })

  it('useDeleteTeam calls delete with team id array', async () => {
    vi.mocked(teamsApi.delete).mockResolvedValue(undefined)
    const wrapper = createWrapper()
    const { result } = renderHook(() => useDeleteTeam(), { wrapper })

    await act(async () => {
      result.current.mutate(['t1', 't2'])
    })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(teamsApi.delete).toHaveBeenCalled()
    expect(vi.mocked(teamsApi.delete).mock.calls[0][0]).toEqual(['t1', 't2'])
  })

  it('useAddTeamMember calls addMember and invalidates teams', async () => {
    vi.mocked(teamsApi.addMember).mockResolvedValue({})
    const wrapper = createWrapper()
    const { result } = renderHook(() => useAddTeamMember(), { wrapper })

    await act(async () => {
      result.current.mutate({ teamId: 't1', member: { role: 'admin', user_id: 'u1' } })
    })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(teamsApi.addMember).toHaveBeenCalledWith('t1', { role: 'admin', user_id: 'u1' })
  })

  it('useDeleteTeamMember calls deleteMember and invalidates teams', async () => {
    vi.mocked(teamsApi.deleteMember).mockResolvedValue(undefined)
    const wrapper = createWrapper()
    const { result } = renderHook(() => useDeleteTeamMember(), { wrapper })

    await act(async () => {
      result.current.mutate({ teamId: 't1', userId: 'u1' })
    })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(teamsApi.deleteMember).toHaveBeenCalledWith('t1', 'u1')
  })
})

// ================================================================
// Budgets
// ================================================================
describe('Budgets hooks', () => {
  it('useBudgets calls budgetsApi.list', async () => {
    const data = [{ budget_id: 'b1' }]
    vi.mocked(budgetsApi.list).mockResolvedValue(data as any)
    const { result } = renderHook(() => useBudgets(), { wrapper: createWrapper() })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(result.current.data).toEqual(data)
  })

  it('useCreateBudget calls create and invalidates budgets', async () => {
    vi.mocked(budgetsApi.create).mockResolvedValue({ budget_id: 'b2' } as any)
    const wrapper = createWrapper()
    const { result } = renderHook(() => useCreateBudget(), { wrapper })

    await act(async () => {
      result.current.mutate({ max_budget: 100 } as any)
    })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(budgetsApi.create).toHaveBeenCalled()
    expect(vi.mocked(budgetsApi.create).mock.calls[0][0]).toEqual({ max_budget: 100 })
  })

  it('useUpdateBudget calls update and invalidates budgets', async () => {
    vi.mocked(budgetsApi.update).mockResolvedValue({ budget_id: 'b1' } as any)
    const wrapper = createWrapper()
    const { result } = renderHook(() => useUpdateBudget(), { wrapper })

    await act(async () => {
      result.current.mutate({ budget_id: 'b1', max_budget: 200 } as any)
    })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(budgetsApi.update).toHaveBeenCalled()
    expect(vi.mocked(budgetsApi.update).mock.calls[0][0]).toEqual({ budget_id: 'b1', max_budget: 200 })
  })

  it('useDeleteBudget calls delete and invalidates budgets', async () => {
    vi.mocked(budgetsApi.delete).mockResolvedValue(undefined)
    const wrapper = createWrapper()
    const { result } = renderHook(() => useDeleteBudget(), { wrapper })

    await act(async () => {
      result.current.mutate('b1')
    })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(budgetsApi.delete).toHaveBeenCalled()
    expect(vi.mocked(budgetsApi.delete).mock.calls[0][0]).toEqual('b1')
  })
})

// ================================================================
// Organizations
// ================================================================
describe('Organizations hooks', () => {
  it('useOrganizations calls organizationsApi.list', async () => {
    const data = [{ id: 'org-1', name: 'Org' }]
    vi.mocked(organizationsApi.list).mockResolvedValue(data as any)
    const { result } = renderHook(() => useOrganizations(), { wrapper: createWrapper() })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(result.current.data).toEqual(data)
  })

  it('useOrganization is disabled when id is null', () => {
    const { result } = renderHook(() => useOrganization(null), { wrapper: createWrapper() })
    expect(result.current.isFetching).toBe(false)
    expect(organizationsApi.get).not.toHaveBeenCalled()
  })

  it('useOrganization is enabled when id is provided', async () => {
    vi.mocked(organizationsApi.get).mockResolvedValue({ id: 'org-1' } as any)
    const { result } = renderHook(() => useOrganization('org-1'), { wrapper: createWrapper() })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(organizationsApi.get).toHaveBeenCalled()
    expect(vi.mocked(organizationsApi.get).mock.calls[0][0]).toEqual('org-1')
  })

  it('useCreateOrganization calls create and invalidates organizations', async () => {
    vi.mocked(organizationsApi.create).mockResolvedValue({ id: 'org-2' } as any)
    const wrapper = createWrapper()
    const { result } = renderHook(() => useCreateOrganization(), { wrapper })

    await act(async () => {
      result.current.mutate({ name: 'New Org' } as any)
    })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(organizationsApi.create).toHaveBeenCalled()
    expect(vi.mocked(organizationsApi.create).mock.calls[0][0]).toEqual({ name: 'New Org' })
  })

  it('useUpdateOrganization calls update with id and data', async () => {
    vi.mocked(organizationsApi.update).mockResolvedValue({ id: 'org-1' } as any)
    const wrapper = createWrapper()
    const { result } = renderHook(() => useUpdateOrganization(), { wrapper })

    await act(async () => {
      result.current.mutate({ id: 'org-1', data: { name: 'Renamed' } as any })
    })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(organizationsApi.update).toHaveBeenCalledWith('org-1', { name: 'Renamed' })
  })

  it('useDeleteOrganization calls delete and invalidates organizations', async () => {
    vi.mocked(organizationsApi.delete).mockResolvedValue(undefined)
    const wrapper = createWrapper()
    const { result } = renderHook(() => useDeleteOrganization(), { wrapper })

    await act(async () => {
      result.current.mutate('org-1')
    })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(organizationsApi.delete).toHaveBeenCalled()
    expect(vi.mocked(organizationsApi.delete).mock.calls[0][0]).toEqual('org-1')
  })

  it('useBusinessUnits is disabled when orgId is null', () => {
    const { result } = renderHook(() => useBusinessUnits(null), { wrapper: createWrapper() })
    expect(result.current.isFetching).toBe(false)
    expect(organizationsApi.listBUs).not.toHaveBeenCalled()
  })

  it('useBusinessUnits is enabled when orgId is provided', async () => {
    vi.mocked(organizationsApi.listBUs).mockResolvedValue([{ id: 'bu-1' }] as any)
    const { result } = renderHook(() => useBusinessUnits('org-1'), { wrapper: createWrapper() })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(organizationsApi.listBUs).toHaveBeenCalled()
    expect(vi.mocked(organizationsApi.listBUs).mock.calls[0][0]).toEqual('org-1')
  })

  it('useCreateBusinessUnit calls createBU and invalidates organizations', async () => {
    vi.mocked(organizationsApi.createBU).mockResolvedValue({ id: 'bu-2' } as any)
    const wrapper = createWrapper()
    const { result } = renderHook(() => useCreateBusinessUnit(), { wrapper })

    await act(async () => {
      result.current.mutate({ orgId: 'org-1', data: { name: 'BU' } as any })
    })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(organizationsApi.createBU).toHaveBeenCalledWith('org-1', { name: 'BU' })
  })

  it('useOrgMembers is disabled when orgId is null', () => {
    const { result } = renderHook(() => useOrgMembers(null), { wrapper: createWrapper() })
    expect(result.current.isFetching).toBe(false)
    expect(organizationsApi.listMembers).not.toHaveBeenCalled()
  })

  it('useOrgMembers is enabled when orgId is provided', async () => {
    vi.mocked(organizationsApi.listMembers).mockResolvedValue([{ user_id: 'u1' }] as any)
    const { result } = renderHook(() => useOrgMembers('org-1'), { wrapper: createWrapper() })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(organizationsApi.listMembers).toHaveBeenCalled()
    expect(vi.mocked(organizationsApi.listMembers).mock.calls[0][0]).toEqual('org-1')
  })
})

// ================================================================
// Audit
// ================================================================
describe('Audit hooks', () => {
  it('useAuditLogs calls auditApi.list with params and polls at 30000ms', async () => {
    vi.mocked(auditApi.list).mockResolvedValue([{ id: 'al-1' }] as any)
    const params = { actor_id: 'u1', limit: 50 }
    const { result } = renderHook(() => useAuditLogs(params), { wrapper: createWrapper() })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(auditApi.list).toHaveBeenCalled()
    expect(vi.mocked(auditApi.list).mock.calls[0][0]).toEqual(params)
  })
})

// ================================================================
// DLP
// ================================================================
describe('DLP hooks', () => {
  it('useContentDetectors calls dlpApi.listDetectors', async () => {
    const data = [{ id: 'd1', name: 'SSN Detector' }]
    vi.mocked(dlpApi.listDetectors).mockResolvedValue(data as any)
    const { result } = renderHook(() => useContentDetectors(), { wrapper: createWrapper() })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(result.current.data).toEqual(data)
  })

  it('useCreateDetector calls createDetector and invalidates detectors', async () => {
    vi.mocked(dlpApi.createDetector).mockResolvedValue({ id: 'd2' } as any)
    const wrapper = createWrapper()
    const { result } = renderHook(() => useCreateDetector(), { wrapper })

    await act(async () => {
      result.current.mutate({ name: 'Email Detector' } as any)
    })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(dlpApi.createDetector).toHaveBeenCalled()
    expect(vi.mocked(dlpApi.createDetector).mock.calls[0][0]).toEqual({ name: 'Email Detector' })
  })

  it('useDeleteDetector calls deleteDetector and invalidates detectors', async () => {
    vi.mocked(dlpApi.deleteDetector).mockResolvedValue(undefined)
    const wrapper = createWrapper()
    const { result } = renderHook(() => useDeleteDetector(), { wrapper })

    await act(async () => {
      result.current.mutate('d1')
    })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(dlpApi.deleteDetector).toHaveBeenCalled()
    expect(vi.mocked(dlpApi.deleteDetector).mock.calls[0][0]).toEqual('d1')
  })
})

// ================================================================
// Prompts
// ================================================================
describe('Prompts hooks', () => {
  it('usePromptTemplates calls promptsApi.list with params', async () => {
    vi.mocked(promptsApi.list).mockResolvedValue([{ id: 'p1' }] as any)
    const params = { category: 'system' }
    const { result } = renderHook(() => usePromptTemplates(params), { wrapper: createWrapper() })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(promptsApi.list).toHaveBeenCalled()
    expect(vi.mocked(promptsApi.list).mock.calls[0][0]).toEqual(params)
  })

  it('usePromptTemplate is disabled when slug is null', () => {
    const { result } = renderHook(() => usePromptTemplate(null), { wrapper: createWrapper() })
    expect(result.current.isFetching).toBe(false)
    expect(promptsApi.get).not.toHaveBeenCalled()
  })

  it('usePromptTemplate is enabled when slug is provided', async () => {
    vi.mocked(promptsApi.get).mockResolvedValue({ id: 'p1', slug: 'greeting' } as any)
    const { result } = renderHook(() => usePromptTemplate('greeting'), { wrapper: createWrapper() })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(promptsApi.get).toHaveBeenCalled()
    expect(vi.mocked(promptsApi.get).mock.calls[0][0]).toEqual('greeting')
  })

  it('useCreatePromptTemplate calls create and invalidates prompts', async () => {
    vi.mocked(promptsApi.create).mockResolvedValue({ id: 'p2' } as any)
    const wrapper = createWrapper()
    const { result } = renderHook(() => useCreatePromptTemplate(), { wrapper })

    await act(async () => {
      result.current.mutate({ name: 'New Prompt' } as any)
    })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(promptsApi.create).toHaveBeenCalled()
    expect(vi.mocked(promptsApi.create).mock.calls[0][0]).toEqual({ name: 'New Prompt' })
  })

  it('useUpdatePromptTemplate calls update with id and data', async () => {
    vi.mocked(promptsApi.update).mockResolvedValue({ id: 'p1' } as any)
    const wrapper = createWrapper()
    const { result } = renderHook(() => useUpdatePromptTemplate(), { wrapper })

    await act(async () => {
      result.current.mutate({ id: 'p1', data: { name: 'Updated' } })
    })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(promptsApi.update).toHaveBeenCalledWith('p1', { name: 'Updated' })
  })

  it('useDeletePromptTemplate calls delete and invalidates prompts', async () => {
    vi.mocked(promptsApi.delete).mockResolvedValue(undefined)
    const wrapper = createWrapper()
    const { result } = renderHook(() => useDeletePromptTemplate(), { wrapper })

    await act(async () => {
      result.current.mutate('p1')
    })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(promptsApi.delete).toHaveBeenCalled()
    expect(vi.mocked(promptsApi.delete).mock.calls[0][0]).toEqual('p1')
  })

  it('usePromptApprovals calls promptsApi.listApprovals', async () => {
    vi.mocked(promptsApi.listApprovals).mockResolvedValue([{ id: 'pa1' }] as any)
    const { result } = renderHook(() => usePromptApprovals(), { wrapper: createWrapper() })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(promptsApi.listApprovals).toHaveBeenCalledOnce()
  })
})

// ================================================================
// Rate Limits
// ================================================================
describe('Rate Limits hooks', () => {
  it('useRateLimitPolicies calls rateLimitsApi.list', async () => {
    vi.mocked(rateLimitsApi.list).mockResolvedValue([{ id: 'rl1' }] as any)
    const { result } = renderHook(() => useRateLimitPolicies(), { wrapper: createWrapper() })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(result.current.data).toEqual([{ id: 'rl1' }])
  })

  it('useCreateRateLimitPolicy calls create and invalidates rate-limits', async () => {
    vi.mocked(rateLimitsApi.create).mockResolvedValue({ id: 'rl2' } as any)
    const wrapper = createWrapper()
    const { result } = renderHook(() => useCreateRateLimitPolicy(), { wrapper })

    await act(async () => {
      result.current.mutate({ name: 'policy-1' } as any)
    })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(rateLimitsApi.create).toHaveBeenCalled()
    expect(vi.mocked(rateLimitsApi.create).mock.calls[0][0]).toEqual({ name: 'policy-1' })
  })

  it('useUpdateRateLimitPolicy calls update with id and data', async () => {
    vi.mocked(rateLimitsApi.update).mockResolvedValue({ id: 'rl1' } as any)
    const wrapper = createWrapper()
    const { result } = renderHook(() => useUpdateRateLimitPolicy(), { wrapper })

    await act(async () => {
      result.current.mutate({ id: 'rl1', data: { name: 'updated' } })
    })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(rateLimitsApi.update).toHaveBeenCalledWith('rl1', { name: 'updated' })
  })

  it('useDeleteRateLimitPolicy calls delete and invalidates rate-limits', async () => {
    vi.mocked(rateLimitsApi.delete).mockResolvedValue(undefined)
    const wrapper = createWrapper()
    const { result } = renderHook(() => useDeleteRateLimitPolicy(), { wrapper })

    await act(async () => {
      result.current.mutate('rl1')
    })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(rateLimitsApi.delete).toHaveBeenCalled()
    expect(vi.mocked(rateLimitsApi.delete).mock.calls[0][0]).toEqual('rl1')
  })

  it('useRateLimitEvents calls events with params and polls at 15000ms', async () => {
    vi.mocked(rateLimitsApi.events).mockResolvedValue([])
    const params = { limit: 100 }
    const { result } = renderHook(() => useRateLimitEvents(params), { wrapper: createWrapper() })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(rateLimitsApi.events).toHaveBeenCalled()
    expect(vi.mocked(rateLimitsApi.events).mock.calls[0][0]).toEqual(params)
  })
})

// ================================================================
// Model Access
// ================================================================
describe('Model Access hooks', () => {
  it('useModelAccessTiers calls modelAccessApi.listTiers', async () => {
    vi.mocked(modelAccessApi.listTiers).mockResolvedValue([{ id: 'mat1' }] as any)
    const { result } = renderHook(() => useModelAccessTiers(), { wrapper: createWrapper() })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(result.current.data).toEqual([{ id: 'mat1' }])
  })

  it('useCreateModelAccessTier calls createTier and invalidates model-access-tiers', async () => {
    vi.mocked(modelAccessApi.createTier).mockResolvedValue({ id: 'mat2' } as any)
    const wrapper = createWrapper()
    const { result } = renderHook(() => useCreateModelAccessTier(), { wrapper })

    await act(async () => {
      result.current.mutate({ name: 'Gold' } as any)
    })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(modelAccessApi.createTier).toHaveBeenCalled()
    expect(vi.mocked(modelAccessApi.createTier).mock.calls[0][0]).toEqual({ name: 'Gold' })
  })

  it('useModelAccessRequests calls listRequests with params', async () => {
    vi.mocked(modelAccessApi.listRequests).mockResolvedValue([{ id: 'mar1' }] as any)
    const params = { status: 'pending' }
    const { result } = renderHook(() => useModelAccessRequests(params), { wrapper: createWrapper() })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(modelAccessApi.listRequests).toHaveBeenCalled()
    expect(vi.mocked(modelAccessApi.listRequests).mock.calls[0][0]).toEqual(params)
  })

  it('useCreateModelAccessRequest calls createRequest and invalidates model-access-requests', async () => {
    vi.mocked(modelAccessApi.createRequest).mockResolvedValue({ id: 'mar2' } as any)
    const wrapper = createWrapper()
    const { result } = renderHook(() => useCreateModelAccessRequest(), { wrapper })

    await act(async () => {
      result.current.mutate({ model_name: 'gpt-4' } as any)
    })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(modelAccessApi.createRequest).toHaveBeenCalled()
    expect(vi.mocked(modelAccessApi.createRequest).mock.calls[0][0]).toEqual({ model_name: 'gpt-4' })
  })

  it('useMyModelAccess calls modelAccessApi.myAccess', async () => {
    vi.mocked(modelAccessApi.myAccess).mockResolvedValue([{ id: 'mar1' }] as any)
    const { result } = renderHook(() => useMyModelAccess(), { wrapper: createWrapper() })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(modelAccessApi.myAccess).toHaveBeenCalledOnce()
  })
})

// ================================================================
// Chargeback
// ================================================================
describe('Chargeback hooks', () => {
  it('useCostAllocationRules calls chargebackApi.listRules', async () => {
    vi.mocked(chargebackApi.listRules).mockResolvedValue([{ id: 'car1' }] as any)
    const { result } = renderHook(() => useCostAllocationRules(), { wrapper: createWrapper() })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(result.current.data).toEqual([{ id: 'car1' }])
  })

  it('useCreateCostAllocationRule calls createRule and invalidates cost-allocation-rules', async () => {
    vi.mocked(chargebackApi.createRule).mockResolvedValue({ id: 'car2' } as any)
    const wrapper = createWrapper()
    const { result } = renderHook(() => useCreateCostAllocationRule(), { wrapper })

    await act(async () => {
      result.current.mutate({ name: 'rule-1' } as any)
    })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(chargebackApi.createRule).toHaveBeenCalled()
    expect(vi.mocked(chargebackApi.createRule).mock.calls[0][0]).toEqual({ name: 'rule-1' })
  })

  it('useDeleteCostAllocationRule calls deleteRule and invalidates cost-allocation-rules', async () => {
    vi.mocked(chargebackApi.deleteRule).mockResolvedValue(undefined)
    const wrapper = createWrapper()
    const { result } = renderHook(() => useDeleteCostAllocationRule(), { wrapper })

    await act(async () => {
      result.current.mutate('car1')
    })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(chargebackApi.deleteRule).toHaveBeenCalled()
    expect(vi.mocked(chargebackApi.deleteRule).mock.calls[0][0]).toEqual('car1')
  })

  it('useChargebackReports calls chargebackApi.listReports', async () => {
    vi.mocked(chargebackApi.listReports).mockResolvedValue([{ id: 'cr1' }] as any)
    const { result } = renderHook(() => useChargebackReports(), { wrapper: createWrapper() })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(chargebackApi.listReports).toHaveBeenCalledOnce()
  })

  it('useBudgetForecasts calls chargebackApi.getForecasts', async () => {
    vi.mocked(chargebackApi.getForecasts).mockResolvedValue([{ team_id: 't1' }] as any)
    const { result } = renderHook(() => useBudgetForecasts(), { wrapper: createWrapper() })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(chargebackApi.getForecasts).toHaveBeenCalledOnce()
  })
})

// ================================================================
// SLA
// ================================================================
describe('SLA hooks', () => {
  it('useSLADefinitions calls slaApi.listDefinitions', async () => {
    vi.mocked(slaApi.listDefinitions).mockResolvedValue([{ id: 'sla1' }] as any)
    const { result } = renderHook(() => useSLADefinitions(), { wrapper: createWrapper() })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(result.current.data).toEqual([{ id: 'sla1' }])
  })

  it('useCreateSLADefinition calls createDefinition and invalidates sla-definitions', async () => {
    vi.mocked(slaApi.createDefinition).mockResolvedValue({ id: 'sla2' } as any)
    const wrapper = createWrapper()
    const { result } = renderHook(() => useCreateSLADefinition(), { wrapper })

    await act(async () => {
      result.current.mutate({ name: 'Gold SLA' } as any)
    })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(slaApi.createDefinition).toHaveBeenCalled()
    expect(vi.mocked(slaApi.createDefinition).mock.calls[0][0]).toEqual({ name: 'Gold SLA' })
  })

  it('useProviderHealth calls getHealth and polls at 60000ms', async () => {
    vi.mocked(slaApi.getHealth).mockResolvedValue([{ provider: 'openai' }] as any)
    const { result } = renderHook(() => useProviderHealth(), { wrapper: createWrapper() })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(slaApi.getHealth).toHaveBeenCalledOnce()
  })

  it('useSLAViolations calls listViolations with params', async () => {
    vi.mocked(slaApi.listViolations).mockResolvedValue([{ id: 'v1' }] as any)
    const params = { resolved: false }
    const { result } = renderHook(() => useSLAViolations(params), { wrapper: createWrapper() })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(slaApi.listViolations).toHaveBeenCalled()
    expect(vi.mocked(slaApi.listViolations).mock.calls[0][0]).toEqual(params)
  })

  it('useActiveViolations calls activeViolations and polls at 30000ms', async () => {
    vi.mocked(slaApi.activeViolations).mockResolvedValue([{ id: 'v2' }] as any)
    const { result } = renderHook(() => useActiveViolations(), { wrapper: createWrapper() })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(slaApi.activeViolations).toHaveBeenCalledOnce()
  })

  it('useFailoverRules calls slaApi.listFailoverRules', async () => {
    vi.mocked(slaApi.listFailoverRules).mockResolvedValue([{ id: 'fr1' }] as any)
    const { result } = renderHook(() => useFailoverRules(), { wrapper: createWrapper() })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(result.current.data).toEqual([{ id: 'fr1' }])
  })

  it('useCreateFailoverRule calls createFailoverRule and invalidates failover-rules', async () => {
    vi.mocked(slaApi.createFailoverRule).mockResolvedValue({ id: 'fr2' } as any)
    const wrapper = createWrapper()
    const { result } = renderHook(() => useCreateFailoverRule(), { wrapper })

    await act(async () => {
      result.current.mutate({ name: 'failover-1' } as any)
    })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(slaApi.createFailoverRule).toHaveBeenCalled()
    expect(vi.mocked(slaApi.createFailoverRule).mock.calls[0][0]).toEqual({ name: 'failover-1' })
  })
})

// ================================================================
// A/B Tests
// ================================================================
describe('A/B Tests hooks', () => {
  it('useABTests calls abTestsApi.list', async () => {
    vi.mocked(abTestsApi.list).mockResolvedValue([{ id: 'ab1' }] as any)
    const { result } = renderHook(() => useABTests(), { wrapper: createWrapper() })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(result.current.data).toEqual([{ id: 'ab1' }])
  })

  it('useABTest is disabled when id is null', () => {
    const { result } = renderHook(() => useABTest(null), { wrapper: createWrapper() })
    expect(result.current.isFetching).toBe(false)
    expect(abTestsApi.get).not.toHaveBeenCalled()
  })

  it('useABTest is enabled when id is provided', async () => {
    vi.mocked(abTestsApi.get).mockResolvedValue({ id: 'ab1', name: 'test' } as any)
    const { result } = renderHook(() => useABTest('ab1'), { wrapper: createWrapper() })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(abTestsApi.get).toHaveBeenCalled()
    expect(vi.mocked(abTestsApi.get).mock.calls[0][0]).toEqual('ab1')
  })

  it('useCreateABTest calls create and invalidates ab-tests', async () => {
    vi.mocked(abTestsApi.create).mockResolvedValue({ id: 'ab2' } as any)
    const wrapper = createWrapper()
    const { result } = renderHook(() => useCreateABTest(), { wrapper })

    await act(async () => {
      result.current.mutate({ name: 'new-test' } as any)
    })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(abTestsApi.create).toHaveBeenCalled()
    expect(vi.mocked(abTestsApi.create).mock.calls[0][0]).toEqual({ name: 'new-test' })
  })

  it('useDeleteABTest calls delete and invalidates ab-tests', async () => {
    vi.mocked(abTestsApi.delete).mockResolvedValue(undefined)
    const wrapper = createWrapper()
    const { result } = renderHook(() => useDeleteABTest(), { wrapper })

    await act(async () => {
      result.current.mutate('ab1')
    })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(abTestsApi.delete).toHaveBeenCalled()
    expect(vi.mocked(abTestsApi.delete).mock.calls[0][0]).toEqual('ab1')
  })

  it('useStartABTest calls start and invalidates ab-tests', async () => {
    vi.mocked(abTestsApi.start).mockResolvedValue(undefined)
    const wrapper = createWrapper()
    const { result } = renderHook(() => useStartABTest(), { wrapper })

    await act(async () => {
      result.current.mutate('ab1')
    })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(abTestsApi.start).toHaveBeenCalled()
    expect(vi.mocked(abTestsApi.start).mock.calls[0][0]).toEqual('ab1')
  })

  it('useStopABTest calls stop and invalidates ab-tests', async () => {
    vi.mocked(abTestsApi.stop).mockResolvedValue(undefined)
    const wrapper = createWrapper()
    const { result } = renderHook(() => useStopABTest(), { wrapper })

    await act(async () => {
      result.current.mutate('ab1')
    })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(abTestsApi.stop).toHaveBeenCalled()
    expect(vi.mocked(abTestsApi.stop).mock.calls[0][0]).toEqual('ab1')
  })

  it('usePromoteABTest calls promote and invalidates ab-tests', async () => {
    vi.mocked(abTestsApi.promote).mockResolvedValue(undefined)
    const wrapper = createWrapper()
    const { result } = renderHook(() => usePromoteABTest(), { wrapper })

    await act(async () => {
      result.current.mutate('ab1')
    })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(abTestsApi.promote).toHaveBeenCalled()
    expect(vi.mocked(abTestsApi.promote).mock.calls[0][0]).toEqual('ab1')
  })

  it('useABTestSnapshots is disabled when testId is null', () => {
    const { result } = renderHook(() => useABTestSnapshots(null), { wrapper: createWrapper() })
    expect(result.current.isFetching).toBe(false)
    expect(abTestsApi.snapshots).not.toHaveBeenCalled()
  })

  it('useABTestSnapshots is enabled when testId is provided and polls at 30000ms', async () => {
    vi.mocked(abTestsApi.snapshots).mockResolvedValue([{ id: 'snap1' }] as any)
    const { result } = renderHook(() => useABTestSnapshots('ab1'), { wrapper: createWrapper() })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(abTestsApi.snapshots).toHaveBeenCalled()
    expect(vi.mocked(abTestsApi.snapshots).mock.calls[0][0]).toEqual('ab1')
  })
})

// ================================================================
// Cache
// ================================================================
describe('Cache hooks', () => {
  it('useCacheStats calls cacheApi.stats and polls at 30000ms', async () => {
    vi.mocked(cacheApi.stats).mockResolvedValue({ hit_rate: 0.85 } as any)
    const { result } = renderHook(() => useCacheStats(), { wrapper: createWrapper() })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(result.current.data).toEqual({ hit_rate: 0.85 })
  })

  it('useCacheEntries calls cacheApi.entries with params', async () => {
    vi.mocked(cacheApi.entries).mockResolvedValue([{ id: 'ce1' }] as any)
    const params = { limit: 10, offset: 0 }
    const { result } = renderHook(() => useCacheEntries(params), { wrapper: createWrapper() })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(cacheApi.entries).toHaveBeenCalled()
    expect(vi.mocked(cacheApi.entries).mock.calls[0][0]).toEqual(params)
  })

  it('useClearCache calls clear and invalidates cache-stats + cache-entries', async () => {
    vi.mocked(cacheApi.clear).mockResolvedValue(undefined)
    const wrapper = createWrapper()
    const invalidateSpy = vi.spyOn(queryClient, 'invalidateQueries')
    const { result } = renderHook(() => useClearCache(), { wrapper })

    await act(async () => {
      result.current.mutate()
    })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(cacheApi.clear).toHaveBeenCalledOnce()
    expect(invalidateSpy).toHaveBeenCalledTimes(2)
    expect(vi.mocked(invalidateSpy).mock.calls[0][0]).toEqual({ queryKey: ['cache-stats'] })
    expect(vi.mocked(invalidateSpy).mock.calls[1][0]).toEqual({ queryKey: ['cache-entries'] })
  })

  it('useDeleteCacheEntry calls deleteEntry and invalidates cache-stats + cache-entries', async () => {
    vi.mocked(cacheApi.deleteEntry).mockResolvedValue(undefined)
    const wrapper = createWrapper()
    const invalidateSpy = vi.spyOn(queryClient, 'invalidateQueries')
    const { result } = renderHook(() => useDeleteCacheEntry(), { wrapper })

    await act(async () => {
      result.current.mutate('ce1')
    })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(cacheApi.deleteEntry).toHaveBeenCalled()
    expect(vi.mocked(cacheApi.deleteEntry).mock.calls[0][0]).toEqual('ce1')
    expect(invalidateSpy).toHaveBeenCalledTimes(2)
    expect(vi.mocked(invalidateSpy).mock.calls[0][0]).toEqual({ queryKey: ['cache-stats'] })
    expect(vi.mocked(invalidateSpy).mock.calls[1][0]).toEqual({ queryKey: ['cache-entries'] })
  })
})

// ================================================================
// Events
// ================================================================
describe('Events hooks', () => {
  it('useEventSubscriptions calls eventsApi.listSubscriptions', async () => {
    vi.mocked(eventsApi.listSubscriptions).mockResolvedValue([{ id: 'es1' }] as any)
    const { result } = renderHook(() => useEventSubscriptions(), { wrapper: createWrapper() })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(result.current.data).toEqual([{ id: 'es1' }])
  })

  it('useCreateEventSubscription calls createSubscription and invalidates event-subscriptions', async () => {
    vi.mocked(eventsApi.createSubscription).mockResolvedValue({ id: 'es2' } as any)
    const wrapper = createWrapper()
    const { result } = renderHook(() => useCreateEventSubscription(), { wrapper })

    await act(async () => {
      result.current.mutate({ event_type: 'model.created' } as any)
    })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(eventsApi.createSubscription).toHaveBeenCalled()
    expect(vi.mocked(eventsApi.createSubscription).mock.calls[0][0]).toEqual({ event_type: 'model.created' })
  })

  it('useUpdateEventSubscription calls updateSubscription with id and data', async () => {
    vi.mocked(eventsApi.updateSubscription).mockResolvedValue({ id: 'es1' } as any)
    const wrapper = createWrapper()
    const { result } = renderHook(() => useUpdateEventSubscription(), { wrapper })

    await act(async () => {
      result.current.mutate({ id: 'es1', data: { name: 'updated-sub' } })
    })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(eventsApi.updateSubscription).toHaveBeenCalledWith('es1', { name: 'updated-sub' })
  })

  it('useDeleteEventSubscription calls deleteSubscription and invalidates event-subscriptions', async () => {
    vi.mocked(eventsApi.deleteSubscription).mockResolvedValue(undefined)
    const wrapper = createWrapper()
    const { result } = renderHook(() => useDeleteEventSubscription(), { wrapper })

    await act(async () => {
      result.current.mutate('es1')
    })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(eventsApi.deleteSubscription).toHaveBeenCalled()
    expect(vi.mocked(eventsApi.deleteSubscription).mock.calls[0][0]).toEqual('es1')
  })

  it('useEventLog calls listEvents with params and polls at 15000ms', async () => {
    vi.mocked(eventsApi.listEvents).mockResolvedValue([{ id: 'el1' }] as any)
    const params = { event_type: 'model.created', limit: 50 }
    const { result } = renderHook(() => useEventLog(params), { wrapper: createWrapper() })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(eventsApi.listEvents).toHaveBeenCalled()
    expect(vi.mocked(eventsApi.listEvents).mock.calls[0][0]).toEqual(params)
  })

  it('useSendTestEvent calls sendTestEvent and invalidates event-log', async () => {
    vi.mocked(eventsApi.sendTestEvent).mockResolvedValue(undefined)
    const wrapper = createWrapper()
    const { result } = renderHook(() => useSendTestEvent(), { wrapper })

    const payload = { event_type: 'test', payload: { foo: 'bar' } }
    await act(async () => {
      result.current.mutate(payload)
    })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(eventsApi.sendTestEvent).toHaveBeenCalled()
    expect(vi.mocked(eventsApi.sendTestEvent).mock.calls[0][0]).toEqual(payload)
  })
})

// ================================================================
// Playground
// ================================================================
describe('Playground hooks', () => {
  it('usePlaygroundSessions calls playgroundApi.listSessions with params', async () => {
    vi.mocked(playgroundApi.listSessions).mockResolvedValue([{ id: 'ps1' }] as any)
    const params = { is_public: true }
    const { result } = renderHook(() => usePlaygroundSessions(params), { wrapper: createWrapper() })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(playgroundApi.listSessions).toHaveBeenCalled()
    expect(vi.mocked(playgroundApi.listSessions).mock.calls[0][0]).toEqual(params)
  })

  it('useCreatePlaygroundSession calls createSession and invalidates playground-sessions', async () => {
    vi.mocked(playgroundApi.createSession).mockResolvedValue({ id: 'ps2' } as any)
    const wrapper = createWrapper()
    const { result } = renderHook(() => useCreatePlaygroundSession(), { wrapper })

    await act(async () => {
      result.current.mutate({ name: 'session-1' } as any)
    })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(playgroundApi.createSession).toHaveBeenCalled()
    expect(vi.mocked(playgroundApi.createSession).mock.calls[0][0]).toEqual({ name: 'session-1' })
  })

  it('useDeletePlaygroundSession calls deleteSession and invalidates playground-sessions', async () => {
    vi.mocked(playgroundApi.deleteSession).mockResolvedValue(undefined)
    const wrapper = createWrapper()
    const { result } = renderHook(() => useDeletePlaygroundSession(), { wrapper })

    await act(async () => {
      result.current.mutate('ps1')
    })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(playgroundApi.deleteSession).toHaveBeenCalled()
    expect(vi.mocked(playgroundApi.deleteSession).mock.calls[0][0]).toEqual('ps1')
  })
})

// ================================================================
// Deprecations
// ================================================================
describe('Deprecations hooks', () => {
  it('useModelDeprecations calls deprecationsApi.list', async () => {
    vi.mocked(deprecationsApi.list).mockResolvedValue([{ id: 'md1' }] as any)
    const { result } = renderHook(() => useModelDeprecations(), { wrapper: createWrapper() })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(result.current.data).toEqual([{ id: 'md1' }])
  })

  it('useCreateModelDeprecation calls create and invalidates model-deprecations', async () => {
    vi.mocked(deprecationsApi.create).mockResolvedValue({ id: 'md2' } as any)
    const wrapper = createWrapper()
    const { result } = renderHook(() => useCreateModelDeprecation(), { wrapper })

    await act(async () => {
      result.current.mutate({ model_name: 'gpt-3.5' } as any)
    })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(deprecationsApi.create).toHaveBeenCalled()
    expect(vi.mocked(deprecationsApi.create).mock.calls[0][0]).toEqual({ model_name: 'gpt-3.5' })
  })

  it('useUpdateModelDeprecation calls update with id and data', async () => {
    vi.mocked(deprecationsApi.update).mockResolvedValue({ id: 'md1' } as any)
    const wrapper = createWrapper()
    const { result } = renderHook(() => useUpdateModelDeprecation(), { wrapper })

    await act(async () => {
      result.current.mutate({ id: 'md1', data: { replacement_model: 'gpt-4' } })
    })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(deprecationsApi.update).toHaveBeenCalledWith('md1', { replacement_model: 'gpt-4' })
  })

  it('useDeleteModelDeprecation calls delete and invalidates model-deprecations', async () => {
    vi.mocked(deprecationsApi.delete).mockResolvedValue(undefined)
    const wrapper = createWrapper()
    const { result } = renderHook(() => useDeleteModelDeprecation(), { wrapper })

    await act(async () => {
      result.current.mutate('md1')
    })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(deprecationsApi.delete).toHaveBeenCalled()
    expect(vi.mocked(deprecationsApi.delete).mock.calls[0][0]).toEqual('md1')
  })
})
