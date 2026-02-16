// TypeScript interfaces mirroring backend Pydantic models

export interface ModelConfig {
  model_id: string
  provider: string
  litellm_model_name: string
  tier: 'free' | 'budget' | 'standard' | 'premium'
  cost_per_1k_input: number
  cost_per_1k_output: number
  default_latency_sla_ms: number
  max_tokens: number | null
  supports_streaming: boolean
  supports_function_calling: boolean
  supports_vision: boolean
  is_active: boolean
  created_at: string
  updated_at: string
}

export interface ModelUpdate {
  tier?: string
  cost_per_1k_input?: number
  cost_per_1k_output?: number
  default_latency_sla_ms?: number
}

export interface Budget {
  id: string
  name: string
  entity_type: 'global' | 'team' | 'user'
  entity_id: string | null
  monthly_limit: number
  current_spend: number
  soft_limit_percent: number
  hard_limit_percent: number
  alert_email: string | null
  is_active: boolean
  created_at: string
  updated_at: string
}

export interface BudgetCreate {
  name: string
  entity_type: string
  entity_id: string
  monthly_limit: number
  soft_limit_percent: number
  hard_limit_percent: number
  alert_email: string
}

export interface BudgetUpdate {
  name?: string
  monthly_limit?: number
  soft_limit_percent?: number
  hard_limit_percent?: number
  alert_email?: string | null
  is_active?: boolean
}

export interface Team {
  id: string
  name: string
  description: string | null
  monthly_budget: number | null
  default_model: string | null
  is_active: boolean
  members: string[]
  created_at: string
  updated_at: string
}

export interface TeamCreate {
  name: string
  description: string
  monthly_budget: number | null
  default_model: string
}

export interface TeamUpdate {
  name?: string
  description?: string | null
  monthly_budget?: number | null
  default_model?: string | null
  is_active?: boolean
}

export interface TeamMemberAdd {
  user_id: string
  role: 'member' | 'admin'
}

export interface GuardrailAssignment {
  team_id: string
  team_name: string
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
  config_yaml: string
}

export interface APIKeyInfo {
  token: string | null
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
  metadata?: Record<string, unknown>
}

export interface KeyGenerateResponse {
  key: string
  key_name: string
  expires: string | null
  [key: string]: unknown
}

export interface KeyUpdateRequest {
  key: string
  key_alias?: string
  max_budget?: number
  models?: string[]
  duration?: string
}

export interface KeyDeleteRequest {
  keys: string[]
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

export interface RealtimeMetrics {
  requests_per_minute: number
  total_cost_today: number
  total_tokens_today: number
  error_rate: number
  provider_status: Record<string, boolean>
  model_usage: Record<string, number>
}

export interface PlatformSettings {
  default_model: string
  global_rate_limit: number
  enable_caching: boolean
  cache_ttl_seconds: number
  enable_cost_tracking: boolean
  enable_budget_enforcement: boolean
  enable_routing_policies: boolean
  enable_guardrails: boolean
  maintenance_mode: boolean
}

export interface LoginResponse {
  access_token: string
  expires_at: string
  token_type: string
}

export interface RoutingPolicy {
  id: string
  name: string
  description: string
  priority: number
  condition: PolicyCondition
  action: 'permit' | 'deny'
  targetModels: string[]
  isActive: boolean
}

export interface PolicyCondition {
  type: 'and' | 'or' | 'comparison'
  field?: string
  operator?: '<' | '>' | '<=' | '>=' | '==' | '!='
  value?: string | number | boolean
  children?: PolicyCondition[]
}

export interface RoutingPolicyCreate {
  name: string
  description: string
  priority: number
  condition: PolicyCondition
  action: 'permit' | 'deny'
  targetModels: string[]
  isActive: boolean
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

