"""Add multi-tenancy tables: users, organizations, business_units, team_hierarchy, org_memberships, sso_configs.

Revision ID: 010
Revises: 009
Create Date: 2026-02-18

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "010"
down_revision: Union[str, None] = "009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
            email VARCHAR(255) UNIQUE NOT NULL,
            display_name VARCHAR(255),
            avatar_url TEXT,
            auth_provider VARCHAR(50) DEFAULT 'api_key',
            external_id VARCHAR(255),
            idp_metadata JSONB DEFAULT '{}',
            is_active BOOLEAN DEFAULT TRUE,
            is_platform_admin BOOLEAN DEFAULT FALSE,
            last_login_at TIMESTAMPTZ,
            created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
        )
    """)

    op.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS idx_users_external_id
        ON users(auth_provider, external_id) WHERE external_id IS NOT NULL
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS organizations (
            id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
            name VARCHAR(255) UNIQUE NOT NULL,
            slug VARCHAR(255) UNIQUE NOT NULL,
            description TEXT,
            max_budget DECIMAL(20,10),
            allowed_models TEXT[],
            metadata JSONB DEFAULT '{}',
            is_active BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
        )
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS business_units (
            id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
            org_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
            name VARCHAR(255) NOT NULL,
            slug VARCHAR(255) NOT NULL,
            description TEXT,
            max_budget DECIMAL(20,10),
            allowed_models TEXT[],
            metadata JSONB DEFAULT '{}',
            is_active BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(org_id, slug)
        )
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS team_hierarchy (
            team_id VARCHAR(255) PRIMARY KEY,
            org_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
            bu_id UUID REFERENCES business_units(id) ON DELETE SET NULL,
            max_budget_override DECIMAL(20,10),
            created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
        )
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS org_memberships (
            id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
            user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            org_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
            role VARCHAR(50) NOT NULL DEFAULT 'member',
            bu_id UUID REFERENCES business_units(id) ON DELETE SET NULL,
            created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(user_id, org_id, bu_id)
        )
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS sso_configs (
            id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
            org_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
            provider_type VARCHAR(50) NOT NULL,
            provider_name VARCHAR(100) NOT NULL,
            client_id VARCHAR(255),
            client_secret_encrypted TEXT,
            issuer_url TEXT,
            authorization_url TEXT,
            token_url TEXT,
            userinfo_url TEXT,
            jwks_uri TEXT,
            saml_metadata_url TEXT,
            scopes VARCHAR(500) DEFAULT 'openid email profile',
            group_claim VARCHAR(255) DEFAULT 'groups',
            group_to_org_mapping JSONB DEFAULT '{}',
            is_active BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(org_id, provider_type)
        )
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS sso_configs CASCADE")
    op.execute("DROP TABLE IF EXISTS org_memberships CASCADE")
    op.execute("DROP TABLE IF EXISTS team_hierarchy CASCADE")
    op.execute("DROP TABLE IF EXISTS business_units CASCADE")
    op.execute("DROP TABLE IF EXISTS organizations CASCADE")
    op.execute("DROP INDEX IF EXISTS idx_users_external_id")
    op.execute("DROP TABLE IF EXISTS users CASCADE")
