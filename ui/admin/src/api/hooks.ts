import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  modelsApi,
  policiesApi,
  budgetsApi,
  teamsApi,
  mcpServersApi,
  keysApi,
  workflowsApi,
  metricsApi,
  settingsApi,
  guardrailsApi,
} from './client'
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
  RoutingPolicy,
  RoutingPolicyCreate,
  GuardrailConfig,
  GuardrailConfigCreate,
  GuardrailConfigUpdate,
  GuardrailEvent,
  GuardrailScanRequest,
  GuardrailScanResponse,
} from '../types'

// Models hooks
export function useModels() {
  return useQuery<ModelConfig[]>({
    queryKey: ['models'],
    queryFn: modelsApi.list,
  })
}

export function useUpdateModel() {
  const queryClient = useQueryClient()
  return useMutation<ModelConfig, Error, { modelId: string; data: ModelUpdate }>({
    mutationFn: ({ modelId, data }) => modelsApi.update(modelId, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['models'] })
    },
  })
}

// Routing Policies hooks
export function useRoutingPolicies() {
  return useQuery<RoutingPolicy[]>({
    queryKey: ['routing-policies'],
    queryFn: policiesApi.list,
  })
}

export function useCreatePolicy() {
  const queryClient = useQueryClient()
  return useMutation<RoutingPolicy, Error, RoutingPolicyCreate>({
    mutationFn: policiesApi.create,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['routing-policies'] })
    },
  })
}

export function useDeletePolicy() {
  const queryClient = useQueryClient()
  return useMutation<void, Error, string>({
    mutationFn: policiesApi.delete,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['routing-policies'] })
    },
  })
}

// Budgets hooks
export function useBudgets() {
  return useQuery<Budget[]>({
    queryKey: ['budgets'],
    queryFn: budgetsApi.list,
  })
}

export function useCreateBudget() {
  const queryClient = useQueryClient()
  return useMutation<Budget, Error, BudgetCreate>({
    mutationFn: budgetsApi.create,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['budgets'] })
    },
  })
}

export function useUpdateBudget() {
  const queryClient = useQueryClient()
  return useMutation<Budget, Error, { id: string; data: BudgetUpdate }>({
    mutationFn: ({ id, data }) => budgetsApi.update(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['budgets'] })
    },
  })
}

// Teams hooks
export function useTeams() {
  return useQuery<Team[]>({
    queryKey: ['teams'],
    queryFn: teamsApi.list,
  })
}

export function useCreateTeam() {
  const queryClient = useQueryClient()
  return useMutation<Team, Error, TeamCreate>({
    mutationFn: teamsApi.create,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['teams'] })
    },
  })
}

export function useAddTeamMember() {
  const queryClient = useQueryClient()
  return useMutation<Team, Error, { teamId: string; data: TeamMemberAdd }>({
    mutationFn: ({ teamId, data }) => teamsApi.addMember(teamId, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['teams'] })
    },
  })
}

// MCP Servers hooks
export function useMCPServers() {
  return useQuery<MCPServerConfig[]>({
    queryKey: ['mcp-servers'],
    queryFn: mcpServersApi.list,
  })
}

export function useCreateMCPServer() {
  const queryClient = useQueryClient()
  return useMutation<MCPServerConfig, Error, MCPServerCreate>({
    mutationFn: mcpServersApi.create,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['mcp-servers'] })
    },
  })
}

export function useUpdateMCPServer() {
  const queryClient = useQueryClient()
  return useMutation<MCPServerConfig, Error, { id: string; data: MCPServerUpdate }>({
    mutationFn: ({ id, data }) => mcpServersApi.update(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['mcp-servers'] })
    },
  })
}

export function useDeleteMCPServer() {
  const queryClient = useQueryClient()
  return useMutation<void, Error, string>({
    mutationFn: mcpServersApi.delete,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['mcp-servers'] })
    },
  })
}

export function useTestMCPServer() {
  return useMutation<MCPTestResult, Error, string>({
    mutationFn: mcpServersApi.test,
  })
}

export function useSyncMCPToGateway() {
  const queryClient = useQueryClient()
  return useMutation<GatewaySyncResult, Error>({
    mutationFn: mcpServersApi.sync,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['mcp-servers'] })
    },
  })
}

export function useGatewayConfigPreview() {
  return useQuery<GatewayConfigPreview>({
    queryKey: ['mcp-servers', 'gateway-preview'],
    queryFn: mcpServersApi.previewConfig,
    enabled: false, // only fetch on demand
  })
}

// API Keys hooks
export function useAPIKeys() {
  return useQuery<unknown>({
    queryKey: ['api-keys'],
    queryFn: keysApi.list,
  })
}

export function useGenerateKey() {
  const queryClient = useQueryClient()
  return useMutation<KeyGenerateResponse, Error, KeyGenerateRequest>({
    mutationFn: keysApi.generate,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['api-keys'] })
    },
  })
}

export function useUpdateKey() {
  const queryClient = useQueryClient()
  return useMutation<unknown, Error, KeyUpdateRequest>({
    mutationFn: keysApi.update,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['api-keys'] })
    },
  })
}

export function useDeleteKey() {
  const queryClient = useQueryClient()
  return useMutation<unknown, Error, KeyDeleteRequest>({
    mutationFn: keysApi.delete,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['api-keys'] })
    },
  })
}

// Workflows hooks
export function useWorkflows() {
  return useQuery<WorkflowSummary[]>({
    queryKey: ['workflows'],
    queryFn: workflowsApi.list,
  })
}

export function useCreateWorkflow() {
  const queryClient = useQueryClient()
  return useMutation<WorkflowSummary, Error, WorkflowCreate>({
    mutationFn: workflowsApi.create,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['workflows'] })
    },
  })
}

export function useWorkflowExecutions() {
  return useQuery<WorkflowExecutionSummary[]>({
    queryKey: ['workflow-executions'],
    queryFn: workflowsApi.listExecutions,
    refetchInterval: 10000,
  })
}

export function useWorkflowExecution(executionId: string | null) {
  return useQuery<WorkflowExecutionDetail>({
    queryKey: ['workflow-executions', executionId],
    queryFn: () => workflowsApi.getExecution(executionId!),
    enabled: !!executionId,
    refetchInterval: (query) => {
      const status = query.state.data?.status
      return status === 'running' || status === 'pending' ? 2000 : false
    },
  })
}

export function useExecuteWorkflow() {
  const queryClient = useQueryClient()
  return useMutation<unknown, Error, WorkflowExecuteRequest>({
    mutationFn: workflowsApi.execute,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['workflow-executions'] })
    },
  })
}

// Metrics hooks
export function useRealtimeMetrics() {
  return useQuery<RealtimeMetrics>({
    queryKey: ['metrics', 'realtime'],
    queryFn: metricsApi.realtime,
    refetchInterval: 30000,
  })
}

// Guardrails hooks
export function useGuardrails() {
  return useQuery<GuardrailConfig[]>({
    queryKey: ['guardrails'],
    queryFn: guardrailsApi.list,
  })
}

export function useCreateGuardrail() {
  const queryClient = useQueryClient()
  return useMutation<GuardrailConfig, Error, GuardrailConfigCreate>({
    mutationFn: guardrailsApi.create,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['guardrails'] })
    },
  })
}

export function useUpdateGuardrail() {
  const queryClient = useQueryClient()
  return useMutation<GuardrailConfig, Error, { id: string; data: GuardrailConfigUpdate }>({
    mutationFn: ({ id, data }) => guardrailsApi.update(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['guardrails'] })
    },
  })
}

export function useDeleteGuardrail() {
  const queryClient = useQueryClient()
  return useMutation<void, Error, string>({
    mutationFn: guardrailsApi.delete,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['guardrails'] })
    },
  })
}

export function useGuardrailEvents(params?: { team_id?: string; event_type?: string }) {
  return useQuery<GuardrailEvent[]>({
    queryKey: ['guardrail-events', params],
    queryFn: () => guardrailsApi.events(params),
    refetchInterval: 30000,
  })
}

export function useScanText() {
  return useMutation<GuardrailScanResponse, Error, GuardrailScanRequest>({
    mutationFn: guardrailsApi.scan,
  })
}

// Settings hooks
export function useSettings() {
  return useQuery<PlatformSettings>({
    queryKey: ['settings'],
    queryFn: settingsApi.get,
  })
}

export function useUpdateSettings() {
  const queryClient = useQueryClient()
  return useMutation<PlatformSettings, Error, PlatformSettings>({
    mutationFn: settingsApi.update,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['settings'] })
    },
  })
}
