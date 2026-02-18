"""Add playground sessions table for saving multi-model comparison sessions.

Revision ID: 021
Revises: 020
Create Date: 2026-02-18

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "021"
down_revision: Union[str, None] = "020"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS playground_sessions (
            id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
            name VARCHAR(255),
            prompt TEXT NOT NULL,
            models TEXT[] NOT NULL,
            settings JSONB,
            results JSONB,
            created_by VARCHAR(255),
            is_public BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
        )
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_playground_sessions_created_by
        ON playground_sessions(created_by)
    """)


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_playground_sessions_created_by")
    op.execute("DROP TABLE IF EXISTS playground_sessions CASCADE")
