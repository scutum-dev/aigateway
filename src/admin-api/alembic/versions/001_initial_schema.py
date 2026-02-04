"""Initial schema for admin-api tables.

Revision ID: 001
Revises:
Create Date: 2026-02-05

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = '001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Model routing configuration
    op.execute("""
        CREATE TABLE IF NOT EXISTS model_routing_config (
            model_id VARCHAR(255) PRIMARY KEY,
            provider VARCHAR(255),
            tier VARCHAR(50),
            cost_per_1k_input DECIMAL(20, 10),
            cost_per_1k_output DECIMAL(20, 10),
            supports_streaming BOOLEAN DEFAULT TRUE,
            supports_function_calling BOOLEAN DEFAULT FALSE,
            supports_vision BOOLEAN DEFAULT FALSE,
            default_latency_sla_ms INTEGER DEFAULT 5000,
            is_active BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Add missing columns if table already existed
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                          WHERE table_name = 'model_routing_config' AND column_name = 'supports_vision') THEN
                ALTER TABLE model_routing_config ADD COLUMN supports_vision BOOLEAN DEFAULT FALSE;
            END IF;
            IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                          WHERE table_name = 'model_routing_config' AND column_name = 'is_active') THEN
                ALTER TABLE model_routing_config ADD COLUMN is_active BOOLEAN DEFAULT TRUE;
            END IF;
        END $$;
    """)

    # Cost tracking daily
    op.execute("""
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
        )
    """)

    # Routing policies
    op.execute("""
        CREATE TABLE IF NOT EXISTS routing_policies (
            id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
            name VARCHAR(255) UNIQUE NOT NULL,
            description TEXT,
            priority INTEGER DEFAULT 0,
            condition TEXT NOT NULL,
            action TEXT NOT NULL,
            is_active BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Budgets
    op.execute("""
        CREATE TABLE IF NOT EXISTS budgets (
            id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
            name VARCHAR(255) NOT NULL,
            entity_type VARCHAR(50) NOT NULL,
            entity_id VARCHAR(255),
            monthly_limit DECIMAL(20, 10) NOT NULL,
            current_spend DECIMAL(20, 10) DEFAULT 0,
            soft_limit_percent DECIMAL(5, 2) DEFAULT 80,
            hard_limit_percent DECIMAL(5, 2) DEFAULT 100,
            alert_email VARCHAR(255),
            is_active BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Teams
    op.execute("""
        CREATE TABLE IF NOT EXISTS teams (
            id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
            name VARCHAR(255) UNIQUE NOT NULL,
            description TEXT,
            monthly_budget DECIMAL(20, 10),
            default_model VARCHAR(255),
            is_active BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Team members
    op.execute("""
        CREATE TABLE IF NOT EXISTS team_members (
            team_id UUID REFERENCES teams(id) ON DELETE CASCADE,
            user_id VARCHAR(255) NOT NULL,
            role VARCHAR(50) DEFAULT 'member',
            created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (team_id, user_id)
        )
    """)

    # MCP servers
    op.execute("""
        CREATE TABLE IF NOT EXISTS mcp_servers (
            id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
            name VARCHAR(255) UNIQUE NOT NULL,
            server_type VARCHAR(50) NOT NULL,
            command TEXT,
            url TEXT,
            env JSONB,
            is_active BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Platform settings
    op.execute("""
        CREATE TABLE IF NOT EXISTS platform_settings (
            key VARCHAR(255) PRIMARY KEY,
            value JSONB NOT NULL,
            updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Workflow definitions
    op.execute("""
        CREATE TABLE IF NOT EXISTS workflow_definitions (
            id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
            name VARCHAR(255) UNIQUE NOT NULL,
            version VARCHAR(50) DEFAULT '1.0.0',
            template_type VARCHAR(100),
            description TEXT,
            graph_definition JSONB,
            input_schema JSONB,
            is_active BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
        )
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS workflow_definitions")
    op.execute("DROP TABLE IF EXISTS platform_settings")
    op.execute("DROP TABLE IF EXISTS mcp_servers")
    op.execute("DROP TABLE IF EXISTS team_members")
    op.execute("DROP TABLE IF EXISTS teams")
    op.execute("DROP TABLE IF EXISTS budgets")
    op.execute("DROP TABLE IF EXISTS routing_policies")
    op.execute("DROP TABLE IF EXISTS cost_tracking_daily")
    op.execute("DROP TABLE IF EXISTS model_routing_config")
