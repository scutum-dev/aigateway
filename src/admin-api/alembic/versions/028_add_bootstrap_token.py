"""Add bootstrap_token + api_key + jwt_secret columns to trial_instances.

Revision ID: 028
Revises: 027
Create Date: 2026-05-06

Trial-provisioner generates these per-trial and injects them as Fly machine
env vars (SCUTUM_API_KEY / BOOTSTRAP_TOKEN / JWT_SECRET_KEY) so install.sh
honours them instead of randomising. Storing the values on the row gives:
- the /api/v1/trial-signup/{id}/status endpoint a way to surface the
  bootstrap URL when the trial flips to 'active',
- recovery: a provisioner restart mid-flow can resume with the same tokens
  rather than rotating them and stranding the in-flight Fly machine env,
- audit: customer-support can look up which credential the user has.

All three are nullable so existing rows are untouched.
"""

from typing import Sequence, Union

from alembic import op

revision: str = "028"
down_revision: Union[str, None] = "027"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        ALTER TABLE trial_instances
            ADD COLUMN IF NOT EXISTS api_key TEXT,
            ADD COLUMN IF NOT EXISTS bootstrap_token TEXT,
            ADD COLUMN IF NOT EXISTS jwt_secret TEXT
    """)


def downgrade() -> None:
    op.execute("""
        ALTER TABLE trial_instances
            DROP COLUMN IF EXISTS jwt_secret,
            DROP COLUMN IF EXISTS bootstrap_token,
            DROP COLUMN IF EXISTS api_key
    """)
