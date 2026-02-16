import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  modelsApi,
  policiesApi,
  budgetsApi,
  teamsApi,
  mcpServersApi,
  workflowsApi,
  metricsApi,
  settingsApi,
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
  WorkflowSummary,
  RealtimeMetrics,
  PlatformSettings,
  RoutingPolicy,
  RoutingPolicyCreate,
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

// Workflows hooks
export function useWorkflows() {
  return useQuery<WorkflowSummary[]>({
    queryKey: ['workflows'],
    queryFn: workflowsApi.list,
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
