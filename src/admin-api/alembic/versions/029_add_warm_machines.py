"""Add warm_machines pool table for fast trial provisioning.

Revision ID: 029
Revises: 028
Create Date: 2026-05-06

The trial-provisioner runs a background pool of pre-warmed Fly machines:
each one has been booted once (dockerd + golden-image load + alembic +
LiteLLM db push) and then stopped. When a user signs up we claim a 'ready'
row, PATCH per-trial env vars (SCUTUM_API_KEY, BOOTSTRAP_TOKEN,
JWT_SECRET_KEY) onto the Fly machine, start it, and the user is in the
dashboard in ~1 min instead of the ~10 min cold start.

Status flow:
    NEW                                       (lifecycle scheduler reaps these)
     │
     ▼
  warming  ──── warmup failed ────►  failed   (recycler destroys + retries)
     │
     │  warmup succeeded + machine stopped
     ▼
   ready  ──── stale (>14d unclaimed) ────►  recycled
     │
     │  user signs up
     ▼
  claimed                                     (FK to trial_instances; on trial
                                               teardown the row stays as
                                               historical record but the Fly
                                               app is destroyed)

The recycler reaps:
  - 'warming' rows older than 30 min (stuck warmer)
  - 'ready'   rows older than 14 days (idle volume cost adds up)
  - 'failed'  rows after a backoff retry has been kicked off elsewhere
"""

from typing import Sequence, Union

from alembic import op

revision: str = "029"
down_revision: Union[str, None] = "028"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS warm_machines (
            id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
            fly_app_name TEXT NOT NULL UNIQUE,
            fly_machine_id TEXT,
            fly_volume_id TEXT,
            region TEXT NOT NULL,
            status TEXT NOT NULL
                CHECK (status IN ('warming', 'ready', 'claimed', 'failed', 'recycled')),
            created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
            warmed_at TIMESTAMPTZ,
            claimed_at TIMESTAMPTZ,
            claimed_by_trial_id UUID REFERENCES trial_instances(id) ON DELETE SET NULL,
            last_warm_error TEXT,
            recycle_after TIMESTAMPTZ
        )
    """)

    # Pool warmer's hot path: count + select ready by region.
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_warm_machines_status_region
        ON warm_machines (status, region)
        WHERE status IN ('warming', 'ready')
    """)

    # Reaper sweep — picks up rows past their recycle deadline.
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_warm_machines_recycle
        ON warm_machines (recycle_after)
        WHERE status = 'ready' AND recycle_after IS NOT NULL
    """)


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_warm_machines_recycle")
    op.execute("DROP INDEX IF EXISTS idx_warm_machines_status_region")
    op.execute("DROP TABLE IF EXISTS warm_machines CASCADE")
