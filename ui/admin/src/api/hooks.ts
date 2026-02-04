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

// Models hooks
export function useModels() {
  return useQuery({
    queryKey: ['models'],
    queryFn: modelsApi.list,
  })
}

export function useUpdateModel() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ modelId, data }: { modelId: string; data: any }) =>
      modelsApi.update(modelId, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['models'] })
    },
  })
}

// Routing Policies hooks
export function useRoutingPolicies() {
  return useQuery({
    queryKey: ['routing-policies'],
    queryFn: policiesApi.list,
  })
}

export function useCreatePolicy() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: policiesApi.create,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['routing-policies'] })
    },
  })
}

export function useDeletePolicy() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: policiesApi.delete,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['routing-policies'] })
    },
  })
}

// Budgets hooks
export function useBudgets() {
  return useQuery({
    queryKey: ['budgets'],
    queryFn: budgetsApi.list,
  })
}

export function useCreateBudget() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: budgetsApi.create,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['budgets'] })
    },
  })
}

export function useUpdateBudget() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: any }) =>
      budgetsApi.update(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['budgets'] })
    },
  })
}

// Teams hooks
export function useTeams() {
  return useQuery({
    queryKey: ['teams'],
    queryFn: teamsApi.list,
  })
}

export function useCreateTeam() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: teamsApi.create,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['teams'] })
    },
  })
}

export function useAddTeamMember() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ teamId, data }: { teamId: string; data: any }) =>
      teamsApi.addMember(teamId, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['teams'] })
    },
  })
}

// MCP Servers hooks
export function useMCPServers() {
  return useQuery({
    queryKey: ['mcp-servers'],
    queryFn: mcpServersApi.list,
  })
}

export function useCreateMCPServer() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: mcpServersApi.create,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['mcp-servers'] })
    },
  })
}

// Workflows hooks
export function useWorkflows() {
  return useQuery({
    queryKey: ['workflows'],
    queryFn: workflowsApi.list,
  })
}

// Metrics hooks
export function useRealtimeMetrics() {
  return useQuery({
    queryKey: ['metrics', 'realtime'],
    queryFn: metricsApi.realtime,
    refetchInterval: 30000, // Refresh every 30 seconds
  })
}

// Settings hooks
export function useSettings() {
  return useQuery({
    queryKey: ['settings'],
    queryFn: settingsApi.get,
  })
}

export function useUpdateSettings() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: settingsApi.update,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['settings'] })
    },
  })
}
