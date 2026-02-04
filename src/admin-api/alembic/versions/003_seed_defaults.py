"""Seed default teams, budgets, and platform settings.

Revision ID: 003
Revises: 002
Create Date: 2026-02-05

"""
from typing import Sequence, Union

from alembic import op

revision: str = '003'
down_revision: Union[str, None] = '002'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Seed default teams
    op.execute("""
        INSERT INTO teams (name, description, monthly_budget, default_model)
        VALUES
            ('engineering', 'Engineering team', 500.00, 'gpt-4o-mini'),
            ('data-science', 'Data Science team', 1000.00, 'gpt-4o'),
            ('product', 'Product team', 250.00, 'claude-haiku-4.5')
        ON CONFLICT (name) DO NOTHING
    """)

    # Seed default platform settings
    op.execute("""
        INSERT INTO platform_settings (key, value)
        VALUES
            ('general', '{"platform_name": "AI Gateway", "default_model": "gpt-4o-mini", "max_tokens_default": 4096}'),
            ('security', '{"require_api_key": true, "allowed_origins": ["*"], "rate_limit_enabled": true}'),
            ('notifications', '{"budget_alerts": true, "error_alerts": true, "slack_webhook": null}')
        ON CONFLICT (key) DO UPDATE SET
            value = EXCLUDED.value,
            updated_at = CURRENT_TIMESTAMP
    """)

    # Seed default routing policies
    op.execute("""
        INSERT INTO routing_policies (name, description, priority, condition, action)
        VALUES
            ('budget-fallback', 'Route to cheaper models when budget is low', 100,
             'context.budget_remaining < 10.0', 'select_model(tier=budget)'),
            ('latency-sla', 'Enforce latency SLA requirements', 90,
             'context.latency_sla_ms < 2000', 'select_model(latency_ms < context.latency_sla_ms)'),
            ('error-circuit-breaker', 'Avoid models with high error rates', 80,
             'resource.error_rate > 0.05', 'forbid')
        ON CONFLICT (name) DO NOTHING
    """)


def downgrade() -> None:
    op.execute("DELETE FROM routing_policies WHERE name IN ('budget-fallback', 'latency-sla', 'error-circuit-breaker')")
    op.execute("DELETE FROM platform_settings WHERE key IN ('general', 'security', 'notifications')")
    op.execute("DELETE FROM teams WHERE name IN ('engineering', 'data-science', 'product')")
