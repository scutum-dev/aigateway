// ============================================================================
// AI Gateway Platform - Cedar RBAC Policies
// Version: 1.0
//
// Cedar Policy Language: https://www.cedarpolicy.com/
// These policies are enforced by Agent Gateway for authorization decisions
// ============================================================================

// ============================================================================
// NAMESPACE: AI Gateway
// ============================================================================

namespace AIGateway {
    // ========================================================================
    // Entity Types
    // ========================================================================

    entity User {
        team: Team,
        roles: Set<Role>,
        budget_remaining: Long,
        tier: String,
    };

    entity Team {
        org: Organization,
        budget_limit: Long,
        allowed_models: Set<String>,
    };

    entity Organization {
        plan: String,
    };

    entity Role;

    entity Model {
        provider: String,
        tier: String,
        cost_per_1k_tokens: Decimal,
    };

    entity MCPServer {
        owner: Team,
        sensitivity: String,
    };

    entity Agent {
        owner: User,
        capabilities: Set<String>,
    };

    // ========================================================================
    // Actions
    // ========================================================================

    action "llm:chat" appliesTo {
        principal: [User, Agent],
        resource: [Model],
    };

    action "llm:completion" appliesTo {
        principal: [User, Agent],
        resource: [Model],
    };

    action "llm:embedding" appliesTo {
        principal: [User, Agent],
        resource: [Model],
    };

    action "mcp:invoke" appliesTo {
        principal: [User, Agent],
        resource: [MCPServer],
    };

    action "mcp:list_tools" appliesTo {
        principal: [User, Agent],
        resource: [MCPServer],
    };

    action "a2a:send" appliesTo {
        principal: [Agent],
        resource: [Agent],
    };

    action "a2a:discover" appliesTo {
        principal: [User, Agent],
        resource: [Agent],
    };

    action "admin:manage_keys" appliesTo {
        principal: [User],
        resource: [Team],
    };

    action "admin:view_spend" appliesTo {
        principal: [User],
        resource: [Team, Organization],
    };

    action "admin:set_budget" appliesTo {
        principal: [User],
        resource: [Team],
    };
}

// ============================================================================
// ROLE DEFINITIONS
// ============================================================================

// Platform Administrator - Full access
permit (
    principal in AIGateway::Role::"platform-admin",
    action,
    resource
);

// Team Admin - Manage team resources
permit (
    principal,
    action in [
        AIGateway::Action::"admin:manage_keys",
        AIGateway::Action::"admin:view_spend",
        AIGateway::Action::"admin:set_budget"
    ],
    resource
) when {
    principal.roles.contains(AIGateway::Role::"team-admin") &&
    principal.team == resource
};

// ============================================================================
// LLM ACCESS POLICIES
// ============================================================================

// Basic LLM Access - Users can access models their team is allowed
permit (
    principal,
    action in [
        AIGateway::Action::"llm:chat",
        AIGateway::Action::"llm:completion"
    ],
    resource
) when {
    principal.team.allowed_models.contains(resource.id) &&
    principal.budget_remaining > 0
};

// Embedding Access - More permissive (lower cost)
permit (
    principal,
    action == AIGateway::Action::"llm:embedding",
    resource
) when {
    resource.tier == "embedding" &&
    principal.budget_remaining > 0
};

// Premium Model Access - Requires premium tier
permit (
    principal,
    action in [
        AIGateway::Action::"llm:chat",
        AIGateway::Action::"llm:completion"
    ],
    resource
) when {
    resource.tier == "premium" &&
    principal.tier in ["premium", "enterprise"] &&
    principal.team.allowed_models.contains(resource.id)
};

// Deny access to premium models for basic tier
forbid (
    principal,
    action in [
        AIGateway::Action::"llm:chat",
        AIGateway::Action::"llm:completion"
    ],
    resource
) when {
    resource.tier == "premium" &&
    principal.tier == "basic"
};

// Deny when budget exhausted
forbid (
    principal,
    action in [
        AIGateway::Action::"llm:chat",
        AIGateway::Action::"llm:completion",
        AIGateway::Action::"llm:embedding"
    ],
    resource
) when {
    principal.budget_remaining <= 0
};

// ============================================================================
// MCP SERVER ACCESS POLICIES
// ============================================================================

// Allow tool listing for all authenticated users
permit (
    principal,
    action == AIGateway::Action::"mcp:list_tools",
    resource
) when {
    resource.sensitivity != "restricted"
};

// Allow MCP invocation for team-owned servers
permit (
    principal,
    action == AIGateway::Action::"mcp:invoke",
    resource
) when {
    resource.owner == principal.team
};

// Allow MCP invocation for public servers
permit (
    principal,
    action == AIGateway::Action::"mcp:invoke",
    resource
) when {
    resource.sensitivity == "public"
};

// Restricted servers require explicit role
permit (
    principal,
    action == AIGateway::Action::"mcp:invoke",
    resource
) when {
    resource.sensitivity == "restricted" &&
    principal.roles.contains(AIGateway::Role::"mcp-restricted-access")
};

// ============================================================================
// A2A (AGENT-TO-AGENT) POLICIES
// ============================================================================

// Agents can discover other agents in same organization
permit (
    principal,
    action == AIGateway::Action::"a2a:discover",
    resource
) when {
    principal.owner.team.org == resource.owner.team.org
};

// Agents can send messages to agents in same team
permit (
    principal,
    action == AIGateway::Action::"a2a:send",
    resource
) when {
    principal.owner.team == resource.owner.team
};

// Cross-team agent communication requires explicit capability
permit (
    principal,
    action == AIGateway::Action::"a2a:send",
    resource
) when {
    principal.capabilities.contains("cross-team-communication") &&
    principal.owner.team.org == resource.owner.team.org
};

// ============================================================================
// ADMIN POLICIES
// ============================================================================

// Team admins can view their team's spend
permit (
    principal,
    action == AIGateway::Action::"admin:view_spend",
    resource
) when {
    principal.roles.contains(AIGateway::Role::"team-admin") &&
    principal.team == resource
};

// Org admins can view all team spend in their org
permit (
    principal,
    action == AIGateway::Action::"admin:view_spend",
    resource
) when {
    principal.roles.contains(AIGateway::Role::"org-admin") &&
    principal.team.org == resource.org
};

// Only org admins can set budgets
permit (
    principal,
    action == AIGateway::Action::"admin:set_budget",
    resource
) when {
    principal.roles.contains(AIGateway::Role::"org-admin") &&
    principal.team.org == resource.org
};

// ============================================================================
// RATE LIMITING POLICIES (Deny patterns)
// ============================================================================

// Deny high-frequency requests from non-premium users
// (Enforced via context attribute set by rate limiter)
forbid (
    principal,
    action in [
        AIGateway::Action::"llm:chat",
        AIGateway::Action::"llm:completion"
    ],
    resource
) when {
    context.rate_limit_exceeded == true &&
    principal.tier == "basic"
};

// ============================================================================
// AUDIT POLICIES
// ============================================================================

// All admin actions are logged (marker policy for audit system)
@advice("audit:required")
permit (
    principal,
    action in [
        AIGateway::Action::"admin:manage_keys",
        AIGateway::Action::"admin:set_budget"
    ],
    resource
);

// Premium model usage is logged
@advice("audit:billing")
permit (
    principal,
    action in [
        AIGateway::Action::"llm:chat",
        AIGateway::Action::"llm:completion"
    ],
    resource
) when {
    resource.tier == "premium"
};
