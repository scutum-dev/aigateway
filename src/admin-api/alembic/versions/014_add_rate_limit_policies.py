"""Add granular rate limit policies and rate limit event tracking.

Revision ID: 014
Revises: 013
Create Date: 2026-02-18

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "014"
down_revision: Union[str, None] = "013"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS rate_limit_policies (
            id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
            name VARCHAR(255) NOT NULL,
            description TEXT,
            scope VARCHAR(50) NOT NULL,
            scope_value VARCHAR(255),
            rpm_limit INTEGER,
            tpm_limit INTEGER,
            rpd_limit INTEGER,
            tpd_limit INTEGER,
            burst_multiplier DECIMAL(3,1) DEFAULT 1.5,
            burst_window_seconds INTEGER DEFAULT 10,
            priority INTEGER DEFAULT 0,
            is_active BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
        )
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS rate_limit_events (
            id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
            policy_id UUID REFERENCES rate_limit_policies(id) ON DELETE SET NULL,
            scope VARCHAR(50),
            scope_value VARCHAR(255),
            limit_type VARCHAR(20),
            current_value INTEGER,
            limit_value INTEGER,
            action VARCHAR(20),
            created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
        )
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_rate_limit_events_created
        ON rate_limit_events(created_at)
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS rate_limit_events CASCADE")
    op.execute("DROP TABLE IF EXISTS rate_limit_policies CASCADE")
