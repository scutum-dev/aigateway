"""Add model access tiers and access request governance.

Revision ID: 015
Revises: 014
Create Date: 2026-02-18

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "015"
down_revision: Union[str, None] = "014"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS model_access_tiers (
            id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
            name VARCHAR(100) UNIQUE NOT NULL,
            description TEXT,
            requires_approval BOOLEAN DEFAULT FALSE,
            requires_justification BOOLEAN DEFAULT FALSE,
            max_grant_duration_days INTEGER,
            models TEXT[] DEFAULT '{}',
            created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
        )
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS model_access_requests (
            id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
            user_id VARCHAR(255) NOT NULL,
            team_id UUID,
            model_pattern VARCHAR(255) NOT NULL,
            tier_id UUID REFERENCES model_access_tiers(id),
            justification TEXT,
            status VARCHAR(50) DEFAULT 'pending',
            reviewer VARCHAR(255),
            review_comment TEXT,
            granted_at TIMESTAMPTZ,
            expires_at TIMESTAMPTZ,
            created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Seed default tiers
    op.execute("""
        INSERT INTO model_access_tiers (name, requires_approval, requires_justification, max_grant_duration_days, models)
        VALUES
            ('standard', false, false, NULL, '{gpt-4o-mini,claude-haiku-4.5,gemini-2.5-flash}'),
            ('premium', true, true, 90, '{gpt-5,claude-sonnet-4.5,gemini-2.5-pro,o3}'),
            ('experimental', true, true, 30, '{gpt-5.2,o3-pro,grok-4-heavy}')
        ON CONFLICT DO NOTHING
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS model_access_requests CASCADE")
    op.execute("DROP TABLE IF EXISTS model_access_tiers CASCADE")
