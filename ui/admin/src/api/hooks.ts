import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  mcpServersApi,
  agentsApi,
  workflowsApi,
  reportsApi,
  settingsApi,
  guardrailsApi,
  modelsApi,
  keysApi,
  teamsApi,
  budgetsApi,
} from './client'
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

// A2A Agents hooks
export function useAgents() {
  return useQuery<A2AAgentConfig[]>({
    queryKey: ['agents'],
    queryFn: agentsApi.list,
  })
}

export function useCreateAgent() {
  const queryClient = useQueryClient()
  return useMutation<A2AAgentConfig, Error, A2AAgentCreate>({
    mutationFn: agentsApi.create,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['agents'] })
    },
  })
}

export function useUpdateAgent() {
  const queryClient = useQueryClient()
  return useMutation<A2AAgentConfig, Error, { id: string; data: A2AAgentUpdate }>({
    mutationFn: ({ id, data }) => agentsApi.update(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['agents'] })
    },
  })
}

export function useDeleteAgent() {
  const queryClient = useQueryClient()
  return useMutation<void, Error, string>({
    mutationFn: agentsApi.delete,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['agents'] })
    },
  })
}

export function useTestAgent() {
  return useMutation<A2ATestResult, Error, string>({
    mutationFn: agentsApi.test,
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

// Reports hooks
export function useReportsSummary() {
  return useQuery<ReportsSummary>({
    queryKey: ['reports', 'summary'],
    queryFn: reportsApi.summary,
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
      queryClient.invalidateQueries({ queryKey: ['guardrail-assignments'] })
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

export function useGuardrailAssignments() {
  return useQuery<GuardrailAssignment[]>({
    queryKey: ['guardrail-assignments'],
    queryFn: guardrailsApi.assignments,
  })
}

export function useAssignGuardrail() {
  const queryClient = useQueryClient()
  return useMutation<void, Error, { configId: string; teamId: string; priority?: number }>({
    mutationFn: ({ configId, teamId, priority }) => guardrailsApi.assignToTeam(configId, teamId, priority),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['guardrail-assignments'] })
    },
  })
}

export function useUnassignGuardrail() {
  const queryClient = useQueryClient()
  return useMutation<void, Error, { configId: string; teamId: string }>({
    mutationFn: ({ configId, teamId }) => guardrailsApi.unassignFromTeam(configId, teamId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['guardrail-assignments'] })
    },
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

// Models hooks
export function useModels() {
  return useQuery<{ data: ModelInfo[] }>({
    queryKey: ['models'],
    queryFn: modelsApi.list,
  })
}

export function useCreateModel() {
  const queryClient = useQueryClient()
  return useMutation<unknown, Error, ModelCreateRequest>({
    mutationFn: modelsApi.create,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['models'] })
    },
  })
}

export function useDeleteModel() {
  const queryClient = useQueryClient()
  return useMutation<void, Error, string>({
    mutationFn: modelsApi.delete,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['models'] })
    },
  })
}

// API Keys hooks
export function useAPIKeys() {
  return useQuery<KeyInfo[]>({
    queryKey: ['keys'],
    queryFn: keysApi.list,
  })
}

export function useGenerateKey() {
  const queryClient = useQueryClient()
  return useMutation<KeyGenerateResponse, Error, KeyGenerateRequest>({
    mutationFn: keysApi.generate,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['keys'] })
    },
  })
}

export function useDeleteKey() {
  const queryClient = useQueryClient()
  return useMutation<void, Error, string[]>({
    mutationFn: keysApi.delete,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['keys'] })
    },
  })
}

// Teams hooks
export function useTeams() {
  return useQuery<TeamInfo[]>({
    queryKey: ['teams'],
    queryFn: teamsApi.list,
  })
}

export function useCreateTeam() {
  const queryClient = useQueryClient()
  return useMutation<TeamInfo, Error, TeamCreateRequest>({
    mutationFn: teamsApi.create,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['teams'] })
    },
  })
}

export function useUpdateTeam() {
  const queryClient = useQueryClient()
  return useMutation<TeamInfo, Error, TeamUpdateRequest>({
    mutationFn: teamsApi.update,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['teams'] })
    },
  })
}

export function useDeleteTeam() {
  const queryClient = useQueryClient()
  return useMutation<void, Error, string[]>({
    mutationFn: teamsApi.delete,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['teams'] })
    },
  })
}

export function useAddTeamMember() {
  const queryClient = useQueryClient()
  return useMutation<unknown, Error, { teamId: string; member: { role: string; user_id: string } }>({
    mutationFn: ({ teamId, member }) => teamsApi.addMember(teamId, member),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['teams'] })
    },
  })
}

export function useDeleteTeamMember() {
  const queryClient = useQueryClient()
  return useMutation<void, Error, { teamId: string; userId: string }>({
    mutationFn: ({ teamId, userId }) => teamsApi.deleteMember(teamId, userId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['teams'] })
    },
  })
}

// Budgets hooks
export function useBudgets() {
  return useQuery<BudgetInfo[]>({
    queryKey: ['budgets'],
    queryFn: budgetsApi.list,
  })
}

export function useCreateBudget() {
  const queryClient = useQueryClient()
  return useMutation<BudgetInfo, Error, BudgetCreateRequest>({
    mutationFn: budgetsApi.create,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['budgets'] })
    },
  })
}

export function useUpdateBudget() {
  const queryClient = useQueryClient()
  return useMutation<BudgetInfo, Error, BudgetUpdateRequest>({
    mutationFn: budgetsApi.update,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['budgets'] })
    },
  })
}

export function useDeleteBudget() {
  const queryClient = useQueryClient()
  return useMutation<void, Error, string>({
    mutationFn: budgetsApi.delete,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['budgets'] })
    },
  })
}
