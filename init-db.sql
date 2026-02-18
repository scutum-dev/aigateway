-- Initialize databases for AI Control Plane Platform
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
-- FinOps view over LiteLLM's native spend logs (LiteLLM creates its own tables separately)
-- =============================================================================

-- cost_tracking_daily is a VIEW backed by LiteLLM_SpendLogs.
-- The Alembic migration (007) creates this view; the definition here is for
-- fresh databases only and will be a no-op if the table/view already exists.
-- NOTE: LiteLLM must create LiteLLM_SpendLogs first, so this CREATE VIEW may
-- fail on a truly fresh DB — the Alembic migration handles the real transition.

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

-- A2A agents configuration
CREATE TABLE IF NOT EXISTS a2a_agents (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    name VARCHAR(255) UNIQUE NOT NULL,
    description TEXT,
    url VARCHAR(2048) NOT NULL,
    skills JSONB DEFAULT '[]',
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
    ('enable_guardrails', 'true'),
    ('maintenance_mode', 'false')
ON CONFLICT DO NOTHING;

-- =============================================================================
-- Guardrails tables
-- =============================================================================

-- Guardrail configuration profiles
CREATE TABLE IF NOT EXISTS guardrail_configs (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    name VARCHAR(255) UNIQUE NOT NULL,
    description TEXT,
    enable_prompt_injection BOOLEAN DEFAULT TRUE,
    prompt_injection_threshold DECIMAL(3, 2) DEFAULT 0.90,
    enable_pii_detection BOOLEAN DEFAULT TRUE,
    pii_action VARCHAR(50) DEFAULT 'anonymize',
    pii_entities TEXT[] DEFAULT '{PERSON,EMAIL_ADDRESS,PHONE_NUMBER,CREDIT_CARD,US_SSN,IBAN_CODE,IP_ADDRESS}',
    enable_toxicity BOOLEAN DEFAULT TRUE,
    toxicity_threshold DECIMAL(3, 2) DEFAULT 0.70,
    banned_topics TEXT[] DEFAULT '{}',
    enable_secrets_detection BOOLEAN DEFAULT TRUE,
    enable_invisible_text BOOLEAN DEFAULT TRUE,
    enable_malicious_urls BOOLEAN DEFAULT TRUE,
    enable_sensitive_output BOOLEAN DEFAULT TRUE,
    mode VARCHAR(50) DEFAULT 'block',
    on_fail VARCHAR(50) DEFAULT 'block',
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- Team-to-guardrail assignment (many-to-many)
-- team_id references LiteLLM team IDs (no FK to local teams table)
CREATE TABLE IF NOT EXISTS team_guardrails (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    team_id UUID NOT NULL,
    guardrail_config_id UUID NOT NULL REFERENCES guardrail_configs(id) ON DELETE CASCADE,
    priority INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(team_id, guardrail_config_id)
);

CREATE INDEX IF NOT EXISTS idx_team_guardrails_team ON team_guardrails(team_id);

-- Guardrail event audit log
CREATE TABLE IF NOT EXISTS guardrail_events (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    event_type VARCHAR(50) NOT NULL,
    scanner_name VARCHAR(100) NOT NULL,
    user_id VARCHAR(255),
    team_id VARCHAR(255),
    model VARCHAR(255),
    risk_score DECIMAL(5, 4),
    action_taken VARCHAR(50) DEFAULT 'blocked',
    details JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_guardrail_events_created ON guardrail_events(created_at);
CREATE INDEX IF NOT EXISTS idx_guardrail_events_team ON guardrail_events(team_id);
CREATE INDEX IF NOT EXISTS idx_guardrail_events_type ON guardrail_events(event_type);

-- Insert default guardrail profile
INSERT INTO guardrail_configs (name, description)
VALUES ('default', 'Default guardrail profile with standard protections')
ON CONFLICT DO NOTHING;

-- Grant permissions on new tables
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO litellm;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO litellm;

-- Done
SELECT 'AI Control Plane database initialized successfully' as status;
