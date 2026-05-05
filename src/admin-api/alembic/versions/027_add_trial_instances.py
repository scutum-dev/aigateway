"""Add trial_instances table for the hosted free-trial funnel.

Revision ID: 027
Revises: 026
Create Date: 2026-05-05

Each row tracks one user-facing trial:
- the Fly app we provisioned for them (one app per trial),
- the subdomain pointing at it,
- where the trial sits in its lifecycle.

The signup router writes a 'pending_verification' row when someone fills
the form. Email verification flips it to 'provisioning'. The
trial-provisioner picks up 'provisioning' rows, creates the Fly app,
sets fly_app_name + fqdn, marks it 'active', stamps expires_at = now()+30d.
The lifecycle scheduler scans (status, expires_at) to send 3-day reminders
and to delete past-expiry trials. After teardown the row is kept with
status='deleted' for funnel attribution; nothing else points at it.
"""

from typing import Sequence, Union

from alembic import op

revision: str = "027"
down_revision: Union[str, None] = "026"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS trial_instances (
            id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
            user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            org_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
            status TEXT NOT NULL
                CHECK (status IN ('pending_verification', 'provisioning', 'active', 'expired', 'deleted', 'failed')),
            fly_app_name TEXT,
            fqdn TEXT,
            verification_token TEXT,
            verification_expires_at TIMESTAMPTZ,
            provision_error TEXT,
            reminder_email_sent_at TIMESTAMPTZ,
            created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
            verified_at TIMESTAMPTZ,
            activated_at TIMESTAMPTZ,
            expires_at TIMESTAMPTZ,
            deleted_at TIMESTAMPTZ
        )
    """)

    # Scheduler scans by (status, expires_at) — past-expiry sweep + 3-day reminder window.
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_trial_instances_status_expires
        ON trial_instances (status, expires_at)
        WHERE status IN ('active', 'provisioning')
    """)

    # One active trial per user. Lifted only when status flips to 'deleted' or 'expired'.
    op.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS idx_trial_instances_one_per_user
        ON trial_instances (user_id)
        WHERE status NOT IN ('deleted', 'expired', 'failed')
    """)

    # Reverse lookup by Fly app name (provisioner reconciliation, scheduler delete).
    op.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS idx_trial_instances_fly_app_name
        ON trial_instances (fly_app_name)
        WHERE fly_app_name IS NOT NULL
    """)

    # Verification-token lookup must be cheap; tokens are random UUIDs.
    op.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS idx_trial_instances_verification_token
        ON trial_instances (verification_token)
        WHERE verification_token IS NOT NULL
    """)

    # Per-IP rate-limit accounting for /api/v1/trial-signup. A row per attempt
    # (success or failure). Lets us count attempts in a rolling window without
    # needing Redis on the marketing VM.
    op.execute("""
        CREATE TABLE IF NOT EXISTS trial_signup_attempts (
            id BIGSERIAL PRIMARY KEY,
            source_ip TEXT NOT NULL,
            email TEXT,
            success BOOLEAN NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_trial_signup_attempts_ip_time
        ON trial_signup_attempts (source_ip, created_at DESC)
    """)


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_trial_signup_attempts_ip_time")
    op.execute("DROP TABLE IF EXISTS trial_signup_attempts CASCADE")
    op.execute("DROP INDEX IF EXISTS idx_trial_instances_verification_token")
    op.execute("DROP INDEX IF EXISTS idx_trial_instances_fly_app_name")
    op.execute("DROP INDEX IF EXISTS idx_trial_instances_one_per_user")
    op.execute("DROP INDEX IF EXISTS idx_trial_instances_status_expires")
    op.execute("DROP TABLE IF EXISTS trial_instances CASCADE")
