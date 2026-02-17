from datetime import timedelta
from typing import Any, Dict, List

from temporalio import workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    from a2a_models import InvokeAgentInput
    from activities import invoke_agent, record_execution_step, wait_for_human_approval


@workflow.defn
class SingleAgentWorkflow:
    """Workflow for single agent invocation with retries."""

    @workflow.run
    async def run(self, agent_id: str, capability: str, input_data: Dict[str, Any]) -> Dict[str, Any]:
        workflow_id = workflow.info().workflow_id

        # Record start
        await workflow.execute_activity(
            record_execution_step,
            args=[workflow_id, "start", "running", input_data, None, None],
            start_to_close_timeout=timedelta(seconds=30),
        )

        # Invoke agent with retry policy
        result = await workflow.execute_activity(
            invoke_agent,
            InvokeAgentInput(
                agent_id=agent_id,
                capability=capability,
                input_data=input_data,
            ),
            start_to_close_timeout=timedelta(minutes=10),
            retry_policy=RetryPolicy(
                initial_interval=timedelta(seconds=1),
                maximum_interval=timedelta(minutes=1),
                maximum_attempts=3,
            ),
        )

        # Record completion
        await workflow.execute_activity(
            record_execution_step,
            args=[
                workflow_id,
                "complete",
                "completed" if result.success else "failed",
                {},
                result.result,
                result.error,
            ],
            start_to_close_timeout=timedelta(seconds=30),
        )

        if not result.success:
            raise Exception(result.error)

        return {
            "result": result.result,
            "tokens_used": result.tokens_used,
            "duration_ms": result.duration_ms,
        }


@workflow.defn
class SequentialAgentWorkflow:
    """Workflow for sequential agent invocations (pipeline)."""

    @workflow.run
    async def run(self, agents: List[Dict[str, str]], initial_input: Dict[str, Any]) -> Dict[str, Any]:
        workflow_id = workflow.info().workflow_id
        current_input = initial_input
        results = []

        for i, agent_config in enumerate(agents):
            agent_id = agent_config["agent_id"]
            capability = agent_config["capability"]
            step_name = f"agent_{i}_{agent_id}"

            # Record step start
            await workflow.execute_activity(
                record_execution_step,
                args=[workflow_id, step_name, "running", current_input, None, None],
                start_to_close_timeout=timedelta(seconds=30),
            )

            # Invoke agent
            result = await workflow.execute_activity(
                invoke_agent,
                InvokeAgentInput(
                    agent_id=agent_id,
                    capability=capability,
                    input_data=current_input,
                ),
                start_to_close_timeout=timedelta(minutes=10),
                retry_policy=RetryPolicy(maximum_attempts=3),
            )

            if not result.success:
                await workflow.execute_activity(
                    record_execution_step,
                    args=[workflow_id, step_name, "failed", current_input, None, result.error],
                    start_to_close_timeout=timedelta(seconds=30),
                )
                raise Exception(f"Agent {agent_id} failed: {result.error}")

            # Record step completion
            await workflow.execute_activity(
                record_execution_step,
                args=[workflow_id, step_name, "completed", current_input, result.result, None],
                start_to_close_timeout=timedelta(seconds=30),
            )

            results.append(
                {
                    "agent_id": agent_id,
                    "result": result.result,
                    "tokens_used": result.tokens_used,
                }
            )

            # Pass output to next agent
            current_input = result.result or {}

        return {
            "final_result": current_input,
            "steps": results,
        }


@workflow.defn
class ParallelAgentWorkflow:
    """Workflow for parallel agent invocations."""

    @workflow.run
    async def run(self, agents: List[Dict[str, str]], input_data: Dict[str, Any]) -> Dict[str, Any]:
        _workflow_id = workflow.info().workflow_id

        # Start all agents in parallel
        tasks = []
        for agent_config in agents:
            task = workflow.execute_activity(
                invoke_agent,
                InvokeAgentInput(
                    agent_id=agent_config["agent_id"],
                    capability=agent_config["capability"],
                    input_data=input_data,
                ),
                start_to_close_timeout=timedelta(minutes=10),
                retry_policy=RetryPolicy(maximum_attempts=3),
            )
            tasks.append((agent_config["agent_id"], task))

        # Wait for all to complete
        results = {}
        errors = []

        for agent_id, task in tasks:
            try:
                result = await task
                if result.success:
                    results[agent_id] = result.result
                else:
                    errors.append(f"{agent_id}: {result.error}")
            except Exception as e:
                errors.append(f"{agent_id}: {str(e)}")

        return {
            "results": results,
            "errors": errors if errors else None,
            "success_count": len(results),
            "failure_count": len(errors),
        }


@workflow.defn
class SupervisorAgentWorkflow:
    """Workflow with a supervisor agent coordinating worker agents."""

    @workflow.run
    async def run(
        self,
        supervisor_id: str,
        worker_agents: List[str],
        task: Dict[str, Any],
        max_iterations: int = 10,
    ) -> Dict[str, Any]:
        _workflow_id = workflow.info().workflow_id
        iteration = 0
        context = {"task": task, "results": [], "status": "in_progress"}

        while iteration < max_iterations:
            iteration += 1

            # Ask supervisor what to do next
            supervisor_result = await workflow.execute_activity(
                invoke_agent,
                InvokeAgentInput(
                    agent_id=supervisor_id,
                    capability="coordinate",
                    input_data={
                        "context": context,
                        "available_agents": worker_agents,
                        "iteration": iteration,
                    },
                ),
                start_to_close_timeout=timedelta(minutes=5),
            )

            if not supervisor_result.success:
                raise Exception(f"Supervisor failed: {supervisor_result.error}")

            decision = supervisor_result.result or {}
            action = decision.get("action", "complete")

            if action == "complete":
                context["status"] = "completed"
                context["final_result"] = decision.get("result")
                break

            elif action == "delegate":
                # Delegate to a worker agent
                worker_id = decision.get("agent_id")
                worker_capability = decision.get("capability", "execute")
                worker_input = decision.get("input", {})

                worker_result = await workflow.execute_activity(
                    invoke_agent,
                    InvokeAgentInput(
                        agent_id=worker_id,
                        capability=worker_capability,
                        input_data=worker_input,
                    ),
                    start_to_close_timeout=timedelta(minutes=10),
                    retry_policy=RetryPolicy(maximum_attempts=2),
                )

                context["results"].append(
                    {
                        "iteration": iteration,
                        "agent": worker_id,
                        "success": worker_result.success,
                        "result": worker_result.result,
                        "error": worker_result.error,
                    }
                )

            elif action == "parallel":
                # Run multiple agents in parallel
                parallel_agents = decision.get("agents", [])
                parallel_input = decision.get("input", {})

                tasks = []
                for agent_id in parallel_agents:
                    task = workflow.execute_activity(
                        invoke_agent,
                        InvokeAgentInput(
                            agent_id=agent_id,
                            capability="execute",
                            input_data=parallel_input,
                        ),
                        start_to_close_timeout=timedelta(minutes=10),
                    )
                    tasks.append((agent_id, task))

                parallel_results = {}
                for agent_id, task in tasks:
                    result = await task
                    parallel_results[agent_id] = {
                        "success": result.success,
                        "result": result.result,
                        "error": result.error,
                    }

                context["results"].append(
                    {
                        "iteration": iteration,
                        "type": "parallel",
                        "results": parallel_results,
                    }
                )

        return context


@workflow.defn
class HumanInLoopWorkflow:
    """Workflow with human approval steps."""

    @workflow.run
    async def run(
        self,
        agent_id: str,
        capability: str,
        input_data: Dict[str, Any],
        approval_timeout_seconds: int = 3600,
    ) -> Dict[str, Any]:
        workflow_id = workflow.info().workflow_id

        # Execute agent
        result = await workflow.execute_activity(
            invoke_agent,
            InvokeAgentInput(
                agent_id=agent_id,
                capability=capability,
                input_data=input_data,
            ),
            start_to_close_timeout=timedelta(minutes=10),
        )

        if not result.success:
            raise Exception(result.error)

        # Wait for human approval
        approval = await workflow.execute_activity(
            wait_for_human_approval,
            args=[workflow_id, "review", approval_timeout_seconds],
            start_to_close_timeout=timedelta(seconds=approval_timeout_seconds + 60),
        )

        if not approval.get("approved"):
            return {
                "status": "rejected",
                "result": result.result,
                "rejection_reason": approval.get("comment"),
            }

        return {
            "status": "approved",
            "result": result.result,
            "approval": approval,
        }
