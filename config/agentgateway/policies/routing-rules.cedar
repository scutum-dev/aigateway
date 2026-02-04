// =============================================================================
// Cedar Policies for AI Gateway Model Routing
// =============================================================================
// These policies control which models can be selected for routing based on
// cost, latency, budget, and capability constraints.
// =============================================================================

// -----------------------------------------------------------------------------
// Cost-Based Routing
// -----------------------------------------------------------------------------

// When budget is critically low, prefer self-hosted models
@id("cost-001")
permit (principal, action == Action::"routing:select_model", resource)
when {
    context.cost_budget_remaining < 10.0 &&
    resource.provider == "vllm"
};

// When budget is moderately low, prefer budget-tier models
@id("cost-002")
permit (principal, action == Action::"routing:select_model", resource)
when {
    context.cost_budget_remaining < 50.0 &&
    context.cost_budget_remaining >= 10.0 &&
    (resource.tier == "budget" || resource.tier == "free")
};

// Forbid premium models when budget is very low
@id("cost-003")
forbid (principal, action == Action::"routing:select_model", resource)
when {
    context.cost_budget_remaining < 5.0 &&
    resource.tier == "premium"
};

// -----------------------------------------------------------------------------
// Latency SLA Routing
// -----------------------------------------------------------------------------

// Forbid models that exceed latency SLA
@id("latency-001")
forbid (principal, action == Action::"routing:select_model", resource)
when {
    context.latency_sla_ms > 0 &&
    resource has average_latency_ms &&
    resource.average_latency_ms > context.latency_sla_ms
};

// Prefer fast models for low-latency requirements
@id("latency-002")
permit (principal, action == Action::"routing:select_model", resource)
when {
    context.latency_sla_ms < 1000 &&
    resource has average_latency_ms &&
    resource.average_latency_ms < 500
};

// -----------------------------------------------------------------------------
// Error Rate Circuit Breaker
// -----------------------------------------------------------------------------

// Block models with high error rates (> 5%)
@id("circuit-001")
forbid (principal, action == Action::"routing:select_model", resource)
when {
    resource has current_error_rate &&
    resource.current_error_rate > 0.05
};

// Block models with critical error rates (> 10%) - hard stop
@id("circuit-002")
forbid (principal, action == Action::"routing:select_model", resource)
when {
    resource has current_error_rate &&
    resource.current_error_rate > 0.10
};

// -----------------------------------------------------------------------------
// Priority-Based Routing
// -----------------------------------------------------------------------------

// High priority requests can use premium models regardless of budget
@id("priority-001")
permit (principal, action == Action::"routing:select_model", resource)
when {
    context.priority == "high" &&
    resource.tier == "premium"
};

// Low priority requests should use budget models
@id("priority-002")
permit (principal, action == Action::"routing:select_model", resource)
when {
    context.priority == "low" &&
    (resource.tier == "budget" || resource.tier == "free" || resource.provider == "vllm")
};

// -----------------------------------------------------------------------------
// Provider Diversity (Avoid Single Point of Failure)
// -----------------------------------------------------------------------------

// Default permit for all model selections (base policy)
// This ensures requests aren't blocked by default
@id("default-001")
permit (principal, action == Action::"routing:select_model", resource);
