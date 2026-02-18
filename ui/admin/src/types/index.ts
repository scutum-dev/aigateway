// TypeScript interfaces mirroring backend Pydantic models

export interface GuardrailAssignment {
  team_id: string
  team_name: string | null
  guardrail_config_id: string
  config_name: string
  priority: number
}

export interface MCPServerConfig {
  id: string
  name: string
  server_type: 'stdio' | 'http'
  command: string | null
  url: string | null
  args: string[]
  env: Record<string, string>
  tools: string[]
  is_active: boolean
  created_at: string
}

export interface MCPServerCreate {
  name: string
  server_type: string
  command?: string
  url?: string
  args: string[]
  env: Record<string, string>
}

export interface MCPServerUpdate {
  name?: string
  server_type?: string
  command?: string
  url?: string
  args?: string[]
  env?: Record<string, string>
  is_active?: boolean
}

export interface MCPTestResult {
  status: 'ok' | 'error'
  message: string
}

export interface GatewaySyncResult {
  status: 'ok' | 'partial' | 'error'
  servers_synced: number
  configmap: { status: string; message?: string }
  restart: { status: string; message?: string }
}

export interface GatewayConfigPreview {
  active_servers: number
  active_agents?: number
  config_yaml: string
}

// A2A Agents
export interface A2AAgentConfig {
  id: string
  name: string
  description: string | null
  url: string
  skills: string[]
  is_active: boolean
}

export interface A2AAgentCreate {
  name: string
  description?: string
  url: string
  skills: string[]
}

export interface A2AAgentUpdate {
  name?: string
  description?: string
  url?: string
  skills?: string[]
  is_active?: boolean
}

export interface A2ATestResult {
  status: 'ok' | 'error'
  message: string
}

export interface WorkflowSummary {
  id: string
  name: string
  template_type: string | null
  description: string | null
  is_active: boolean
  created_at: string
}

export interface WorkflowExecuteRequest {
  workflow_name?: string
  template_type: string
  input_text: string
  user_id?: string
  team_id?: string
  config?: Record<string, unknown>
}

export interface WorkflowExecutionSummary {
  id: string
  workflow_name: string | null
  status: string
  total_cost: number | null
  started_at: string | null
  completed_at: string | null
}

export interface WorkflowStep {
  node_name: string
  step_order: number
  status: string
  output_data: Record<string, unknown> | null
  cost: number
  duration_ms: number
  error: string | null
}

export interface WorkflowExecutionDetail {
  id: string
  workflow_name: string | null
  template_type: string | null
  status: string
  input: Record<string, unknown>
  output: Record<string, unknown> | null
  current_node: string | null
  error: string | null
  total_tokens: number
  total_cost: number
  duration_ms: number
  steps: WorkflowStep[]
  created_at: string | null
  completed_at: string | null
}

export interface WorkflowCreate {
  name: string
  template_type: string
  description?: string
  config?: Record<string, unknown>
}

export interface WorkflowTemplate {
  type: string
  name: string
  description: string
}

export interface ReportsSummary {
  today: { cost: number; requests: number }
  this_week: { cost: number; requests: number }
  this_month: { cost: number; requests: number }
  top_models: { model: string; cost: number }[]
  requests_today: number
  tokens_today: number
  model_usage: Record<string, number>
}

export interface PlatformSettings {
  default_model: string
  global_rate_limit: number
  enable_caching: boolean
  cache_ttl_seconds: number
  enable_cost_tracking: boolean
  enable_budget_enforcement: boolean
  enable_guardrails: boolean
  maintenance_mode: boolean
}

export interface LoginResponse {
  access_token: string
  expires_at: string
  token_type: string
}

export interface UserInfo {
  user_id: string
  role: string
}

// Guardrails
export interface GuardrailConfig {
  id: string
  name: string
  description: string | null
  enable_prompt_injection: boolean
  prompt_injection_threshold: number
  enable_pii_detection: boolean
  pii_action: string
  pii_entities: string[]
  enable_toxicity: boolean
  toxicity_threshold: number
  banned_topics: string[]
  enable_secrets_detection: boolean
  enable_invisible_text: boolean
  enable_malicious_urls: boolean
  enable_sensitive_output: boolean
  mode: string
  on_fail: string
  is_active: boolean
  created_at: string | null
  updated_at: string | null
}

export interface GuardrailConfigCreate {
  name: string
  description?: string
  enable_prompt_injection?: boolean
  prompt_injection_threshold?: number
  enable_pii_detection?: boolean
  pii_action?: string
  pii_entities?: string[]
  enable_toxicity?: boolean
  toxicity_threshold?: number
  banned_topics?: string[]
  enable_secrets_detection?: boolean
  enable_invisible_text?: boolean
  enable_malicious_urls?: boolean
  enable_sensitive_output?: boolean
  mode?: string
  on_fail?: string
  is_active?: boolean
}

export interface GuardrailConfigUpdate extends Partial<GuardrailConfigCreate> {}

export interface GuardrailEvent {
  id: string
  event_type: string
  scanner_name: string
  user_id: string | null
  team_id: string | null
  model: string | null
  risk_score: number | null
  action_taken: string
  details: Record<string, unknown>
  created_at: string | null
}

// Models (from LiteLLM /model/info response)
export interface ModelInfo {
  model_name: string
  litellm_params: Record<string, unknown>
  model_info: Record<string, unknown>
}

export interface ModelCreateRequest {
  model_name: string
  litellm_params: Record<string, unknown>
  model_info?: Record<string, unknown>
}

// API Keys
export interface KeyInfo {
  token: string
  key_alias: string | null
  key_name: string | null
  spend: number
  max_budget: number | null
  models: string[] | null
  team_id: string | null
  expires: string | null
  created_at: string | null
}

export interface KeyGenerateRequest {
  key_alias?: string
  max_budget?: number
  models?: string[]
  team_id?: string
  duration?: string
}

export interface KeyGenerateResponse {
  key: string
  key_name: string | null
  expires: string | null
}

// Teams (from LiteLLM)
export interface TeamInfo {
  team_id: string
  team_alias: string | null
  members_with_roles: Array<{ role: string; user_id: string }>
  max_budget: number | null
  spend: number
  models: string[]
}

export interface TeamCreateRequest {
  team_alias: string
  max_budget?: number
  models?: string[]
}

export interface TeamUpdateRequest {
  team_id: string
  team_alias?: string
  max_budget?: number
  models?: string[]
}

// Budgets (from LiteLLM)
export interface BudgetInfo {
  budget_id: string
  max_budget: number | null
  soft_budget: number | null
  max_parallel_requests: number | null
  tpm_limit: number | null
  rpm_limit: number | null
  budget_reset_at: string | null
}

export interface BudgetCreateRequest {
  max_budget?: number
  soft_budget?: number
  max_parallel_requests?: number
  tpm_limit?: number
  rpm_limit?: number
}

export interface BudgetUpdateRequest {
  budget_id: string
  max_budget?: number
  soft_budget?: number
  max_parallel_requests?: number
  tpm_limit?: number
  rpm_limit?: number
}

// Organizations
export interface Organization {
  id: string
  name: string
  slug: string
  description: string | null
  max_budget: number | null
  allowed_models: string[] | null
  metadata: Record<string, unknown>
  is_active: boolean
  created_at: string
  updated_at: string
  bu_count?: number
  team_count?: number
  member_count?: number
}

export interface OrganizationCreate {
  name: string
  slug: string
  description?: string
  max_budget?: number
  allowed_models?: string[]
}

export interface OrganizationUpdate {
  name?: string
  slug?: string
  description?: string
  max_budget?: number
  allowed_models?: string[]
  is_active?: boolean
}

// Business Units
export interface BusinessUnit {
  id: string
  org_id: string
  name: string
  slug: string
  description: string | null
  max_budget: number | null
  allowed_models: string[] | null
  is_active: boolean
  created_at: string
}

export interface BusinessUnitCreate {
  name: string
  slug: string
  description?: string
  max_budget?: number
  allowed_models?: string[]
}

// Team Hierarchy
export interface TeamHierarchy {
  team_id: string
  org_id: string
  bu_id: string | null
}

// Org Membership
export interface OrgMembership {
  id: string
  user_id: string
  email?: string
  display_name?: string
  org_id: string
  role: string
  bu_id: string | null
  created_at: string
}

// Audit Logs
export interface AuditLogEntry {
  id: string
  timestamp: string
  actor_id: string
  actor_email: string | null
  actor_ip: string | null
  org_id: string | null
  action: string
  resource_type: string
  resource_id: string | null
  resource_name: string | null
  changes: Record<string, unknown>
  created_at: string
}

// DLP
export interface ContentDetector {
  id: string
  name: string
  description: string | null
  detector_type: string
  config: Record<string, unknown>
  is_active: boolean
  created_at: string
}

export interface ContentDetectorCreate {
  name: string
  description?: string
  detector_type: string
  config: Record<string, unknown>
}

export interface TeamContentPolicy {
  id: string
  team_id: string
  policy_type: string
  config: Record<string, unknown>
  is_active: boolean
  created_at: string
}

// SSO
export interface SSOConfig {
  id: string
  org_id: string
  provider_type: string
  provider_name: string
  client_id: string | null
  issuer_url: string | null
  is_active: boolean
  created_at: string
}

export interface SSOProvider {
  org_slug: string
  org_name: string
  provider_type: string
  provider_name: string
}

// Prompt Registry
export interface PromptTemplate {
  id: string
  name: string
  slug: string
  description: string | null
  category: string | null
  template_text: string
  variables: Array<{ name: string; type: string; required: boolean; default?: string }>
  version: number
  is_current: boolean
  status: string
  team_id: string | null
  model_hint: string | null
  tags: string[]
  created_by: string | null
  approved_by: string | null
  approved_at: string | null
  is_active: boolean
  created_at: string
  updated_at: string
}

export interface PromptTemplateCreate {
  name: string
  slug: string
  description?: string
  category?: string
  template_text: string
  variables?: Array<{ name: string; type: string; required: boolean; default?: string }>
  model_hint?: string
  tags?: string[]
}

export interface PromptApproval {
  id: string
  template_id: string
  template_version: number
  requested_by: string
  reviewer: string | null
  status: string
  comment: string | null
  requested_at: string
  reviewed_at: string | null
}

// Rate Limits
export interface RateLimitPolicy {
  id: string
  name: string
  description: string | null
  scope: string
  scope_value: string | null
  rpm_limit: number | null
  tpm_limit: number | null
  rpd_limit: number | null
  tpd_limit: number | null
  burst_multiplier: number
  burst_window_seconds: number
  priority: number
  is_active: boolean
  created_at: string
}

export interface RateLimitPolicyCreate {
  name: string
  description?: string
  scope: string
  scope_value?: string
  rpm_limit?: number
  tpm_limit?: number
  rpd_limit?: number
  tpd_limit?: number
  burst_multiplier?: number
  burst_window_seconds?: number
  priority?: number
}

export interface RateLimitEvent {
  id: string
  policy_id: string | null
  scope: string | null
  scope_value: string | null
  limit_type: string
  current_value: number
  limit_value: number
  action: string
  created_at: string
}

// Model Access
export interface ModelAccessTier {
  id: string
  name: string
  description: string | null
  requires_approval: boolean
  requires_justification: boolean
  max_grant_duration_days: number | null
  models: string[]
  created_at: string
}

export interface ModelAccessTierCreate {
  name: string
  description?: string
  requires_approval?: boolean
  requires_justification?: boolean
  max_grant_duration_days?: number
  models?: string[]
}

export interface ModelAccessRequest {
  id: string
  user_id: string
  team_id: string | null
  model_pattern: string
  tier_id: string | null
  justification: string | null
  status: string
  reviewer: string | null
  review_comment: string | null
  granted_at: string | null
  expires_at: string | null
  created_at: string
}

export interface ModelAccessRequestCreate {
  model_pattern: string
  tier_id?: string
  team_id?: string
  justification?: string
}

// Chargeback
export interface CostAllocationRule {
  id: string
  name: string
  team_id: string | null
  allocation_type: string
  allocation_target: string
  allocation_percent: number
  metadata: Record<string, unknown>
  is_active: boolean
  created_at: string
}

export interface CostAllocationRuleCreate {
  name: string
  team_id?: string
  allocation_type: string
  allocation_target: string
  allocation_percent?: number
  metadata?: Record<string, unknown>
}

export interface ChargebackReport {
  id: string
  report_period: string
  status: string
  total_cost: number
  breakdown: unknown[]
  generated_by: string | null
  finalized_at: string | null
  created_at: string
}

export interface BudgetForecast {
  id: string
  team_id: string | null
  forecast_period: string
  forecast_type: string
  forecasted_cost: number
  confidence_low: number
  confidence_high: number
  actual_cost: number | null
  created_at: string
}

// SLA Monitoring
export interface SLADefinition {
  id: string
  name: string
  provider: string | null
  model_pattern: string | null
  target_p50_ms: number | null
  target_p95_ms: number | null
  target_p99_ms: number | null
  target_error_rate: number
  target_availability: number
  evaluation_window_minutes: number
  alert_channels: string[]
  is_active: boolean
  created_at: string
}

export interface SLADefinitionCreate {
  name: string
  provider?: string
  model_pattern?: string
  target_p50_ms?: number
  target_p95_ms?: number
  target_p99_ms?: number
  target_error_rate?: number
  target_availability?: number
  evaluation_window_minutes?: number
  alert_channels?: string[]
}

export interface ProviderHealthMetric {
  id: string
  provider: string
  model: string
  bucket_start: string
  request_count: number
  error_count: number
  p50_latency_ms: number | null
  p95_latency_ms: number | null
  p99_latency_ms: number | null
  avg_latency_ms: number | null
  total_tokens: number
  total_cost: number
}

export interface SLAViolation {
  id: string
  sla_definition_id: string
  provider: string | null
  model: string | null
  violation_type: string
  threshold_value: number
  actual_value: number
  alert_sent: boolean
  resolved_at: string | null
  created_at: string
}

export interface FailoverRule {
  id: string
  primary_model: string
  fallback_model: string
  trigger_condition: string | null
  trigger_threshold: number | null
  cooldown_minutes: number
  is_active: boolean
  last_triggered_at: string | null
  created_at: string
}

export interface FailoverRuleCreate {
  primary_model: string
  fallback_model: string
  trigger_condition?: string
  trigger_threshold?: number
  cooldown_minutes?: number
}

// A/B Tests
export interface ABTest {
  id: string
  name: string
  status: string
  base_model: string
  variant_model: string
  traffic_split_percent: number
  success_metric: string
  promotion_threshold: Record<string, unknown> | null
  rollback_threshold: Record<string, unknown> | null
  auto_promote: boolean
  auto_rollback: boolean
  started_at: string | null
  completed_at: string | null
  created_by: string | null
  created_at: string
}

export interface ABTestCreate {
  name: string
  base_model: string
  variant_model: string
  traffic_split_percent?: number
  success_metric?: string
  auto_promote?: boolean
  auto_rollback?: boolean
}

export interface ABTestSnapshot {
  id: string
  test_id: string
  snapshot_at: string
  base_metrics: Record<string, unknown> | null
  variant_metrics: Record<string, unknown> | null
  recommendation: string | null
}

// Semantic Cache
export interface CacheStats {
  total_entries: number
  total_hits: number
  hit_rate: number
  cache_size_mb: number
  avg_token_savings: number
}

export interface CacheEntry {
  id: string
  prompt_hash: string
  model: string
  token_count: number | null
  hit_count: number
  last_hit_at: string | null
  created_at: string
  expires_at: string | null
}

export interface CacheSettings {
  enabled: boolean
  similarity_threshold: number
  ttl_seconds: number
  max_entries: number
}

// Event System
export interface EventSubscription {
  id: string
  name: string
  event_types: string[]
  channel: string
  config: Record<string, unknown>
  filters: Record<string, unknown> | null
  is_active: boolean
  created_at: string
}

export interface EventSubscriptionCreate {
  name: string
  event_types: string[]
  channel: string
  config: Record<string, unknown>
  filters?: Record<string, unknown>
}

export interface EventLogEntry {
  id: string
  event_type: string
  payload: Record<string, unknown>
  source_service: string | null
  created_at: string
}

// Playground
export interface PlaygroundSession {
  id: string
  name: string | null
  prompt: string
  models: string[]
  settings: Record<string, unknown> | null
  results: Record<string, unknown> | null
  created_by: string | null
  is_public: boolean
  created_at: string
}

export interface PlaygroundSessionCreate {
  name?: string
  prompt: string
  models: string[]
  settings?: Record<string, unknown>
  results?: Record<string, unknown>
  is_public?: boolean
}

// Model Deprecations
export interface ModelDeprecation {
  id: string
  model_name: string
  replacement_model: string | null
  deprecation_date: string | null
  sunset_date: string | null
  message: string | null
  created_at: string
}

export interface ModelDeprecationCreate {
  model_name: string
  replacement_model?: string
  deprecation_date?: string
  sunset_date?: string
  message?: string
}
