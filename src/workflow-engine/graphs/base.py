"""
Base LangGraph workflow class.
"""

import logging
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, AsyncIterator
from datetime import datetime

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

from models.state import WorkflowState
from models.execution import WorkflowExecution, ExecutionStatus

logger = logging.getLogger(__name__)


class BaseWorkflow(ABC):
    """
    Base class for LangGraph workflows.

    Provides common functionality for:
    - Graph compilation
    - State management
    - Checkpoint persistence
    - Execution tracking
    """

    def __init__(
        self,
        name: str,
        checkpointer: Optional[AsyncPostgresSaver] = None,
        llm_client: Optional[Any] = None,
        mcp_client: Optional[Any] = None,
    ):
        """
        Initialize base workflow.

        Args:
            name: Workflow name
            checkpointer: PostgreSQL checkpointer for state persistence
            llm_client: LLM client for model calls
            mcp_client: MCP client for tool calls
        """
        self.name = name
        self.checkpointer = checkpointer
        self.llm_client = llm_client
        self.mcp_client = mcp_client
        self._graph = None
        self._compiled = None

    @abstractmethod
    def build_graph(self) -> StateGraph:
        """
        Build the LangGraph state graph.

        Subclasses must implement this method to define
        the workflow's nodes and edges.

        Returns:
            Configured StateGraph
        """
        pass

    def compile(self) -> Any:
        """Compile the workflow graph."""
        if self._compiled is None:
            self._graph = self.build_graph()
            self._compiled = self._graph.compile(
                checkpointer=self.checkpointer
            )
        return self._compiled

    async def run(
        self,
        input_data: Dict[str, Any],
        config: Optional[Dict[str, Any]] = None,
    ) -> WorkflowState:
        """
        Execute the workflow.

        Args:
            input_data: Input data for the workflow
            config: LangGraph config (thread_id, etc.)

        Returns:
            Final workflow state
        """
        graph = self.compile()

        # Initialize state
        initial_state = WorkflowState(
            input=input_data,
            messages=[{"role": "user", "content": str(input_data)}],
        )

        # Run the graph
        config = config or {}
        if "configurable" not in config:
            config["configurable"] = {}
        if "thread_id" not in config["configurable"]:
            config["configurable"]["thread_id"] = f"{self.name}-{datetime.utcnow().isoformat()}"

        final_state = await graph.ainvoke(initial_state, config)

        return WorkflowState(**final_state)

    async def stream(
        self,
        input_data: Dict[str, Any],
        config: Optional[Dict[str, Any]] = None,
    ) -> AsyncIterator[Dict[str, Any]]:
        """
        Stream workflow execution updates.

        Args:
            input_data: Input data for the workflow
            config: LangGraph config

        Yields:
            State updates as the workflow progresses
        """
        graph = self.compile()

        # Initialize state
        initial_state = WorkflowState(
            input=input_data,
            messages=[{"role": "user", "content": str(input_data)}],
        )

        # Configure
        config = config or {}
        if "configurable" not in config:
            config["configurable"] = {}
        if "thread_id" not in config["configurable"]:
            config["configurable"]["thread_id"] = f"{self.name}-{datetime.utcnow().isoformat()}"

        # Stream updates
        async for event in graph.astream(initial_state, config):
            yield event

    async def resume(
        self,
        thread_id: str,
        config: Optional[Dict[str, Any]] = None,
    ) -> WorkflowState:
        """
        Resume a paused workflow.

        Args:
            thread_id: Thread ID to resume
            config: Additional config

        Returns:
            Final workflow state
        """
        graph = self.compile()

        config = config or {}
        config["configurable"] = config.get("configurable", {})
        config["configurable"]["thread_id"] = thread_id

        # Get current state from checkpoint
        state = await graph.aget_state(config)

        if not state or not state.values:
            raise ValueError(f"No checkpoint found for thread {thread_id}")

        # Resume execution
        final_state = await graph.ainvoke(None, config)

        return WorkflowState(**final_state)

    async def get_state(
        self,
        thread_id: str,
    ) -> Optional[WorkflowState]:
        """
        Get current workflow state.

        Args:
            thread_id: Thread ID

        Returns:
            Current state or None
        """
        graph = self.compile()

        config = {"configurable": {"thread_id": thread_id}}
        state = await graph.aget_state(config)

        if state and state.values:
            return WorkflowState(**state.values)

        return None
