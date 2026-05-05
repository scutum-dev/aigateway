"""Replace cost_tracking_daily table with a view over LiteLLM_SpendLogs.

Revision ID: 007
Revises: 006
Create Date: 2026-02-17

The view depends on `"LiteLLM_SpendLogs"`, which LiteLLM creates at runtime
via Prisma. On a fresh deploy admin-api may run migrations before LiteLLM
has booted, so the table does not yet exist. We skip view creation in that
case rather than crash the migration; admin-api retries via a startup
background task (see `_ensure_cost_view` in main.py).
"""

import logging
from typing import Sequence, Union

from alembic import op

revision: str = "007"
down_revision: Union[str, None] = "006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

logger = logging.getLogger("alembic.runtime.migration")


COST_VIEW_SQL = """
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
"""


def upgrade() -> None:
    bind = op.get_bind()

    # Type-agnostic drop: DROP VIEW IF EXISTS errors out when the object is
    # a TABLE (and vice-versa) — Postgres won't ignore the wrong-type case.
    # Earlier migrations created cost_tracking_daily as a table, so on a
    # fresh DB we must drop the table form here. Use a DO block that picks
    # the right DROP based on information_schema.
    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM information_schema.tables
                       WHERE table_schema = 'public'
                         AND table_name = 'cost_tracking_daily'
                         AND table_type = 'BASE TABLE') THEN
                EXECUTE 'DROP TABLE cost_tracking_daily CASCADE';
            END IF;
            IF EXISTS (SELECT 1 FROM information_schema.views
                       WHERE table_schema = 'public'
                         AND table_name = 'cost_tracking_daily') THEN
                EXECUTE 'DROP VIEW cost_tracking_daily CASCADE';
            END IF;
        END $$
    """)
    op.execute("DROP INDEX IF EXISTS idx_cost_tracking_date")
    op.execute("DROP INDEX IF EXISTS idx_cost_tracking_user")
    op.execute("DROP INDEX IF EXISTS idx_cost_tracking_team")
    op.execute("DROP INDEX IF EXISTS idx_cost_tracking_model")

    spendlogs_exists = bind.exec_driver_sql("SELECT to_regclass('public.\"LiteLLM_SpendLogs\"') IS NOT NULL").scalar()

    if not spendlogs_exists:
        logger.warning(
            'Skipping cost_tracking_daily view: "LiteLLM_SpendLogs" not yet created. '
            "Admin-api will create it once LiteLLM has initialised the table."
        )
        return

    # Savepoint isolates a column-mismatch (LiteLLM schema drift across versions)
    # so it doesn't abort the migration's outer transaction and stall alembic_version.
    try:
        with bind.begin_nested():
            bind.exec_driver_sql(COST_VIEW_SQL)
    except Exception as e:
        logger.warning(
            "Skipping cost_tracking_daily view (LiteLLM_SpendLogs schema mismatch?): %s. "
            "Admin-api will retry on startup.",
            e,
        )


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
