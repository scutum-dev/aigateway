"""Add licenses table for the 30-day trial / paid license enforcement.

Revision ID: 026
Revises: 025
Create Date: 2026-05-03

Stores Ed25519-signed JWT license tokens. admin-api validates each token
against the bundled public key on startup and refuses to mark expired
licenses as active. Most-recent active row is the operative license.

Customer flow on first deploy:
1. Customer sets LICENSE_KEY env var to the JWT we issued them.
2. admin-api validates on startup, inserts a row with is_active=true.
3. Subsequent boots read from the table; LICENSE_KEY is fallback only.
4. Customer can post a refreshed license to /api/v1/license/activate to
   extend without restart.
"""

from typing import Sequence, Union

from alembic import op

revision: str = "026"
down_revision: Union[str, None] = "025"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS licenses (
            id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
            license_key TEXT NOT NULL,
            customer_id TEXT NOT NULL,
            customer_email TEXT NOT NULL,
            company TEXT,
            tier TEXT NOT NULL
                CHECK (tier IN ('trial','team','business','enterprise')),
            issued_at TIMESTAMPTZ NOT NULL,
            expires_at TIMESTAMPTZ NOT NULL,
            features JSONB NOT NULL DEFAULT '{}'::jsonb,
            is_active BOOLEAN NOT NULL DEFAULT TRUE,
            activated_by TEXT,
            created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
        )
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_licenses_active_expires
        ON licenses (is_active, expires_at DESC)
    """)
    op.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS idx_licenses_key_unique
        ON licenses (license_key)
    """)


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_licenses_key_unique")
    op.execute("DROP INDEX IF EXISTS idx_licenses_active_expires")
    op.execute("DROP TABLE IF EXISTS licenses CASCADE")
