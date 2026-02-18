"""Add chargeback cost allocation, reports, and budget forecasts.

Revision ID: 016
Revises: 015
Create Date: 2026-02-18

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "016"
down_revision: Union[str, None] = "015"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS cost_allocation_rules (
            id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
            name VARCHAR(255) NOT NULL,
            team_id UUID,
            allocation_type VARCHAR(50) NOT NULL,
            allocation_target VARCHAR(255) NOT NULL,
            allocation_percent DECIMAL(5, 2) DEFAULT 100.0,
            metadata JSONB DEFAULT '{}',
            is_active BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
        )
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS chargeback_reports (
            id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
            report_period VARCHAR(20) NOT NULL,
            status VARCHAR(50) DEFAULT 'draft',
            total_cost DECIMAL(20, 10) DEFAULT 0,
            breakdown JSONB DEFAULT '[]',
            generated_by VARCHAR(255),
            finalized_at TIMESTAMPTZ,
            exported_at TIMESTAMPTZ,
            created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
        )
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS budget_forecasts (
            id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
            team_id UUID,
            forecast_period VARCHAR(20) NOT NULL,
            forecast_type VARCHAR(50) DEFAULT 'linear',
            forecasted_cost DECIMAL(20, 10),
            confidence_low DECIMAL(20, 10),
            confidence_high DECIMAL(20, 10),
            actual_cost DECIMAL(20, 10),
            created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
        )
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS budget_forecasts CASCADE")
    op.execute("DROP TABLE IF EXISTS chargeback_reports CASCADE")
    op.execute("DROP TABLE IF EXISTS cost_allocation_rules CASCADE")
