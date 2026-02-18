"""Replace cost_tracking_daily table with a view over LiteLLM_SpendLogs.

Revision ID: 007
Revises: 006
Create Date: 2026-02-17

"""

from typing import Sequence, Union

from alembic import op

revision: str = "007"
down_revision: Union[str, None] = "006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Drop as view first (in case a previous run created it), then as table
    op.execute("DROP VIEW IF EXISTS cost_tracking_daily CASCADE")
    op.execute("DROP TABLE IF EXISTS cost_tracking_daily CASCADE")
    op.execute("DROP INDEX IF EXISTS idx_cost_tracking_date")
    op.execute("DROP INDEX IF EXISTS idx_cost_tracking_user")
    op.execute("DROP INDEX IF EXISTS idx_cost_tracking_team")
    op.execute("DROP INDEX IF EXISTS idx_cost_tracking_model")

    op.execute("""
        CREATE OR REPLACE VIEW cost_tracking_daily AS
        SELECT
            "startTime"::date  AS date,
            COALESCE("user", '')  AS user_id,
            COALESCE(team_id, '') AS team_id,
            model,
            custom_llm_provider   AS provider,
            COUNT(*)              AS request_count,
            CAST(SUM(prompt_tokens) AS BIGINT)     AS input_tokens,
            CAST(SUM(completion_tokens) AS BIGINT)  AS output_tokens,
            SUM(spend)            AS total_cost
        FROM "LiteLLM_SpendLogs"
        GROUP BY "startTime"::date, "user", team_id, model, custom_llm_provider
    """)


def downgrade() -> None:
    op.execute("DROP VIEW IF EXISTS cost_tracking_daily")

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
    op.execute("CREATE INDEX idx_cost_tracking_date ON cost_tracking_daily(date)")
    op.execute("CREATE INDEX idx_cost_tracking_user ON cost_tracking_daily(user_id)")
    op.execute("CREATE INDEX idx_cost_tracking_team ON cost_tracking_daily(team_id)")
    op.execute("CREATE INDEX idx_cost_tracking_model ON cost_tracking_daily(model)")
