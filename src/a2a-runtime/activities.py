import asyncio
import json
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional, Any

import httpx
from temporalio import activity

import state
from a2a_models import Agent, InvokeAgentInput, InvokeAgentOutput


@activity.defn
async def invoke_agent(input: InvokeAgentInput) -> InvokeAgentOutput:
    """Invoke an agent with the given capability."""
    start_time = datetime.now(timezone.utc)

    async with httpx.AsyncClient(timeout=input.timeout_seconds) as client:
        try:
            # Get agent endpoint from registry
            agent_data = await state.redis_client.hget("a2a:agents", input.agent_id)
            if not agent_data:
                return InvokeAgentOutput(
                    success=False,
                    result=None,
                    error=f"Agent {input.agent_id} not found",
                    tokens_used=0,
                    duration_ms=0,
                )

            agent = Agent(**json.loads(agent_data))

            # Invoke the agent
            response = await client.post(
                f"{agent.endpoint}/invoke",
                json={
                    "capability": input.capability,
                    "input": input.input_data,
                },
            )

            duration_ms = int((datetime.now(timezone.utc) - start_time).total_seconds() * 1000)

            if response.status_code == 200:
                result = response.json()
                return InvokeAgentOutput(
                    success=True,
                    result=result.get("result"),
                    error=None,
                    tokens_used=result.get("tokens_used", 0),
                    duration_ms=duration_ms,
                )
            else:
                return InvokeAgentOutput(
                    success=False,
                    result=None,
                    error=f"Agent returned status {response.status_code}: {response.text}",
                    tokens_used=0,
                    duration_ms=duration_ms,
                )

        except Exception as e:
            duration_ms = int((datetime.now(timezone.utc) - start_time).total_seconds() * 1000)
            return InvokeAgentOutput(
                success=False,
                result=None,
                error=str(e),
                tokens_used=0,
                duration_ms=duration_ms,
            )


@activity.defn
async def send_message(message: Dict[str, Any]) -> bool:
    """Send a message to an agent."""
    async with httpx.AsyncClient(timeout=30) as client:
        try:
            agent_data = await state.redis_client.hget("a2a:agents", message["target_agent"])
            if not agent_data:
                return False

            agent = Agent(**json.loads(agent_data))

            response = await client.post(
                f"{agent.endpoint}/messages",
                json=message,
            )
            return response.status_code == 200
        except Exception:
            return False


@activity.defn
async def wait_for_human_approval(workflow_id: str, step_id: str, timeout_seconds: int) -> Dict[str, Any]:
    """Wait for human approval on a workflow step."""
    key = f"a2a:approvals:{workflow_id}:{step_id}"
    deadline = datetime.now(timezone.utc) + timedelta(seconds=timeout_seconds)

    while datetime.now(timezone.utc) < deadline:
        approval_data = await state.redis_client.get(key)
        if approval_data:
            return json.loads(approval_data)
        await asyncio.sleep(5)

    raise TimeoutError(f"Human approval timed out after {timeout_seconds} seconds")


@activity.defn
async def record_execution_step(
    workflow_id: str,
    step_name: str,
    status: str,
    input_data: Dict[str, Any],
    output_data: Optional[Dict[str, Any]],
    error: Optional[str],
) -> None:
    """Record workflow execution step for audit."""
    step = {
        "workflow_id": workflow_id,
        "step_name": step_name,
        "status": status,
        "input": input_data,
        "output": output_data,
        "error": error,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    await state.redis_client.rpush(f"a2a:history:{workflow_id}", json.dumps(step))
