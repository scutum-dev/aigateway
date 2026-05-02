"""Add demo_requests for the landing page Book-a-Demo flow.

Revision ID: 025
Revises: 024
Create Date: 2026-05-02

"""

from typing import Sequence, Union

from alembic import op

revision: str = "025"
down_revision: Union[str, None] = "024"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS demo_requests (
            id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
            name TEXT NOT NULL,
            work_email TEXT NOT NULL,
            company TEXT,
            role TEXT,
            team_size TEXT,
            use_case TEXT,
            preferred_window JSONB,
            calcom_booking_id TEXT,
            calcom_meeting_url TEXT,
            source_ip TEXT,
            user_agent TEXT,
            status TEXT NOT NULL DEFAULT 'new'
                CHECK (status IN ('new','scheduled','contacted','closed')),
            notes TEXT,
            created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
        )
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_demo_requests_status_created
        ON demo_requests (status, created_at DESC)
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_demo_requests_email
        ON demo_requests (work_email)
    """)


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_demo_requests_email")
    op.execute("DROP INDEX IF EXISTS idx_demo_requests_status_created")
    op.execute("DROP TABLE IF EXISTS demo_requests CASCADE")
