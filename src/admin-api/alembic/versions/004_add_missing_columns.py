"""Add missing columns to mcp_servers and routing_policies.

Revision ID: 004
Revises: 003
Create Date: 2026-02-16

"""
from typing import Sequence, Union

from alembic import op

revision: str = '004'
down_revision: Union[str, None] = '003'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add args and tools columns to mcp_servers
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                          WHERE table_name = 'mcp_servers' AND column_name = 'args') THEN
                ALTER TABLE mcp_servers ADD COLUMN args TEXT[] DEFAULT '{}';
            END IF;
            IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                          WHERE table_name = 'mcp_servers' AND column_name = 'tools') THEN
                ALTER TABLE mcp_servers ADD COLUMN tools TEXT[] DEFAULT '{}';
            END IF;
        END $$;
    """)

    # Add target_models column to routing_policies
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                          WHERE table_name = 'routing_policies' AND column_name = 'target_models') THEN
                ALTER TABLE routing_policies ADD COLUMN target_models VARCHAR(255)[];
            END IF;
        END $$;
    """)

    # Add unique constraint on budgets(entity_type, entity_id) if not exists
    # First deduplicate any existing rows, keeping the newest
    op.execute("""
        DELETE FROM budgets a USING budgets b
        WHERE a.id < b.id
          AND a.entity_type = b.entity_type
          AND COALESCE(a.entity_id, '') = COALESCE(b.entity_id, '')
    """)
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint
                WHERE conname = 'budgets_entity_type_entity_id_key'
            ) THEN
                ALTER TABLE budgets ADD CONSTRAINT budgets_entity_type_entity_id_key
                    UNIQUE (entity_type, entity_id);
            END IF;
        END $$;
    """)


def downgrade() -> None:
    op.execute("ALTER TABLE mcp_servers DROP COLUMN IF EXISTS args")
    op.execute("ALTER TABLE mcp_servers DROP COLUMN IF EXISTS tools")
    op.execute("ALTER TABLE routing_policies DROP COLUMN IF EXISTS target_models")
    op.execute("ALTER TABLE budgets DROP CONSTRAINT IF EXISTS budgets_entity_type_entity_id_key")
