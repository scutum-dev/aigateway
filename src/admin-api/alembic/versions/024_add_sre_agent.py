"""Add SRE agent: incidents, action decisions, seeded disabled agent and subscription.

Revision ID: 024
Revises: 023
Create Date: 2026-05-02

"""

from typing import Sequence, Union

from alembic import op

revision: str = "024"
down_revision: Union[str, None] = "023"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS sre_incidents (
            id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
            trigger_event VARCHAR(100) NOT NULL,
            trigger_payload JSONB NOT NULL,
            correlation_id UUID,
            workflow_id VARCHAR(255),
            diagnosis JSONB,
            proposed_plan JSONB,
            executed_actions JSONB DEFAULT '[]'::jsonb,
            status VARCHAR(32) NOT NULL DEFAULT 'open'
                CHECK (status IN ('open','diagnosing','awaiting_approval','executing','closed_success','closed_failed','closed_rejected')),
            outcome_summary TEXT,
            opened_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
            closed_at TIMESTAMPTZ
        )
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_sre_incidents_status_opened
        ON sre_incidents (status, opened_at DESC)
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_sre_incidents_trigger
        ON sre_incidents (trigger_event)
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_sre_incidents_workflow
        ON sre_incidents (workflow_id)
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS sre_action_decisions (
            id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
            incident_id UUID NOT NULL REFERENCES sre_incidents(id) ON DELETE CASCADE,
            action VARCHAR(64) NOT NULL,
            params JSONB NOT NULL,
            risk_score INTEGER,
            decision VARCHAR(16),
            approved_by VARCHAR(255),
            executed_at TIMESTAMPTZ,
            success BOOLEAN,
            error TEXT,
            created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
        )
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_sre_action_decisions_incident
        ON sre_action_decisions (incident_id)
    """)

    # Seed: disabled SRE agent registration. Operator activates from UI when ready.
    op.execute("""
        INSERT INTO a2a_agents (name, description, url, skills, is_active)
        VALUES (
            'sre-agent',
            'LLM-driven SRE agent: diagnoses incidents and proposes remediations gated through human approval.',
            'http://sre-agent:8092',
            '["diagnose","remediate","escalate"]'::jsonb,
            FALSE
        )
        ON CONFLICT (name) DO NOTHING
    """)

    # Seed: disabled event subscription that fans incident triggers to sre-agent.
    # event_subscriptions has no unique constraint, so guard with NOT EXISTS.
    op.execute("""
        INSERT INTO event_subscriptions (name, event_types, channel, config, is_active)
        SELECT
            'sre-agent default',
            ARRAY['sla.violation','budget.exceeded','provider.unhealthy','guardrail.violation'],
            'sre_workflow',
            '{}'::jsonb,
            FALSE
        WHERE NOT EXISTS (
            SELECT 1 FROM event_subscriptions WHERE name = 'sre-agent default'
        )
    """)


def downgrade() -> None:
    op.execute("""
        DELETE FROM event_subscriptions WHERE name = 'sre-agent default'
    """)
    op.execute("""
        DELETE FROM a2a_agents WHERE name = 'sre-agent'
    """)
    op.execute("DROP INDEX IF EXISTS idx_sre_action_decisions_incident")
    op.execute("DROP TABLE IF EXISTS sre_action_decisions CASCADE")
    op.execute("DROP INDEX IF EXISTS idx_sre_incidents_workflow")
    op.execute("DROP INDEX IF EXISTS idx_sre_incidents_trigger")
    op.execute("DROP INDEX IF EXISTS idx_sre_incidents_status_opened")
    op.execute("DROP TABLE IF EXISTS sre_incidents CASCADE")
