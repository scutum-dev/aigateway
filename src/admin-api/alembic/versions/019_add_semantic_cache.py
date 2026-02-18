"""Add semantic cache table with vector embedding support.

Revision ID: 019
Revises: 018
Create Date: 2026-02-18

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "019"
down_revision: Union[str, None] = "018"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Check if pgvector extension is available
    conn = op.get_bind()
    result = conn.execute(sa.text("SELECT COUNT(*) FROM pg_available_extensions WHERE name = 'vector'"))
    has_pgvector = result.scalar() > 0

    if has_pgvector:
        op.execute("CREATE EXTENSION IF NOT EXISTS vector")
        op.execute("""
            CREATE TABLE IF NOT EXISTS semantic_cache (
                id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
                embedding vector(1536),
                prompt_hash VARCHAR(64),
                model VARCHAR(255),
                request_body JSONB,
                response_body JSONB,
                token_count INTEGER,
                hit_count INTEGER DEFAULT 0,
                last_hit_at TIMESTAMPTZ,
                created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
                expires_at TIMESTAMPTZ
            )
        """)
        op.execute("""
            CREATE INDEX IF NOT EXISTS idx_semantic_cache_embedding
            ON semantic_cache USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100)
        """)
    else:
        # Create table without vector column when pgvector is not available
        op.execute("""
            CREATE TABLE IF NOT EXISTS semantic_cache (
                id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
                prompt_hash VARCHAR(64),
                model VARCHAR(255),
                request_body JSONB,
                response_body JSONB,
                token_count INTEGER,
                hit_count INTEGER DEFAULT 0,
                last_hit_at TIMESTAMPTZ,
                created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
                expires_at TIMESTAMPTZ
            )
        """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_semantic_cache_prompt_hash
        ON semantic_cache(prompt_hash)
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_semantic_cache_model
        ON semantic_cache(model)
    """)


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_semantic_cache_model")
    op.execute("DROP INDEX IF EXISTS idx_semantic_cache_prompt_hash")
    op.execute("DROP INDEX IF EXISTS idx_semantic_cache_embedding")
    op.execute("DROP TABLE IF EXISTS semantic_cache CASCADE")
