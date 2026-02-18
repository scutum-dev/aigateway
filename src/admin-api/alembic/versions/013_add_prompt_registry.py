"""Add prompt registry tables for template management, usage tracking, and approvals.

Revision ID: 013
Revises: 012
Create Date: 2026-02-18

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "013"
down_revision: Union[str, None] = "012"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS prompt_templates (
            id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
            name VARCHAR(255) NOT NULL,
            slug VARCHAR(255) NOT NULL,
            description TEXT,
            category VARCHAR(100),
            template_text TEXT NOT NULL,
            variables JSONB DEFAULT '[]',
            version INTEGER NOT NULL DEFAULT 1,
            is_current BOOLEAN DEFAULT TRUE,
            status VARCHAR(50) DEFAULT 'draft',
            team_id UUID,
            model_hint VARCHAR(255),
            tags TEXT[] DEFAULT '{}',
            created_by VARCHAR(255),
            approved_by VARCHAR(255),
            approved_at TIMESTAMPTZ,
            is_active BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(slug, version)
        )
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS prompt_template_usage (
            id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
            template_id UUID REFERENCES prompt_templates(id) ON DELETE CASCADE,
            template_version INTEGER,
            user_id VARCHAR(255),
            model VARCHAR(255),
            input_tokens INTEGER,
            output_tokens INTEGER,
            cost DECIMAL(20, 10),
            latency_ms INTEGER,
            status VARCHAR(50) DEFAULT 'success',
            created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
        )
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS prompt_approvals (
            id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
            template_id UUID REFERENCES prompt_templates(id) ON DELETE CASCADE,
            template_version INTEGER NOT NULL,
            requested_by VARCHAR(255) NOT NULL,
            reviewer VARCHAR(255),
            status VARCHAR(50) DEFAULT 'pending',
            comment TEXT,
            requested_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
            reviewed_at TIMESTAMPTZ
        )
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS prompt_approvals CASCADE")
    op.execute("DROP TABLE IF EXISTS prompt_template_usage CASCADE")
    op.execute("DROP TABLE IF EXISTS prompt_templates CASCADE")
