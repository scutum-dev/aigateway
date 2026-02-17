"""Add guardrail tables for content scanning and PII protection.

Revision ID: 005
Revises: 004
Create Date: 2026-02-17

"""

from typing import Sequence, Union

from alembic import op

revision: str = "005"
down_revision: Union[str, None] = "004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Guardrail configuration profiles
    op.execute("""
        CREATE TABLE IF NOT EXISTS guardrail_configs (
            id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
            name VARCHAR(255) UNIQUE NOT NULL,
            description TEXT,
            enable_prompt_injection BOOLEAN DEFAULT TRUE,
            prompt_injection_threshold DECIMAL(3, 2) DEFAULT 0.90,
            enable_pii_detection BOOLEAN DEFAULT TRUE,
            pii_action VARCHAR(50) DEFAULT 'anonymize',
            pii_entities TEXT[] DEFAULT '{PERSON,EMAIL_ADDRESS,PHONE_NUMBER,CREDIT_CARD,US_SSN,IBAN_CODE,IP_ADDRESS}',
            enable_toxicity BOOLEAN DEFAULT TRUE,
            toxicity_threshold DECIMAL(3, 2) DEFAULT 0.70,
            banned_topics TEXT[] DEFAULT '{}',
            enable_secrets_detection BOOLEAN DEFAULT TRUE,
            enable_invisible_text BOOLEAN DEFAULT TRUE,
            enable_malicious_urls BOOLEAN DEFAULT TRUE,
            enable_sensitive_output BOOLEAN DEFAULT TRUE,
            mode VARCHAR(50) DEFAULT 'block',
            on_fail VARCHAR(50) DEFAULT 'block',
            is_active BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Team-to-guardrail assignment (many-to-many)
    op.execute("""
        CREATE TABLE IF NOT EXISTS team_guardrails (
            id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
            team_id UUID NOT NULL,
            guardrail_config_id UUID NOT NULL REFERENCES guardrail_configs(id) ON DELETE CASCADE,
            priority INTEGER DEFAULT 0,
            created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(team_id, guardrail_config_id)
        )
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_team_guardrails_team
        ON team_guardrails(team_id)
    """)

    # Guardrail event audit log
    op.execute("""
        CREATE TABLE IF NOT EXISTS guardrail_events (
            id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
            event_type VARCHAR(50) NOT NULL,
            scanner_name VARCHAR(100) NOT NULL,
            user_id VARCHAR(255),
            team_id VARCHAR(255),
            model VARCHAR(255),
            risk_score DECIMAL(5, 4),
            action_taken VARCHAR(50) DEFAULT 'blocked',
            details JSONB DEFAULT '{}',
            created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
        )
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_guardrail_events_created
        ON guardrail_events(created_at)
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_guardrail_events_team
        ON guardrail_events(team_id)
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_guardrail_events_type
        ON guardrail_events(event_type)
    """)

    # Seed default guardrail profile
    op.execute("""
        INSERT INTO guardrail_configs (name, description)
        VALUES ('default', 'Default guardrail profile with standard protections')
        ON CONFLICT DO NOTHING
    """)

    # Add enable_guardrails to platform settings
    op.execute("""
        INSERT INTO platform_settings (key, value)
        VALUES ('enable_guardrails', 'true')
        ON CONFLICT DO NOTHING
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS guardrail_events")
    op.execute("DROP TABLE IF EXISTS team_guardrails")
    op.execute("DROP TABLE IF EXISTS guardrail_configs")
    op.execute("DELETE FROM platform_settings WHERE key = 'enable_guardrails'")
