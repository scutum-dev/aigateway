"""Add routing policies table.

Revision ID: 023
Revises: 022
"""

from alembic import op

revision = "023"
down_revision = "022"


def upgrade():
    op.execute(
        """
        CREATE TABLE routing_policies (
            id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
            name VARCHAR(255) NOT NULL,
            description TEXT,
            policy_type VARCHAR(50) NOT NULL,
            config JSONB NOT NULL DEFAULT '{}',
            priority INTEGER DEFAULT 0,
            is_active BOOLEAN DEFAULT TRUE,
            synced_at TIMESTAMPTZ,
            created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
        );

        CREATE INDEX idx_routing_policies_type ON routing_policies(policy_type);
        CREATE INDEX idx_routing_policies_active ON routing_policies(is_active);

        -- Seed with current routing strategy from litellm config
        INSERT INTO routing_policies (name, description, policy_type, config, is_active)
        VALUES (
            'Default Routing Strategy',
            'Usage-based routing with RPM/TPM limit checks',
            'routing_strategy',
            '{"strategy": "usage-based-routing", "args": {"ttl": 60, "rpm_limit_check": true, "tpm_limit_check": true}}',
            TRUE
        );
        """
    )


def downgrade():
    op.execute("DROP TABLE IF EXISTS routing_policies CASCADE;")
