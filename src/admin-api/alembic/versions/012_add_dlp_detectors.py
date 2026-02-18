"""Add DLP content detectors, guardrail-detector linking, and team content policies.

Revision ID: 012
Revises: 011
Create Date: 2026-02-18

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "012"
down_revision: Union[str, None] = "011"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS content_detectors (
            id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
            name VARCHAR(255) UNIQUE NOT NULL,
            description TEXT,
            detector_type VARCHAR(50) NOT NULL,
            config JSONB NOT NULL DEFAULT '{}',
            is_active BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
        )
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS guardrail_detectors (
            guardrail_config_id UUID REFERENCES guardrail_configs(id) ON DELETE CASCADE,
            detector_id UUID REFERENCES content_detectors(id) ON DELETE CASCADE,
            priority INTEGER DEFAULT 0,
            PRIMARY KEY (guardrail_config_id, detector_id)
        )
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS team_content_policies (
            id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
            team_id UUID NOT NULL,
            policy_type VARCHAR(50) NOT NULL,
            config JSONB NOT NULL DEFAULT '{}',
            is_active BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(team_id, policy_type)
        )
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS team_content_policies CASCADE")
    op.execute("DROP TABLE IF EXISTS guardrail_detectors CASCADE")
    op.execute("DROP TABLE IF EXISTS content_detectors CASCADE")
