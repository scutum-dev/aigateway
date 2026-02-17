"""Add updated_at column to teams table.

Revision ID: 006
Revises: 005
Create Date: 2026-02-17

"""

from typing import Sequence, Union

from alembic import op

revision: str = "006"
down_revision: Union[str, None] = "005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                          WHERE table_name = 'teams' AND column_name = 'updated_at') THEN
                ALTER TABLE teams ADD COLUMN updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP;
            END IF;
        END $$;
    """)


def downgrade() -> None:
    op.execute("ALTER TABLE teams DROP COLUMN IF EXISTS updated_at")
