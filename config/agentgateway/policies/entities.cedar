// ============================================================================
// AI Gateway Platform - Cedar Entity Definitions
// Version: 1.0
// Last Updated: 2026-02
//
// Entity instances for the AI Gateway Cedar policies
// In production, these are dynamically loaded from PostgreSQL/Vault
// ============================================================================

// ============================================================================
// ORGANIZATIONS
// ============================================================================

AIGateway::Organization::"acme-corp" {
    plan: "enterprise",
};

AIGateway::Organization::"startup-inc" {
    plan: "premium",
};

AIGateway::Organization::"demo-org" {
    plan: "basic",
};

// ============================================================================
// ROLES
// ============================================================================

AIGateway::Role::"platform-admin";
AIGateway::Role::"org-admin";
AIGateway::Role::"team-admin";
AIGateway::Role::"developer";
AIGateway::Role::"analyst";
AIGateway::Role::"mcp-restricted-access";

// ============================================================================
// TEAMS
// ============================================================================

AIGateway::Team::"acme-engineering" {
    org: AIGateway::Organization::"acme-corp",
    budget_limit: 10000,
    allowed_models: [
        "gpt-4o",
        "gpt-4o-mini",
        "claude-3-5-sonnet",
        "claude-3-haiku",
        "grok-3",
        "llama-3.1-70b",
        "llama-3.1-8b"
    ],
};

AIGateway::Team::"acme-data-science" {
    org: AIGateway::Organization::"acme-corp",
    budget_limit: 25000,
    allowed_models: [
        "gpt-4o",
        "gpt-4-turbo",
        "claude-3-opus",
        "claude-3-5-sonnet",
        "grok-3",
        "llama-3.1-70b"
    ],
};

AIGateway::Team::"acme-product" {
    org: AIGateway::Organization::"acme-corp",
    budget_limit: 5000,
    allowed_models: [
        "gpt-4o-mini",
        "claude-3-haiku",
        "grok-3-mini",
        "llama-3.1-8b"
    ],
};

AIGateway::Team::"startup-dev" {
    org: AIGateway::Organization::"startup-inc",
    budget_limit: 2000,
    allowed_models: [
        "gpt-4o-mini",
        "claude-3-haiku",
        "llama-3.1-8b"
    ],
};

// ============================================================================
// MODELS
// ============================================================================

// OpenAI Models
AIGateway::Model::"gpt-4o" {
    provider: "openai",
    tier: "premium",
    cost_per_1k_tokens: 0.005,
};

AIGateway::Model::"gpt-4o-mini" {
    provider: "openai",
    tier: "standard",
    cost_per_1k_tokens: 0.00015,
};

AIGateway::Model::"gpt-4-turbo" {
    provider: "openai",
    tier: "premium",
    cost_per_1k_tokens: 0.01,
};

// Anthropic Models
AIGateway::Model::"claude-3-opus" {
    provider: "anthropic",
    tier: "premium",
    cost_per_1k_tokens: 0.015,
};

AIGateway::Model::"claude-3-5-sonnet" {
    provider: "anthropic",
    tier: "standard",
    cost_per_1k_tokens: 0.003,
};

AIGateway::Model::"claude-3-haiku" {
    provider: "anthropic",
    tier: "standard",
    cost_per_1k_tokens: 0.00025,
};

// XAI Models
AIGateway::Model::"grok-3" {
    provider: "xai",
    tier: "premium",
    cost_per_1k_tokens: 0.003,
};

AIGateway::Model::"grok-3-mini" {
    provider: "xai",
    tier: "standard",
    cost_per_1k_tokens: 0.0003,
};

// Self-hosted Models (vLLM)
AIGateway::Model::"llama-3.1-70b" {
    provider: "vllm",
    tier: "standard",
    cost_per_1k_tokens: 0.0001,
};

AIGateway::Model::"llama-3.1-8b" {
    provider: "vllm",
    tier: "basic",
    cost_per_1k_tokens: 0.00005,
};

// Embedding Models
AIGateway::Model::"text-embedding-3-small" {
    provider: "openai",
    tier: "embedding",
    cost_per_1k_tokens: 0.00002,
};

AIGateway::Model::"text-embedding-3-large" {
    provider: "openai",
    tier: "embedding",
    cost_per_1k_tokens: 0.00013,
};

// ============================================================================
// MCP SERVERS
// ============================================================================

AIGateway::MCPServer::"filesystem-tools" {
    owner: AIGateway::Team::"acme-engineering",
    sensitivity: "internal",
};

AIGateway::MCPServer::"database-tools" {
    owner: AIGateway::Team::"acme-data-science",
    sensitivity: "restricted",
};

AIGateway::MCPServer::"web-search" {
    owner: AIGateway::Team::"acme-engineering",
    sensitivity: "public",
};

AIGateway::MCPServer::"code-analysis" {
    owner: AIGateway::Team::"acme-engineering",
    sensitivity: "internal",
};

// ============================================================================
// SAMPLE USERS
// ============================================================================

AIGateway::User::"alice@acme.com" {
    team: AIGateway::Team::"acme-engineering",
    roles: [
        AIGateway::Role::"team-admin",
        AIGateway::Role::"developer"
    ],
    budget_remaining: 500,
    tier: "enterprise",
};

AIGateway::User::"bob@acme.com" {
    team: AIGateway::Team::"acme-data-science",
    roles: [
        AIGateway::Role::"org-admin",
        AIGateway::Role::"analyst"
    ],
    budget_remaining: 2000,
    tier: "enterprise",
};

AIGateway::User::"carol@acme.com" {
    team: AIGateway::Team::"acme-product",
    roles: [
        AIGateway::Role::"developer"
    ],
    budget_remaining: 100,
    tier: "premium",
};

AIGateway::User::"dave@startup.io" {
    team: AIGateway::Team::"startup-dev",
    roles: [
        AIGateway::Role::"team-admin",
        AIGateway::Role::"developer"
    ],
    budget_remaining: 50,
    tier: "basic",
};

// ============================================================================
// SAMPLE AGENTS
// ============================================================================

AIGateway::Agent::"code-assistant-1" {
    owner: AIGateway::User::"alice@acme.com",
    capabilities: [
        "code-generation",
        "code-review"
    ],
};

AIGateway::Agent::"data-analyst-1" {
    owner: AIGateway::User::"bob@acme.com",
    capabilities: [
        "data-analysis",
        "visualization",
        "cross-team-communication"
    ],
};

AIGateway::Agent::"product-assistant-1" {
    owner: AIGateway::User::"carol@acme.com",
    capabilities: [
        "document-generation"
    ],
};
