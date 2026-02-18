"""Add event system tables for subscriptions and event log.

Revision ID: 020
Revises: 019
Create Date: 2026-02-18

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "020"
down_revision: Union[str, None] = "019"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS event_subscriptions (
            id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
            name VARCHAR(255) NOT NULL,
            event_types TEXT[] NOT NULL,
            channel VARCHAR(50) NOT NULL,
            config JSONB NOT NULL,
            filters JSONB,
            is_active BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
        )
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS event_log (
            id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
            event_type VARCHAR(100) NOT NULL,
            payload JSONB NOT NULL,
            source_service VARCHAR(100),
            created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
        )
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_event_log_type
        ON event_log(event_type)
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_event_log_created
        ON event_log(created_at DESC)
    """)


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_event_log_created")
    op.execute("DROP INDEX IF EXISTS idx_event_log_type")
    op.execute("DROP TABLE IF EXISTS event_log CASCADE")
    op.execute("DROP TABLE IF EXISTS event_subscriptions CASCADE")
