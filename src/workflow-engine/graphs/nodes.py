"""
Reusable LangGraph nodes for workflow construction.
"""

import logging
from typing import Dict, Any, Optional, Callable
from datetime import datetime

from models.state import WorkflowState

logger = logging.getLogger(__name__)


async def llm_node(
    state: WorkflowState,
    llm_client: Any,
    system_prompt: Optional[str] = None,
    model: str = "gpt-4o-mini",
    temperature: float = 0.7,
    max_tokens: int = 2000,
    node_name: str = "llm",
) -> Dict[str, Any]:
    """
    Generic LLM node for workflow graphs.

    Args:
        state: Current workflow state
        llm_client: LLM client (httpx or LangChain)
        system_prompt: System prompt to use
        model: Model to use
        temperature: Temperature setting
        max_tokens: Maximum tokens
        node_name: Name of this node for tracking

    Returns:
        State update dictionary
    """
    start_time = datetime.utcnow()

    try:
        # Build messages
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})

        # Add conversation history
        for msg in state.messages:
            if isinstance(msg, dict):
                messages.append(msg)
            else:
                messages.append({"role": msg.role, "content": msg.content})

        # Call LLM
        response = await llm_client.post(
            "/v1/chat/completions",
            json={
                "model": model,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
            }
        )

        if response.status_code != 200:
            raise Exception(f"LLM call failed: {response.text}")

        data = response.json()
        content = data["choices"][0]["message"]["content"]
        usage = data.get("usage", {})

        # Calculate cost (approximate)
        input_tokens = usage.get("prompt_tokens", 0)
        output_tokens = usage.get("completion_tokens", 0)
        cost = (input_tokens * 0.00015 + output_tokens * 0.0006) / 1000  # GPT-4o-mini pricing

        duration = (datetime.utcnow() - start_time).total_seconds() * 1000

        # Update state
        state.update_node_state(
            node_name=node_name,
            status="completed",
            tokens=input_tokens + output_tokens,
            cost=cost,
            output={"content": content}
        )

        return {
            "messages": [{"role": "assistant", "content": content}],
            "current_node": node_name,
        }

    except Exception as e:
        logger.error(f"LLM node error: {e}")
        state.update_node_state(
            node_name=node_name,
            status="failed",
            error=str(e)
        )
        return {
            "error": str(e),
            "should_continue": False,
        }


async def tool_node(
    state: WorkflowState,
    mcp_client: Any,
    tool_name: str,
    tool_args: Dict[str, Any],
    node_name: str = "tool",
) -> Dict[str, Any]:
    """
    MCP tool invocation node.

    Args:
        state: Current workflow state
        mcp_client: MCP client
        tool_name: Tool to invoke
        tool_args: Tool arguments
        node_name: Name of this node

    Returns:
        State update dictionary
    """
    start_time = datetime.utcnow()

    try:
        # Call MCP tool
        response = await mcp_client.post(
            "/mcp/tools/call",
            json={
                "name": tool_name,
                "arguments": tool_args,
            }
        )

        if response.status_code != 200:
            raise Exception(f"Tool call failed: {response.text}")

        result = response.json()

        duration = (datetime.utcnow() - start_time).total_seconds() * 1000

        state.update_node_state(
            node_name=node_name,
            status="completed",
            output={"tool_result": result}
        )

        return {
            "messages": [{
                "role": "tool",
                "content": str(result),
                "name": tool_name,
            }],
            "intermediate_results": {tool_name: result},
            "current_node": node_name,
        }

    except Exception as e:
        logger.error(f"Tool node error: {e}")
        state.update_node_state(
            node_name=node_name,
            status="failed",
            error=str(e)
        )
        return {
            "error": str(e),
            "should_continue": False,
        }


def router_node(
    state: WorkflowState,
    conditions: Dict[str, Callable[[WorkflowState], bool]],
    default: str = "end",
) -> str:
    """
    Conditional routing node.

    Args:
        state: Current workflow state
        conditions: Dict mapping target node names to condition functions
        default: Default target if no condition matches

    Returns:
        Name of the next node
    """
    for target, condition in conditions.items():
        try:
            if condition(state):
                logger.info(f"Router: routing to {target}")
                return target
        except Exception as e:
            logger.warning(f"Router condition error for {target}: {e}")

    logger.info(f"Router: using default route to {default}")
    return default


def create_llm_node(
    llm_client: Any,
    system_prompt: str,
    model: str = "gpt-4o-mini",
    node_name: str = "llm",
):
    """
    Factory function to create an LLM node with pre-configured settings.

    Args:
        llm_client: LLM client
        system_prompt: System prompt
        model: Model to use
        node_name: Node name

    Returns:
        Async function suitable for LangGraph
    """
    async def node(state: WorkflowState) -> Dict[str, Any]:
        return await llm_node(
            state=state,
            llm_client=llm_client,
            system_prompt=system_prompt,
            model=model,
            node_name=node_name,
        )

    return node


def create_tool_node(
    mcp_client: Any,
    tool_name: str,
    args_extractor: Callable[[WorkflowState], Dict[str, Any]],
    node_name: Optional[str] = None,
):
    """
    Factory function to create a tool node.

    Args:
        mcp_client: MCP client
        tool_name: Tool name
        args_extractor: Function to extract args from state
        node_name: Node name (defaults to tool_name)

    Returns:
        Async function suitable for LangGraph
    """
    async def node(state: WorkflowState) -> Dict[str, Any]:
        args = args_extractor(state)
        return await tool_node(
            state=state,
            mcp_client=mcp_client,
            tool_name=tool_name,
            tool_args=args,
            node_name=node_name or tool_name,
        )

    return node
