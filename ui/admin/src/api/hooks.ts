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
  routingApi,
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
  Organization,
  OrganizationCreate,
  OrganizationUpdate,
  BusinessUnit,
  BusinessUnitCreate,
  OrgMembership,
  AuditLogEntry,
  ContentDetector,
  ContentDetectorCreate,
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

// Organizations hooks
export function useOrganizations() {
  return useQuery<Organization[]>({
    queryKey: ['organizations'],
    queryFn: organizationsApi.list,
  })
}

export function useOrganization(id: string | null) {
  return useQuery<Organization>({
    queryKey: ['organizations', id],
    queryFn: () => organizationsApi.get(id!),
    enabled: !!id,
  })
}

export function useCreateOrganization() {
  const queryClient = useQueryClient()
  return useMutation<Organization, Error, OrganizationCreate>({
    mutationFn: organizationsApi.create,
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ['organizations'] }) },
  })
}

export function useUpdateOrganization() {
  const queryClient = useQueryClient()
  return useMutation<Organization, Error, { id: string; data: OrganizationUpdate }>({
    mutationFn: ({ id, data }) => organizationsApi.update(id, data),
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ['organizations'] }) },
  })
}

export function useDeleteOrganization() {
  const queryClient = useQueryClient()
  return useMutation<void, Error, string>({
    mutationFn: organizationsApi.delete,
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ['organizations'] }) },
  })
}

export function useBusinessUnits(orgId: string | null) {
  return useQuery<BusinessUnit[]>({
    queryKey: ['organizations', orgId, 'business-units'],
    queryFn: () => organizationsApi.listBUs(orgId!),
    enabled: !!orgId,
  })
}

export function useCreateBusinessUnit() {
  const queryClient = useQueryClient()
  return useMutation<BusinessUnit, Error, { orgId: string; data: BusinessUnitCreate }>({
    mutationFn: ({ orgId, data }) => organizationsApi.createBU(orgId, data),
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ['organizations'] }) },
  })
}

export function useOrgMembers(orgId: string | null) {
  return useQuery<OrgMembership[]>({
    queryKey: ['organizations', orgId, 'members'],
    queryFn: () => organizationsApi.listMembers(orgId!),
    enabled: !!orgId,
  })
}

// Audit hooks
export function useAuditLogs(params?: { actor_id?: string; resource_type?: string; action?: string; limit?: number; offset?: number }) {
  return useQuery<AuditLogEntry[]>({
    queryKey: ['audit-logs', params],
    queryFn: () => auditApi.list(params),
    refetchInterval: 30000,
  })
}

// DLP hooks
export function useContentDetectors() {
  return useQuery<ContentDetector[]>({
    queryKey: ['detectors'],
    queryFn: dlpApi.listDetectors,
  })
}

export function useCreateDetector() {
  const queryClient = useQueryClient()
  return useMutation<ContentDetector, Error, ContentDetectorCreate>({
    mutationFn: dlpApi.createDetector,
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ['detectors'] }) },
  })
}

export function useDeleteDetector() {
  const queryClient = useQueryClient()
  return useMutation<void, Error, string>({
    mutationFn: dlpApi.deleteDetector,
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ['detectors'] }) },
  })
}

// Prompt hooks
export function usePromptTemplates(params?: { category?: string; status?: string }) {
  return useQuery<PromptTemplate[]>({
    queryKey: ['prompts', params],
    queryFn: () => promptsApi.list(params),
  })
}

export function usePromptTemplate(slug: string | null) {
  return useQuery<PromptTemplate>({
    queryKey: ['prompts', slug],
    queryFn: () => promptsApi.get(slug!),
    enabled: !!slug,
  })
}

export function useCreatePromptTemplate() {
  const queryClient = useQueryClient()
  return useMutation<PromptTemplate, Error, PromptTemplateCreate>({
    mutationFn: promptsApi.create,
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ['prompts'] }) },
  })
}

export function useUpdatePromptTemplate() {
  const queryClient = useQueryClient()
  return useMutation<PromptTemplate, Error, { id: string; data: Partial<PromptTemplateCreate> }>({
    mutationFn: ({ id, data }) => promptsApi.update(id, data),
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ['prompts'] }) },
  })
}

export function useDeletePromptTemplate() {
  const queryClient = useQueryClient()
  return useMutation<void, Error, string>({
    mutationFn: promptsApi.delete,
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ['prompts'] }) },
  })
}

export function usePromptApprovals() {
  return useQuery<PromptApproval[]>({
    queryKey: ['prompt-approvals'],
    queryFn: promptsApi.listApprovals,
  })
}

// Rate limit hooks
export function useRateLimitPolicies() {
  return useQuery<RateLimitPolicy[]>({
    queryKey: ['rate-limits'],
    queryFn: rateLimitsApi.list,
  })
}

export function useCreateRateLimitPolicy() {
  const queryClient = useQueryClient()
  return useMutation<RateLimitPolicy, Error, RateLimitPolicyCreate>({
    mutationFn: rateLimitsApi.create,
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ['rate-limits'] }) },
  })
}

export function useUpdateRateLimitPolicy() {
  const queryClient = useQueryClient()
  return useMutation<RateLimitPolicy, Error, { id: string; data: Partial<RateLimitPolicyCreate> }>({
    mutationFn: ({ id, data }) => rateLimitsApi.update(id, data),
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ['rate-limits'] }) },
  })
}

export function useDeleteRateLimitPolicy() {
  const queryClient = useQueryClient()
  return useMutation<void, Error, string>({
    mutationFn: rateLimitsApi.delete,
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ['rate-limits'] }) },
  })
}

export function useRateLimitEvents(params?: { limit?: number }) {
  return useQuery<RateLimitEvent[]>({
    queryKey: ['rate-limit-events', params],
    queryFn: () => rateLimitsApi.events(params),
    refetchInterval: 15000,
  })
}

// Model access hooks
export function useModelAccessTiers() {
  return useQuery<ModelAccessTier[]>({
    queryKey: ['model-access-tiers'],
    queryFn: modelAccessApi.listTiers,
  })
}

export function useCreateModelAccessTier() {
  const queryClient = useQueryClient()
  return useMutation<ModelAccessTier, Error, ModelAccessTierCreate>({
    mutationFn: modelAccessApi.createTier,
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ['model-access-tiers'] }) },
  })
}

export function useModelAccessRequests(params?: { status?: string }) {
  return useQuery<ModelAccessRequest[]>({
    queryKey: ['model-access-requests', params],
    queryFn: () => modelAccessApi.listRequests(params),
  })
}

export function useCreateModelAccessRequest() {
  const queryClient = useQueryClient()
  return useMutation<ModelAccessRequest, Error, ModelAccessRequestCreate>({
    mutationFn: modelAccessApi.createRequest,
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ['model-access-requests'] }) },
  })
}

export function useMyModelAccess() {
  return useQuery<ModelAccessRequest[]>({
    queryKey: ['model-access-my'],
    queryFn: modelAccessApi.myAccess,
  })
}

// Chargeback hooks
export function useCostAllocationRules() {
  return useQuery<CostAllocationRule[]>({
    queryKey: ['cost-allocation-rules'],
    queryFn: chargebackApi.listRules,
  })
}

export function useCreateCostAllocationRule() {
  const queryClient = useQueryClient()
  return useMutation<CostAllocationRule, Error, CostAllocationRuleCreate>({
    mutationFn: chargebackApi.createRule,
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ['cost-allocation-rules'] }) },
  })
}

export function useDeleteCostAllocationRule() {
  const queryClient = useQueryClient()
  return useMutation<void, Error, string>({
    mutationFn: chargebackApi.deleteRule,
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ['cost-allocation-rules'] }) },
  })
}

export function useChargebackReports() {
  return useQuery<ChargebackReport[]>({
    queryKey: ['chargeback-reports'],
    queryFn: chargebackApi.listReports,
  })
}

export function useBudgetForecasts() {
  return useQuery<BudgetForecast[]>({
    queryKey: ['budget-forecasts'],
    queryFn: chargebackApi.getForecasts,
  })
}

// SLA hooks
export function useSLADefinitions() {
  return useQuery<SLADefinition[]>({
    queryKey: ['sla-definitions'],
    queryFn: slaApi.listDefinitions,
  })
}

export function useCreateSLADefinition() {
  const queryClient = useQueryClient()
  return useMutation<SLADefinition, Error, SLADefinitionCreate>({
    mutationFn: slaApi.createDefinition,
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ['sla-definitions'] }) },
  })
}

export function useProviderHealth() {
  return useQuery<ProviderHealthMetric[]>({
    queryKey: ['sla-health'],
    queryFn: slaApi.getHealth,
    refetchInterval: 60000,
  })
}

export function useSLAViolations(params?: { resolved?: boolean }) {
  return useQuery<SLAViolation[]>({
    queryKey: ['sla-violations', params],
    queryFn: () => slaApi.listViolations(params),
  })
}

export function useActiveViolations() {
  return useQuery<SLAViolation[]>({
    queryKey: ['sla-violations-active'],
    queryFn: slaApi.activeViolations,
    refetchInterval: 30000,
  })
}

export function useFailoverRules() {
  return useQuery<FailoverRule[]>({
    queryKey: ['failover-rules'],
    queryFn: slaApi.listFailoverRules,
  })
}

export function useCreateFailoverRule() {
  const queryClient = useQueryClient()
  return useMutation<FailoverRule, Error, FailoverRuleCreate>({
    mutationFn: slaApi.createFailoverRule,
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ['failover-rules'] }) },
  })
}

// A/B Tests hooks
export function useABTests() {
  return useQuery<ABTest[]>({
    queryKey: ['ab-tests'],
    queryFn: abTestsApi.list,
  })
}

export function useABTest(id: string | null) {
  return useQuery<ABTest & { latest_snapshot?: ABTestSnapshot }>({
    queryKey: ['ab-tests', id],
    queryFn: () => abTestsApi.get(id!),
    enabled: !!id,
  })
}

export function useCreateABTest() {
  const queryClient = useQueryClient()
  return useMutation<ABTest, Error, ABTestCreate>({
    mutationFn: abTestsApi.create,
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ['ab-tests'] }) },
  })
}

export function useDeleteABTest() {
  const queryClient = useQueryClient()
  return useMutation<void, Error, string>({
    mutationFn: abTestsApi.delete,
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ['ab-tests'] }) },
  })
}

export function useStartABTest() {
  const queryClient = useQueryClient()
  return useMutation<void, Error, string>({
    mutationFn: abTestsApi.start,
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ['ab-tests'] }) },
  })
}

export function useStopABTest() {
  const queryClient = useQueryClient()
  return useMutation<void, Error, string>({
    mutationFn: abTestsApi.stop,
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ['ab-tests'] }) },
  })
}

export function usePromoteABTest() {
  const queryClient = useQueryClient()
  return useMutation<void, Error, string>({
    mutationFn: abTestsApi.promote,
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ['ab-tests'] }) },
  })
}

export function useABTestSnapshots(testId: string | null) {
  return useQuery<ABTestSnapshot[]>({
    queryKey: ['ab-tests', testId, 'snapshots'],
    queryFn: () => abTestsApi.snapshots(testId!),
    enabled: !!testId,
    refetchInterval: 30000,
  })
}

// Cache hooks
export function useCacheStats() {
  return useQuery<CacheStats>({
    queryKey: ['cache-stats'],
    queryFn: cacheApi.stats,
    refetchInterval: 30000,
  })
}

export function useCacheEntries(params?: { limit?: number; offset?: number }) {
  return useQuery<CacheEntry[]>({
    queryKey: ['cache-entries', params],
    queryFn: () => cacheApi.entries(params),
  })
}

export function useClearCache() {
  const queryClient = useQueryClient()
  return useMutation<void, Error>({
    mutationFn: cacheApi.clear,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['cache-stats'] })
      queryClient.invalidateQueries({ queryKey: ['cache-entries'] })
    },
  })
}

export function useDeleteCacheEntry() {
  const queryClient = useQueryClient()
  return useMutation<void, Error, string>({
    mutationFn: cacheApi.deleteEntry,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['cache-stats'] })
      queryClient.invalidateQueries({ queryKey: ['cache-entries'] })
    },
  })
}

// Events hooks
export function useEventSubscriptions() {
  return useQuery<EventSubscription[]>({
    queryKey: ['event-subscriptions'],
    queryFn: eventsApi.listSubscriptions,
  })
}

export function useCreateEventSubscription() {
  const queryClient = useQueryClient()
  return useMutation<EventSubscription, Error, EventSubscriptionCreate>({
    mutationFn: eventsApi.createSubscription,
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ['event-subscriptions'] }) },
  })
}

export function useUpdateEventSubscription() {
  const queryClient = useQueryClient()
  return useMutation<EventSubscription, Error, { id: string; data: Partial<EventSubscriptionCreate> }>({
    mutationFn: ({ id, data }) => eventsApi.updateSubscription(id, data),
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ['event-subscriptions'] }) },
  })
}

export function useDeleteEventSubscription() {
  const queryClient = useQueryClient()
  return useMutation<void, Error, string>({
    mutationFn: eventsApi.deleteSubscription,
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ['event-subscriptions'] }) },
  })
}

export function useEventLog(params?: { event_type?: string; limit?: number; offset?: number }) {
  return useQuery<EventLogEntry[]>({
    queryKey: ['event-log', params],
    queryFn: () => eventsApi.listEvents(params),
    refetchInterval: 15000,
  })
}

export function useSendTestEvent() {
  const queryClient = useQueryClient()
  return useMutation<void, Error, { event_type: string; payload: Record<string, unknown> }>({
    mutationFn: eventsApi.sendTestEvent,
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ['event-log'] }) },
  })
}

// Playground hooks
export function usePlaygroundSessions(params?: { is_public?: boolean }) {
  return useQuery<PlaygroundSession[]>({
    queryKey: ['playground-sessions', params],
    queryFn: () => playgroundApi.listSessions(params),
  })
}

export function useCreatePlaygroundSession() {
  const queryClient = useQueryClient()
  return useMutation<PlaygroundSession, Error, PlaygroundSessionCreate>({
    mutationFn: playgroundApi.createSession,
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ['playground-sessions'] }) },
  })
}

export function useDeletePlaygroundSession() {
  const queryClient = useQueryClient()
  return useMutation<void, Error, string>({
    mutationFn: playgroundApi.deleteSession,
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ['playground-sessions'] }) },
  })
}

// Deprecations hooks
export function useModelDeprecations() {
  return useQuery<ModelDeprecation[]>({
    queryKey: ['model-deprecations'],
    queryFn: deprecationsApi.list,
  })
}

export function useCreateModelDeprecation() {
  const queryClient = useQueryClient()
  return useMutation<ModelDeprecation, Error, ModelDeprecationCreate>({
    mutationFn: deprecationsApi.create,
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ['model-deprecations'] }) },
  })
}

export function useUpdateModelDeprecation() {
  const queryClient = useQueryClient()
  return useMutation<ModelDeprecation, Error, { id: string; data: Partial<ModelDeprecationCreate> }>({
    mutationFn: ({ id, data }) => deprecationsApi.update(id, data),
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ['model-deprecations'] }) },
  })
}

export function useDeleteModelDeprecation() {
  const queryClient = useQueryClient()
  return useMutation<void, Error, string>({
    mutationFn: deprecationsApi.delete,
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ['model-deprecations'] }) },
  })
}

// Routing Policies hooks
export function useRoutingPolicies(params?: { policy_type?: string; is_active?: boolean }) {
  return useQuery<RoutingPolicy[]>({
    queryKey: ['routing-policies', params],
    queryFn: () => routingApi.list(params),
  })
}

export function useCreateRoutingPolicy() {
  const queryClient = useQueryClient()
  return useMutation<RoutingPolicy, Error, RoutingPolicyCreate>({
    mutationFn: routingApi.create,
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ['routing-policies'] }) },
  })
}

export function useUpdateRoutingPolicy() {
  const queryClient = useQueryClient()
  return useMutation<RoutingPolicy, Error, { id: string; data: RoutingPolicyCreate }>({
    mutationFn: ({ id, data }) => routingApi.update(id, data),
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ['routing-policies'] }) },
  })
}

export function useDeleteRoutingPolicy() {
  const queryClient = useQueryClient()
  return useMutation<void, Error, string>({
    mutationFn: routingApi.delete,
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ['routing-policies'] }) },
  })
}

export function useSyncRoutingPolicies() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: routingApi.syncAll,
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ['routing-policies'] }) },
  })
}

export function useLiteLLMRouterStatus() {
  return useQuery<LiteLLMRouterStatus>({
    queryKey: ['litellm-router-status'],
    queryFn: routingApi.getLiteLLMStatus,
  })
}
