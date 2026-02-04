"""
Repository for workflow CRUD operations.
"""

import logging
import json
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone
import asyncpg

from models.workflow import WorkflowDefinition, WorkflowTemplate
from models.execution import WorkflowExecution, ExecutionStatus, WorkflowStep, ExecutionSummary

logger = logging.getLogger(__name__)


class WorkflowRepository:
    """
    Repository for workflow data persistence.

    Handles CRUD operations for:
    - Workflow definitions
    - Workflow executions
    - Workflow steps
    """

    def __init__(self, pool: asyncpg.Pool):
        """
        Initialize repository.

        Args:
            pool: Database connection pool
        """
        self.pool = pool

    async def init_tables(self):
        """Initialize database tables."""
        async with self.pool.acquire() as conn:
            # Workflow definitions
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS workflow_definitions (
                    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
                    name VARCHAR(255) UNIQUE NOT NULL,
                    version VARCHAR(50) DEFAULT '1.0.0',
                    template_type VARCHAR(100),
                    description TEXT,
                    graph_definition JSONB NOT NULL,
                    input_schema JSONB,
                    output_schema JSONB,
                    is_active BOOLEAN DEFAULT TRUE,
                    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Workflow executions
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS workflow_executions (
                    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
                    workflow_id UUID REFERENCES workflow_definitions(id),
                    workflow_name VARCHAR(255),
                    template_type VARCHAR(100),
                    user_id VARCHAR(255),
                    team_id VARCHAR(255),
                    status VARCHAR(50) DEFAULT 'pending',
                    input JSONB,
                    output JSONB,
                    current_node VARCHAR(255),
                    error TEXT,
                    total_tokens BIGINT DEFAULT 0,
                    total_cost DECIMAL(20, 10) DEFAULT 0,
                    duration_ms INTEGER DEFAULT 0,
                    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
                    completed_at TIMESTAMPTZ
                )
            """)

            # Workflow steps
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS workflow_steps (
                    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
                    execution_id UUID REFERENCES workflow_executions(id),
                    node_name VARCHAR(255) NOT NULL,
                    step_order INTEGER NOT NULL,
                    status VARCHAR(50) DEFAULT 'pending',
                    input_data JSONB,
                    output_data JSONB,
                    input_tokens BIGINT DEFAULT 0,
                    output_tokens BIGINT DEFAULT 0,
                    cost DECIMAL(20, 10) DEFAULT 0,
                    duration_ms INTEGER DEFAULT 0,
                    error TEXT,
                    started_at TIMESTAMPTZ,
                    completed_at TIMESTAMPTZ
                )
            """)

            # Indexes
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_executions_user ON workflow_executions(user_id)")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_executions_status ON workflow_executions(status)")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_executions_created ON workflow_executions(created_at)")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_steps_execution ON workflow_steps(execution_id)")

            logger.info("Workflow tables initialized")

    # Workflow Definitions

    async def create_workflow(self, workflow: WorkflowDefinition) -> str:
        """Create a new workflow definition."""
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow("""
                INSERT INTO workflow_definitions
                (name, version, template_type, description, graph_definition, input_schema, output_schema, is_active)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                RETURNING id
            """,
                workflow.name,
                workflow.version,
                workflow.template_type,
                workflow.description,
                json.dumps(workflow.graph_definition.model_dump()) if workflow.graph_definition else "{}",
                json.dumps(workflow.input_schema) if workflow.input_schema else None,
                json.dumps(workflow.output_schema) if workflow.output_schema else None,
                workflow.is_active,
            )
            return str(row["id"])

    async def get_workflow(self, workflow_id: str) -> Optional[WorkflowDefinition]:
        """Get a workflow by ID."""
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM workflow_definitions WHERE id = $1",
                workflow_id
            )
            if row:
                return self._row_to_workflow(row)
            return None

    async def get_workflow_by_name(self, name: str) -> Optional[WorkflowDefinition]:
        """Get a workflow by name."""
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM workflow_definitions WHERE name = $1 AND is_active = TRUE",
                name
            )
            if row:
                return self._row_to_workflow(row)
            return None

    async def list_workflows(self, active_only: bool = True) -> List[WorkflowDefinition]:
        """List all workflows."""
        async with self.pool.acquire() as conn:
            query = "SELECT * FROM workflow_definitions"
            if active_only:
                query += " WHERE is_active = TRUE"
            query += " ORDER BY name"

            rows = await conn.fetch(query)
            return [self._row_to_workflow(row) for row in rows]

    def _row_to_workflow(self, row) -> WorkflowDefinition:
        """Convert database row to WorkflowDefinition."""
        from models.workflow import GraphDefinition

        graph_def = row["graph_definition"]
        if isinstance(graph_def, str):
            graph_def = json.loads(graph_def)

        return WorkflowDefinition(
            id=str(row["id"]),
            name=row["name"],
            version=row["version"],
            template_type=row["template_type"],
            description=row["description"],
            graph_definition=GraphDefinition(**graph_def) if graph_def else None,
            input_schema=row["input_schema"],
            output_schema=row["output_schema"],
            is_active=row["is_active"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    # Workflow Executions

    async def create_execution(self, execution: WorkflowExecution) -> str:
        """Create a new execution record."""
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow("""
                INSERT INTO workflow_executions
                (workflow_id, workflow_name, template_type, user_id, team_id, status, input)
                VALUES ($1, $2, $3, $4, $5, $6, $7)
                RETURNING id
            """,
                execution.workflow_id,
                execution.workflow_name,
                execution.template_type,
                execution.user_id,
                execution.team_id,
                execution.status.value if isinstance(execution.status, ExecutionStatus) else execution.status,
                json.dumps(execution.input),
            )
            return str(row["id"])

    async def get_execution(self, execution_id: str) -> Optional[WorkflowExecution]:
        """Get an execution by ID."""
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM workflow_executions WHERE id = $1",
                execution_id
            )
            if row:
                return self._row_to_execution(row)
            return None

    async def update_execution(
        self,
        execution_id: str,
        status: Optional[str] = None,
        current_node: Optional[str] = None,
        output: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None,
        total_tokens: Optional[int] = None,
        total_cost: Optional[float] = None,
        duration_ms: Optional[int] = None,
    ):
        """Update an execution."""
        updates = []
        params = []
        param_idx = 1

        if status:
            updates.append(f"status = ${param_idx}")
            params.append(status)
            param_idx += 1

        if current_node:
            updates.append(f"current_node = ${param_idx}")
            params.append(current_node)
            param_idx += 1

        if output is not None:
            updates.append(f"output = ${param_idx}")
            params.append(json.dumps(output))
            param_idx += 1

        if error is not None:
            updates.append(f"error = ${param_idx}")
            params.append(error)
            param_idx += 1

        if total_tokens is not None:
            updates.append(f"total_tokens = ${param_idx}")
            params.append(total_tokens)
            param_idx += 1

        if total_cost is not None:
            updates.append(f"total_cost = ${param_idx}")
            params.append(total_cost)
            param_idx += 1

        if duration_ms is not None:
            updates.append(f"duration_ms = ${param_idx}")
            params.append(duration_ms)
            param_idx += 1

        if status in ("completed", "failed", "cancelled"):
            updates.append(f"completed_at = ${param_idx}")
            params.append(datetime.now(timezone.utc))
            param_idx += 1

        updates.append("updated_at = CURRENT_TIMESTAMP")

        if updates:
            params.append(execution_id)
            query = f"UPDATE workflow_executions SET {', '.join(updates)} WHERE id = ${param_idx}"

            async with self.pool.acquire() as conn:
                await conn.execute(query, *params)

    async def list_executions(
        self,
        user_id: Optional[str] = None,
        team_id: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 100,
    ) -> List[ExecutionSummary]:
        """List executions with optional filters."""
        query = "SELECT id, workflow_name, template_type, status, user_id, current_node, total_cost, duration_ms, created_at FROM workflow_executions WHERE 1=1"
        params = []
        param_idx = 1

        if user_id:
            query += f" AND user_id = ${param_idx}"
            params.append(user_id)
            param_idx += 1

        if team_id:
            query += f" AND team_id = ${param_idx}"
            params.append(team_id)
            param_idx += 1

        if status:
            query += f" AND status = ${param_idx}"
            params.append(status)
            param_idx += 1

        query += f" ORDER BY created_at DESC LIMIT ${param_idx}"
        params.append(limit)

        async with self.pool.acquire() as conn:
            rows = await conn.fetch(query, *params)
            return [
                ExecutionSummary(
                    id=str(row["id"]),
                    workflow_name=row["workflow_name"],
                    template_type=row["template_type"],
                    status=row["status"],
                    user_id=row["user_id"],
                    current_node=row["current_node"],
                    total_cost=float(row["total_cost"]) if row["total_cost"] else 0.0,
                    duration_ms=row["duration_ms"] or 0,
                    created_at=row["created_at"],
                )
                for row in rows
            ]

    def _row_to_execution(self, row) -> WorkflowExecution:
        """Convert database row to WorkflowExecution."""
        return WorkflowExecution(
            id=str(row["id"]),
            workflow_id=str(row["workflow_id"]) if row["workflow_id"] else None,
            workflow_name=row["workflow_name"],
            template_type=row["template_type"],
            user_id=row["user_id"],
            team_id=row["team_id"],
            status=ExecutionStatus(row["status"]),
            input=row["input"] if row["input"] else {},
            output=row["output"],
            current_node=row["current_node"],
            error=row["error"],
            total_tokens=row["total_tokens"] or 0,
            total_cost=float(row["total_cost"]) if row["total_cost"] else 0.0,
            duration_ms=row["duration_ms"] or 0,
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            completed_at=row["completed_at"],
        )

    # Workflow Steps

    async def add_step(self, step: WorkflowStep) -> str:
        """Add a workflow step."""
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow("""
                INSERT INTO workflow_steps
                (execution_id, node_name, step_order, status, input_data, started_at)
                VALUES ($1, $2, $3, $4, $5, $6)
                RETURNING id
            """,
                step.execution_id,
                step.node_name,
                step.step_order,
                step.status,
                json.dumps(step.input_data) if step.input_data else None,
                step.started_at or datetime.now(timezone.utc),
            )
            return str(row["id"])

    async def update_step(
        self,
        step_id: str,
        status: str,
        output_data: Optional[Dict[str, Any]] = None,
        input_tokens: int = 0,
        output_tokens: int = 0,
        cost: float = 0.0,
        duration_ms: int = 0,
        error: Optional[str] = None,
    ):
        """Update a workflow step."""
        async with self.pool.acquire() as conn:
            await conn.execute("""
                UPDATE workflow_steps
                SET status = $1, output_data = $2, input_tokens = $3, output_tokens = $4,
                    cost = $5, duration_ms = $6, error = $7, completed_at = $8
                WHERE id = $9
            """,
                status,
                json.dumps(output_data) if output_data else None,
                input_tokens,
                output_tokens,
                cost,
                duration_ms,
                error,
                datetime.now(timezone.utc),
                step_id,
            )

    async def get_steps(self, execution_id: str) -> List[WorkflowStep]:
        """Get all steps for an execution."""
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT * FROM workflow_steps WHERE execution_id = $1 ORDER BY step_order",
                execution_id
            )
            return [
                WorkflowStep(
                    id=str(row["id"]),
                    execution_id=str(row["execution_id"]),
                    node_name=row["node_name"],
                    step_order=row["step_order"],
                    status=row["status"],
                    input_data=row["input_data"],
                    output_data=row["output_data"],
                    input_tokens=row["input_tokens"] or 0,
                    output_tokens=row["output_tokens"] or 0,
                    cost=float(row["cost"]) if row["cost"] else 0.0,
                    duration_ms=row["duration_ms"] or 0,
                    error=row["error"],
                    started_at=row["started_at"],
                    completed_at=row["completed_at"],
                )
                for row in rows
            ]
