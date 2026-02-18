"""Add SLA definitions, provider health metrics, violations, and failover rules.

Revision ID: 017
Revises: 016
Create Date: 2026-02-18

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "017"
down_revision: Union[str, None] = "016"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS sla_definitions (
            id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
            name VARCHAR(255) NOT NULL,
            provider VARCHAR(100),
            model_pattern VARCHAR(255),
            target_p50_ms INTEGER,
            target_p95_ms INTEGER,
            target_p99_ms INTEGER,
            target_error_rate DECIMAL(5,4) DEFAULT 0.01,
            target_availability DECIMAL(5,4) DEFAULT 0.999,
            evaluation_window_minutes INTEGER DEFAULT 60,
            alert_channels TEXT[] DEFAULT '{}',
            is_active BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
        )
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS provider_health_metrics (
            id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
            provider VARCHAR(100) NOT NULL,
            model VARCHAR(255) NOT NULL,
            bucket_start TIMESTAMPTZ NOT NULL,
            request_count INTEGER DEFAULT 0,
            error_count INTEGER DEFAULT 0,
            p50_latency_ms INTEGER,
            p95_latency_ms INTEGER,
            p99_latency_ms INTEGER,
            avg_latency_ms INTEGER,
            total_tokens INTEGER DEFAULT 0,
            total_cost DECIMAL(20, 10) DEFAULT 0,
            created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(provider, model, bucket_start)
        )
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS sla_violations (
            id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
            sla_definition_id UUID REFERENCES sla_definitions(id) ON DELETE CASCADE,
            provider VARCHAR(100),
            model VARCHAR(255),
            violation_type VARCHAR(50),
            threshold_value DECIMAL(10, 4),
            actual_value DECIMAL(10, 4),
            alert_sent BOOLEAN DEFAULT FALSE,
            resolved_at TIMESTAMPTZ,
            created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
        )
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS provider_failover_rules (
            id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
            primary_model VARCHAR(255) NOT NULL,
            fallback_model VARCHAR(255) NOT NULL,
            trigger_condition VARCHAR(50),
            trigger_threshold DECIMAL(10, 4),
            cooldown_minutes INTEGER DEFAULT 15,
            is_active BOOLEAN DEFAULT TRUE,
            last_triggered_at TIMESTAMPTZ,
            created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
        )
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_health_metrics_provider
        ON provider_health_metrics(provider, model, bucket_start)
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_sla_violations_created
        ON sla_violations(created_at)
    """)


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_sla_violations_created")
    op.execute("DROP INDEX IF EXISTS idx_health_metrics_provider")
    op.execute("DROP TABLE IF EXISTS provider_failover_rules CASCADE")
    op.execute("DROP TABLE IF EXISTS sla_violations CASCADE")
    op.execute("DROP TABLE IF EXISTS provider_health_metrics CASCADE")
    op.execute("DROP TABLE IF EXISTS sla_definitions CASCADE")
