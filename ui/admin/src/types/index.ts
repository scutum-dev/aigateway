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

export interface TeamMemberAdd {
  user_id: string
  role: 'member' | 'admin'
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

export interface WorkflowSummary {
  id: string
  name: string
  template_type: string | null
  description: string | null
  is_active: boolean
  created_at: string
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
