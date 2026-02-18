"""Add A/B tests and test snapshots tables.

Revision ID: 018
Revises: 017
Create Date: 2026-02-18

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "018"
down_revision: Union[str, None] = "017"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS ab_tests (
            id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
            name VARCHAR(255) UNIQUE NOT NULL,
            status VARCHAR(50) DEFAULT 'draft',
            base_model VARCHAR(255) NOT NULL,
            variant_model VARCHAR(255) NOT NULL,
            traffic_split_percent INTEGER DEFAULT 10,
            success_metric VARCHAR(100) DEFAULT 'cost_efficiency',
            promotion_threshold JSONB,
            rollback_threshold JSONB,
            auto_promote BOOLEAN DEFAULT FALSE,
            auto_rollback BOOLEAN DEFAULT TRUE,
            started_at TIMESTAMPTZ,
            completed_at TIMESTAMPTZ,
            created_by VARCHAR(255),
            created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
        )
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS ab_test_snapshots (
            id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
            test_id UUID REFERENCES ab_tests(id) ON DELETE CASCADE,
            snapshot_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
            base_metrics JSONB,
            variant_metrics JSONB,
            recommendation VARCHAR(50)
        )
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_ab_test_snapshots_test_id
        ON ab_test_snapshots(test_id, snapshot_at DESC)
    """)


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_ab_test_snapshots_test_id")
    op.execute("DROP TABLE IF EXISTS ab_test_snapshots CASCADE")
    op.execute("DROP TABLE IF EXISTS ab_tests CASCADE")
