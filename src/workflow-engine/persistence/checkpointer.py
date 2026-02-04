"""
PostgreSQL checkpointer for LangGraph state persistence.
"""

import logging
from typing import Optional
import asyncpg

logger = logging.getLogger(__name__)


async def create_checkpointer(database_url: str) -> Optional["AsyncPostgresSaver"]:
    """
    Create a PostgreSQL checkpointer for LangGraph.

    Args:
        database_url: PostgreSQL connection URL

    Returns:
        Configured checkpointer or None
    """
    try:
        from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

        # Create connection pool
        pool = await asyncpg.create_pool(database_url, min_size=2, max_size=10)

        # Create checkpointer
        checkpointer = AsyncPostgresSaver(pool)

        # Initialize tables
        await checkpointer.setup()

        logger.info("PostgreSQL checkpointer initialized")
        return checkpointer

    except ImportError:
        logger.warning("langgraph PostgreSQL checkpoint not available")
        return None
    except Exception as e:
        logger.error(f"Failed to create checkpointer: {e}")
        return None


async def init_checkpoint_tables(pool: asyncpg.Pool):
    """
    Initialize checkpoint tables manually if needed.

    Args:
        pool: Database connection pool
    """
    async with pool.acquire() as conn:
        # Create checkpoints table
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS workflow_checkpoints (
                id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
                execution_id UUID NOT NULL,
                thread_id VARCHAR(255) NOT NULL,
                checkpoint_id VARCHAR(255) NOT NULL,
                parent_checkpoint_id VARCHAR(255),
                checkpoint_data JSONB NOT NULL,
                created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(thread_id, checkpoint_id)
            )
        """)

        # Create index
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_checkpoints_thread
            ON workflow_checkpoints(thread_id)
        """)

        logger.info("Checkpoint tables initialized")
