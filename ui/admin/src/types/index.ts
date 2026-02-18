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
