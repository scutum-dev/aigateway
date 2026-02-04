"""
Coding Agent Workflow Template

A cyclic workflow for code generation and refinement:
1. Understand the task
2. Read relevant code (optional)
3. Generate code
4. Analyze generated code
5. If issues found, iterate back to generation
6. Finalize and output

Flow:
    understand_task → read_code → generate_code → analyze_code
                                        ↑              │
                                        └──(if issues)─┘
                                               ↓
                                        finalize_code
"""

import logging
from typing import Dict, Any, Optional, Literal

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

from graphs.base import BaseWorkflow
from models.state import WorkflowState

logger = logging.getLogger(__name__)


class CodingAgentWorkflow(BaseWorkflow):
    """
    Coding agent workflow for code generation and improvement.

    Features:
    - Context-aware code generation
    - Iterative refinement
    - Code analysis and bug detection
    - Filesystem integration via MCP
    """

    MAX_ITERATIONS = 5

    def __init__(
        self,
        checkpointer: Optional[AsyncPostgresSaver] = None,
        llm_client: Optional[Any] = None,
        mcp_client: Optional[Any] = None,
    ):
        super().__init__(
            name="coding_agent",
            checkpointer=checkpointer,
            llm_client=llm_client,
            mcp_client=mcp_client,
        )

    def build_graph(self) -> StateGraph:
        """Build the coding workflow graph."""
        graph = StateGraph(WorkflowState)

        # Add nodes
        graph.add_node("understand_task", self._understand_task)
        graph.add_node("read_code", self._read_code)
        graph.add_node("generate_code", self._generate_code)
        graph.add_node("analyze_code", self._analyze_code)
        graph.add_node("finalize_code", self._finalize_code)

        # Add edges
        graph.set_entry_point("understand_task")
        graph.add_edge("understand_task", "read_code")
        graph.add_edge("read_code", "generate_code")
        graph.add_edge("generate_code", "analyze_code")

        # Conditional edge: analyze → generate (loop) or finalize
        graph.add_conditional_edges(
            "analyze_code",
            self._should_iterate,
            {
                "iterate": "generate_code",
                "finalize": "finalize_code",
            }
        )

        graph.add_edge("finalize_code", END)

        return graph

    def _should_iterate(self, state: WorkflowState) -> Literal["iterate", "finalize"]:
        """Decide if code needs more iteration."""
        # Check iteration limit
        if state.iteration_count >= self.MAX_ITERATIONS:
            return "finalize"

        # Check if analysis indicates issues
        if state.code_analysis:
            analysis_lower = state.code_analysis.lower()
            issue_indicators = ["error", "bug", "issue", "fix", "improve", "missing", "incorrect"]
            if any(word in analysis_lower for word in issue_indicators):
                return "iterate"

        return "finalize"

    async def _understand_task(self, state: WorkflowState) -> Dict[str, Any]:
        """Understand and break down the coding task."""
        task = state.input.get("task", "")
        language = state.input.get("language", "python")

        system_prompt = f"""You are a senior software engineer analyzing a coding task.

Task: {task}
Language: {language}

Analyze the task and provide:
1. Task breakdown into steps
2. Key requirements
3. Potential challenges
4. Files that might need to be read for context

Respond in JSON format:
{{
    "steps": ["step1", "step2"],
    "requirements": ["req1", "req2"],
    "challenges": ["challenge1"],
    "context_files": ["file1.py"]
}}"""

        try:
            response = await self.llm_client.post(
                "/v1/chat/completions",
                json={
                    "model": "gpt-4o",
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": task}
                    ],
                    "temperature": 0.3,
                }
            )

            data = response.json()
            content = data["choices"][0]["message"]["content"]

            state.update_node_state("understand_task", "completed")

            return {
                "messages": [{"role": "assistant", "content": content}],
                "intermediate_results": {"task_analysis": content},
                "current_node": "understand_task",
            }
        except Exception as e:
            logger.error(f"Task understanding error: {e}")
            return {"error": str(e), "should_continue": False}

    async def _read_code(self, state: WorkflowState) -> Dict[str, Any]:
        """Read relevant code files for context."""
        files_to_read = state.input.get("context_files", [])

        if not files_to_read:
            # Try to extract from task analysis
            analysis = state.intermediate_results.get("task_analysis", "")
            # Simple extraction - in production, parse JSON properly
            state.update_node_state("read_code", "completed")
            return {"current_node": "read_code"}

        code_context = []

        for file_path in files_to_read[:5]:  # Limit files
            try:
                response = await self.mcp_client.post(
                    "/mcp/tools/call",
                    json={
                        "name": "read_file",
                        "arguments": {"path": file_path}
                    }
                )

                if response.status_code == 200:
                    content = response.json().get("content", "")
                    code_context.append(f"# File: {file_path}\n{content}")
            except Exception as e:
                logger.warning(f"Could not read {file_path}: {e}")

        combined_context = "\n\n".join(code_context) if code_context else "No context files available"

        state.update_node_state("read_code", "completed")

        return {
            "code_context": combined_context,
            "current_node": "read_code",
        }

    async def _generate_code(self, state: WorkflowState) -> Dict[str, Any]:
        """Generate code based on task and context."""
        task = state.input.get("task", "")
        language = state.input.get("language", "python")
        context = state.code_context or ""
        previous_code = state.generated_code
        previous_analysis = state.code_analysis

        system_prompt = f"""You are an expert {language} programmer. Generate clean, well-documented code.

Follow these guidelines:
1. Write clear, readable code
2. Include appropriate error handling
3. Add docstrings and comments
4. Follow {language} best practices
5. Make the code production-ready"""

        user_message = f"Task: {task}"
        if context:
            user_message += f"\n\nContext code:\n{context}"
        if previous_code and previous_analysis:
            user_message += f"\n\nPrevious attempt:\n{previous_code}\n\nIssues found:\n{previous_analysis}\n\nPlease fix these issues."

        try:
            response = await self.llm_client.post(
                "/v1/chat/completions",
                json={
                    "model": "gpt-4o",
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_message}
                    ],
                    "temperature": 0.2,
                    "max_tokens": 4000,
                }
            )

            data = response.json()
            code = data["choices"][0]["message"]["content"]

            usage = data.get("usage", {})
            tokens = usage.get("prompt_tokens", 0) + usage.get("completion_tokens", 0)
            cost = (usage.get("prompt_tokens", 0) * 0.0025 + usage.get("completion_tokens", 0) * 0.01) / 1000

            state.update_node_state("generate_code", "completed", tokens=tokens, cost=cost)

            return {
                "generated_code": code,
                "messages": [{"role": "assistant", "content": code}],
                "current_node": "generate_code",
                "iteration_count": state.iteration_count + 1,
            }
        except Exception as e:
            logger.error(f"Code generation error: {e}")
            return {"error": str(e), "should_continue": False}

    async def _analyze_code(self, state: WorkflowState) -> Dict[str, Any]:
        """Analyze generated code for issues."""
        code = state.generated_code or ""
        language = state.input.get("language", "python")

        system_prompt = f"""You are a code reviewer specializing in {language}. Analyze the code for:
1. Bugs and errors
2. Security vulnerabilities
3. Performance issues
4. Code style violations
5. Missing edge cases

If the code is good, say "APPROVED" at the start.
If issues exist, list them clearly for the developer to fix."""

        try:
            response = await self.llm_client.post(
                "/v1/chat/completions",
                json={
                    "model": "gpt-4o",
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": f"Review this code:\n\n{code}"}
                    ],
                    "temperature": 0.3,
                }
            )

            data = response.json()
            analysis = data["choices"][0]["message"]["content"]

            usage = data.get("usage", {})
            tokens = usage.get("prompt_tokens", 0) + usage.get("completion_tokens", 0)
            cost = (usage.get("prompt_tokens", 0) * 0.0025 + usage.get("completion_tokens", 0) * 0.01) / 1000

            state.update_node_state("analyze_code", "completed", tokens=tokens, cost=cost)

            return {
                "code_analysis": analysis,
                "messages": [{"role": "assistant", "content": f"Code Analysis:\n{analysis}"}],
                "current_node": "analyze_code",
            }
        except Exception as e:
            logger.error(f"Code analysis error: {e}")
            return {"error": str(e), "should_continue": False}

    async def _finalize_code(self, state: WorkflowState) -> Dict[str, Any]:
        """Finalize and output the code."""
        code = state.generated_code or ""
        analysis = state.code_analysis or ""
        iterations = state.iteration_count

        state.update_node_state("finalize_code", "completed")

        return {
            "output": {
                "code": code,
                "analysis": analysis,
                "iterations": iterations,
                "language": state.input.get("language", "python"),
            },
            "current_node": "finalize_code",
            "should_continue": False,
        }
