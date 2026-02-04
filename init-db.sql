-- Initialize databases for AI Gateway Platform
-- This runs when postgres container starts fresh

-- Create LiteLLM database and user
CREATE DATABASE litellm;
CREATE USER litellm WITH ENCRYPTED PASSWORD 'litellm';
GRANT ALL PRIVILEGES ON DATABASE litellm TO litellm;

-- Connect to litellm database
\c litellm;

-- Grant schema permissions to litellm user
GRANT ALL ON SCHEMA public TO litellm;
ALTER SCHEMA public OWNER TO litellm;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO litellm;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO litellm;

-- Create extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- =============================================================================
-- Custom tables for FinOps reporting (LiteLLM creates its own tables separately)
-- =============================================================================

-- Cost tracking aggregated by day (for FinOps Reporter)
CREATE TABLE IF NOT EXISTS cost_tracking_daily (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    date DATE NOT NULL,
    user_id VARCHAR(255),
    team_id VARCHAR(255),
    model VARCHAR(255) NOT NULL,
    provider VARCHAR(255),
    request_count BIGINT DEFAULT 0,
    input_tokens BIGINT DEFAULT 0,
    output_tokens BIGINT DEFAULT 0,
    total_cost DECIMAL(20, 10) DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(date, user_id, team_id, model)
);

CREATE INDEX idx_cost_tracking_date ON cost_tracking_daily(date);
CREATE INDEX idx_cost_tracking_user ON cost_tracking_daily(user_id);
CREATE INDEX idx_cost_tracking_team ON cost_tracking_daily(team_id);
CREATE INDEX idx_cost_tracking_model ON cost_tracking_daily(model);

-- Budget alerts history (for Budget Webhook)
CREATE TABLE IF NOT EXISTS budget_alerts (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    user_id VARCHAR(255),
    team_id VARCHAR(255),
    alert_type VARCHAR(50) NOT NULL,
    threshold_percent DECIMAL(5, 2),
    current_spend DECIMAL(20, 10),
    budget_limit DECIMAL(20, 10),
    message TEXT,
    acknowledged BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_budget_alerts_user ON budget_alerts(user_id);
CREATE INDEX idx_budget_alerts_team ON budget_alerts(team_id);
CREATE INDEX idx_budget_alerts_created ON budget_alerts(created_at);

-- =============================================================================
-- Policy Router tables
-- =============================================================================

-- Routing decisions log
CREATE TABLE IF NOT EXISTS routing_decisions (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    timestamp TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    user_id VARCHAR(255),
    team_id VARCHAR(255),
    requested_model VARCHAR(255),
    selected_model VARCHAR(255) NOT NULL,
    fallback_models VARCHAR(255)[],
    decision_reason TEXT,
    context_snapshot JSONB
);

CREATE INDEX idx_routing_decisions_timestamp ON routing_decisions(timestamp);
CREATE INDEX idx_routing_decisions_user ON routing_decisions(user_id);

-- Model routing configuration
CREATE TABLE IF NOT EXISTS model_routing_config (
    model_id VARCHAR(255) PRIMARY KEY,
    provider VARCHAR(255),
    tier VARCHAR(50),
    cost_per_1k_input DECIMAL(20, 10),
    cost_per_1k_output DECIMAL(20, 10),
    supports_streaming BOOLEAN DEFAULT TRUE,
    supports_function_calling BOOLEAN DEFAULT FALSE,
    default_latency_sla_ms INTEGER DEFAULT 5000,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- Insert default model configurations
INSERT INTO model_routing_config (model_id, provider, tier, cost_per_1k_input, cost_per_1k_output, supports_streaming, supports_function_calling, default_latency_sla_ms)
VALUES
    ('gpt-4o', 'openai', 'premium', 0.0025, 0.010, TRUE, TRUE, 5000),
    ('gpt-4o-mini', 'openai', 'budget', 0.00015, 0.0006, TRUE, TRUE, 3000),
    ('claude-3-5-sonnet', 'anthropic', 'premium', 0.003, 0.015, TRUE, TRUE, 5000),
    ('claude-3-haiku', 'anthropic', 'budget', 0.00025, 0.00125, TRUE, TRUE, 2000),
    ('grok-3', 'xai', 'premium', 0.003, 0.015, TRUE, TRUE, 4000),
    ('llama-3.1-70b', 'vllm', 'standard', 0.0001, 0.0003, TRUE, FALSE, 8000)
ON CONFLICT DO NOTHING;

-- =============================================================================
-- Workflow Engine tables
-- =============================================================================

-- Workflow definitions
CREATE TABLE IF NOT EXISTS workflow_definitions (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    name VARCHAR(255) UNIQUE NOT NULL,
    version VARCHAR(50) DEFAULT '1.0.0',
    template_type VARCHAR(100),
    description TEXT,
    graph_definition JSONB NOT NULL,
    input_schema JSONB,
    output_schema JSONB,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- Workflow executions
CREATE TABLE IF NOT EXISTS workflow_executions (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    workflow_id UUID REFERENCES workflow_definitions(id),
    workflow_name VARCHAR(255),
    template_type VARCHAR(100),
    user_id VARCHAR(255),
    team_id VARCHAR(255),
    status VARCHAR(50) DEFAULT 'pending',
    input JSONB,
    output JSONB,
    current_node VARCHAR(255),
    error TEXT,
    total_tokens BIGINT DEFAULT 0,
    total_cost DECIMAL(20, 10) DEFAULT 0,
    duration_ms INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMPTZ
);

CREATE INDEX idx_executions_user ON workflow_executions(user_id);
CREATE INDEX idx_executions_status ON workflow_executions(status);
CREATE INDEX idx_executions_created ON workflow_executions(created_at);

-- Workflow checkpoints (for LangGraph persistence)
CREATE TABLE IF NOT EXISTS workflow_checkpoints (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    execution_id UUID REFERENCES workflow_executions(id),
    thread_id VARCHAR(255) NOT NULL,
    checkpoint_id VARCHAR(255) NOT NULL,
    parent_checkpoint_id VARCHAR(255),
    checkpoint_data JSONB NOT NULL,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(thread_id, checkpoint_id)
);

CREATE INDEX idx_checkpoints_thread ON workflow_checkpoints(thread_id);

-- Workflow steps
CREATE TABLE IF NOT EXISTS workflow_steps (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    execution_id UUID REFERENCES workflow_executions(id),
    node_name VARCHAR(255) NOT NULL,
    step_order INTEGER NOT NULL,
    status VARCHAR(50) DEFAULT 'pending',
    input_data JSONB,
    output_data JSONB,
    input_tokens BIGINT DEFAULT 0,
    output_tokens BIGINT DEFAULT 0,
    cost DECIMAL(20, 10) DEFAULT 0,
    duration_ms INTEGER DEFAULT 0,
    error TEXT,
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ
);

CREATE INDEX idx_steps_execution ON workflow_steps(execution_id);

-- =============================================================================
-- Admin API tables
-- =============================================================================

-- Routing policies (Cedar-style)
CREATE TABLE IF NOT EXISTS routing_policies (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    name VARCHAR(255) UNIQUE NOT NULL,
    description TEXT,
    priority INTEGER DEFAULT 0,
    condition TEXT NOT NULL,
    action VARCHAR(50) DEFAULT 'permit',
    target_models VARCHAR(255)[],
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- Budgets
CREATE TABLE IF NOT EXISTS budgets (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    entity_type VARCHAR(50) NOT NULL,
    entity_id VARCHAR(255),
    monthly_limit DECIMAL(20, 10) NOT NULL,
    current_spend DECIMAL(20, 10) DEFAULT 0,
    soft_limit_percent DECIMAL(5, 2) DEFAULT 0.80,
    hard_limit_percent DECIMAL(5, 2) DEFAULT 1.00,
    alert_email VARCHAR(255),
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(entity_type, entity_id)
);

-- Teams
CREATE TABLE IF NOT EXISTS teams (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    name VARCHAR(255) UNIQUE NOT NULL,
    description TEXT,
    monthly_budget DECIMAL(20, 10),
    default_model VARCHAR(255),
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- Team members
CREATE TABLE IF NOT EXISTS team_members (
    team_id UUID REFERENCES teams(id) ON DELETE CASCADE,
    user_id VARCHAR(255) NOT NULL,
    role VARCHAR(50) DEFAULT 'member',
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (team_id, user_id)
);

-- MCP servers configuration
CREATE TABLE IF NOT EXISTS mcp_servers (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    name VARCHAR(255) UNIQUE NOT NULL,
    server_type VARCHAR(50) NOT NULL,
    command TEXT,
    url TEXT,
    args TEXT[],
    env JSONB,
    tools TEXT[],
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- Platform settings
CREATE TABLE IF NOT EXISTS platform_settings (
    key VARCHAR(255) PRIMARY KEY,
    value JSONB NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- Insert default platform settings
INSERT INTO platform_settings (key, value)
VALUES
    ('default_model', '"gpt-4o-mini"'),
    ('global_rate_limit', '1000'),
    ('enable_caching', 'true'),
    ('cache_ttl_seconds', '3600'),
    ('enable_cost_tracking', 'true'),
    ('enable_budget_enforcement', 'true'),
    ('enable_routing_policies', 'true'),
    ('maintenance_mode', 'false')
ON CONFLICT DO NOTHING;

-- Insert sample teams
INSERT INTO teams (name, description, monthly_budget, default_model)
VALUES
    ('engineering', 'Engineering team', 500.00, 'gpt-4o-mini'),
    ('data-science', 'Data Science team', 1000.00, 'gpt-4o'),
    ('product', 'Product team', 250.00, 'claude-3-haiku')
ON CONFLICT DO NOTHING;

-- Insert sample budgets
INSERT INTO budgets (name, entity_type, entity_id, monthly_limit, soft_limit_percent, hard_limit_percent)
VALUES
    ('Engineering Budget', 'team', 'engineering', 500.00, 0.80, 1.00),
    ('Data Science Budget', 'team', 'data-science', 1000.00, 0.80, 1.00),
    ('Global Budget', 'global', NULL, 5000.00, 0.80, 0.95)
ON CONFLICT DO NOTHING;

-- Grant permissions on new tables
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO litellm;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO litellm;

-- =============================================================================
-- Sample data for testing
-- =============================================================================
INSERT INTO cost_tracking_daily (date, user_id, team_id, model, request_count, input_tokens, output_tokens, total_cost)
VALUES
    (CURRENT_DATE - 1, 'user-1', 'engineering', 'gpt-4o-mini', 100, 50000, 20000, 0.045),
    (CURRENT_DATE - 1, 'user-1', 'engineering', 'claude-3-haiku', 50, 25000, 10000, 0.019),
    (CURRENT_DATE - 1, 'user-2', 'data-science', 'gpt-4o', 20, 10000, 5000, 0.075),
    (CURRENT_DATE, 'user-1', 'engineering', 'gpt-4o-mini', 25, 12500, 5000, 0.011),
    (CURRENT_DATE, 'user-1', 'engineering', 'grok-3', 10, 5000, 2000, 0.007)
ON CONFLICT DO NOTHING;

-- Done
SELECT 'AI Gateway database initialized successfully' as status;
