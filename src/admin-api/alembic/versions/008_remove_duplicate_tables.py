"""Remove tables now managed by LiteLLM and Agent Gateway.

Drop: team_members, budgets, routing_policies, model_routing_config,
      routing_decisions, teams.

Revision ID: 008
Revises: 007
Create Date: 2026-02-17

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "008"
down_revision: Union[str, None] = "007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("DROP TABLE IF EXISTS team_members CASCADE")
    op.execute("DROP TABLE IF EXISTS budgets CASCADE")
    op.execute("DROP TABLE IF EXISTS routing_policies CASCADE")
    op.execute("DROP TABLE IF EXISTS model_routing_config CASCADE")
    op.execute("DROP TABLE IF EXISTS routing_decisions CASCADE")
    op.execute("DROP TABLE IF EXISTS teams CASCADE")
    op.execute("DROP INDEX IF EXISTS idx_routing_decisions_timestamp")
    op.execute("DROP INDEX IF EXISTS idx_routing_decisions_user")
    op.execute("DELETE FROM platform_settings WHERE key = 'enable_routing_policies'")


def downgrade() -> None:
    op.execute("""
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
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_routing_decisions_timestamp ON routing_decisions(timestamp)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_routing_decisions_user ON routing_decisions(user_id)")

    op.execute("""
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
        )
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS teams (
            id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
            name VARCHAR(255) UNIQUE NOT NULL,
            description TEXT,
            monthly_budget DECIMAL(20, 10),
            default_model VARCHAR(255),
            is_active BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
        )
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS team_members (
            team_id UUID REFERENCES teams(id) ON DELETE CASCADE,
            user_id VARCHAR(255) NOT NULL,
            role VARCHAR(50) DEFAULT 'member',
            created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (team_id, user_id)
        )
    """)

    op.execute("""
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
        )
    """)

    op.execute("""
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
        )
    """)

    op.execute("INSERT INTO platform_settings (key, value) VALUES ('enable_routing_policies', 'true') ON CONFLICT DO NOTHING")
