"""Add model deprecations table for API versioning and deprecation tracking.

Revision ID: 022
Revises: 021
Create Date: 2026-02-18

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "022"
down_revision: Union[str, None] = "021"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS model_deprecations (
            id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
            model_name VARCHAR(255) UNIQUE NOT NULL,
            replacement_model VARCHAR(255),
            deprecation_date DATE,
            sunset_date DATE,
            message TEXT,
            created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
        )
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS model_deprecations CASCADE")
