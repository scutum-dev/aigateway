"""Add audit_logs and request_logs tables.

Revision ID: 011
Revises: 010
Create Date: 2026-02-18

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "011"
down_revision: Union[str, None] = "010"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS audit_logs (
            id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
            timestamp TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
            actor_id VARCHAR(255) NOT NULL,
            actor_email VARCHAR(255),
            actor_ip VARCHAR(45),
            org_id UUID,
            action VARCHAR(100) NOT NULL,
            resource_type VARCHAR(100) NOT NULL,
            resource_id VARCHAR(255),
            resource_name VARCHAR(255),
            changes JSONB DEFAULT '{}',
            request_metadata JSONB DEFAULT '{}',
            created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
        )
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_audit_logs_timestamp
        ON audit_logs(timestamp DESC)
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_audit_logs_actor_id
        ON audit_logs(actor_id)
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_audit_logs_org_id
        ON audit_logs(org_id)
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_audit_logs_resource
        ON audit_logs(resource_type, resource_id)
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_audit_logs_action
        ON audit_logs(action)
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS request_logs (
            id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
            request_id VARCHAR(255),
            user_id VARCHAR(255),
            team_id VARCHAR(255),
            model VARCHAR(255),
            prompt_text TEXT,
            response_text TEXT,
            is_redacted BOOLEAN DEFAULT FALSE,
            tokens_in INTEGER,
            tokens_out INTEGER,
            cost DECIMAL(20,10),
            latency_ms INTEGER,
            created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
        )
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS request_logs CASCADE")
    op.execute("DROP TABLE IF EXISTS audit_logs CASCADE")
