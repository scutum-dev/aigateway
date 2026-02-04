"""
Research Agent Workflow Template

A multi-step research workflow that:
1. Parses the research query
2. Searches web and databases in parallel
3. Analyzes and synthesizes results
4. Generates a comprehensive report

Flow:
    parse_query → [search_web, search_database] → analyze_results → generate_report
"""

import logging
from typing import Dict, Any, Optional

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

from graphs.base import BaseWorkflow
from models.state import WorkflowState

logger = logging.getLogger(__name__)


class ResearchAgentWorkflow(BaseWorkflow):
    """
    Research agent workflow for comprehensive information gathering.

    Capable of:
    - Web search via Brave Search MCP
    - Database queries via PostgreSQL MCP
    - Multi-source synthesis
    - Structured report generation
    """

    def __init__(
        self,
        checkpointer: Optional[AsyncPostgresSaver] = None,
        llm_client: Optional[Any] = None,
        mcp_client: Optional[Any] = None,
    ):
        super().__init__(
            name="research_agent",
            checkpointer=checkpointer,
            llm_client=llm_client,
            mcp_client=mcp_client,
        )

    def build_graph(self) -> StateGraph:
        """Build the research workflow graph."""
        graph = StateGraph(WorkflowState)

        # Add nodes
        graph.add_node("parse_query", self._parse_query)
        graph.add_node("search_web", self._search_web)
        graph.add_node("search_database", self._search_database)
        graph.add_node("analyze_results", self._analyze_results)
        graph.add_node("generate_report", self._generate_report)

        # Add edges
        graph.set_entry_point("parse_query")
        graph.add_edge("parse_query", "search_web")
        graph.add_edge("parse_query", "search_database")
        graph.add_edge("search_web", "analyze_results")
        graph.add_edge("search_database", "analyze_results")
        graph.add_edge("analyze_results", "generate_report")
        graph.add_edge("generate_report", END)

        return graph

    async def _parse_query(self, state: WorkflowState) -> Dict[str, Any]:
        """Parse and understand the research query."""
        query = state.input.get("query", "")

        system_prompt = """You are a research query analyzer. Parse the user's research query and:
1. Identify key topics and entities
2. Determine search keywords
3. Identify relevant database tables to query
4. Output a structured plan

Respond in JSON format:
{
    "topics": ["topic1", "topic2"],
    "search_keywords": ["keyword1", "keyword2"],
    "database_queries": ["query description 1"],
    "research_plan": "brief plan description"
}"""

        try:
            response = await self.llm_client.post(
                "/v1/chat/completions",
                json={
                    "model": "gpt-4o-mini",
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": f"Research query: {query}"}
                    ],
                    "temperature": 0.3,
                }
            )

            data = response.json()
            content = data["choices"][0]["message"]["content"]

            state.update_node_state("parse_query", "completed")

            return {
                "messages": [{"role": "assistant", "content": content}],
                "intermediate_results": {"parsed_query": content},
                "current_node": "parse_query",
            }
        except Exception as e:
            logger.error(f"Parse query error: {e}")
            return {"error": str(e), "should_continue": False}

    async def _search_web(self, state: WorkflowState) -> Dict[str, Any]:
        """Search the web using Brave Search MCP."""
        query = state.input.get("query", "")

        try:
            # Call Brave Search via MCP
            response = await self.mcp_client.post(
                "/mcp/tools/call",
                json={
                    "name": "brave_search",
                    "arguments": {"query": query, "count": 10}
                }
            )

            results = []
            if response.status_code == 200:
                results = response.json().get("results", [])

            state.update_node_state("search_web", "completed")

            return {
                "search_results": (state.search_results or []) + results,
                "intermediate_results": {"web_results": results},
                "current_node": "search_web",
            }
        except Exception as e:
            logger.error(f"Web search error: {e}")
            # Continue even if search fails
            return {"intermediate_results": {"web_results": []}}

    async def _search_database(self, state: WorkflowState) -> Dict[str, Any]:
        """Search internal database for relevant data."""
        try:
            # Example: query cost tracking data
            response = await self.mcp_client.post(
                "/mcp/tools/call",
                json={
                    "name": "postgres_query",
                    "arguments": {
                        "query": "SELECT * FROM cost_tracking_daily ORDER BY date DESC LIMIT 10"
                    }
                }
            )

            results = []
            if response.status_code == 200:
                results = response.json().get("results", [])

            state.update_node_state("search_database", "completed")

            return {
                "search_results": (state.search_results or []) + [{"source": "database", "data": results}],
                "intermediate_results": {"db_results": results},
                "current_node": "search_database",
            }
        except Exception as e:
            logger.error(f"Database search error: {e}")
            return {"intermediate_results": {"db_results": []}}

    async def _analyze_results(self, state: WorkflowState) -> Dict[str, Any]:
        """Analyze and synthesize all search results."""
        results = state.search_results or []

        system_prompt = """You are a research analyst. Analyze the provided search results and:
1. Identify key findings
2. Note contradictions or gaps
3. Synthesize main themes
4. Rate source reliability

Provide a structured analysis."""

        try:
            response = await self.llm_client.post(
                "/v1/chat/completions",
                json={
                    "model": "gpt-4o",
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": f"Search results:\n{results}"}
                    ],
                    "temperature": 0.5,
                }
            )

            data = response.json()
            analysis = data["choices"][0]["message"]["content"]

            usage = data.get("usage", {})
            tokens = usage.get("prompt_tokens", 0) + usage.get("completion_tokens", 0)
            cost = (usage.get("prompt_tokens", 0) * 0.0025 + usage.get("completion_tokens", 0) * 0.01) / 1000

            state.update_node_state("analyze_results", "completed", tokens=tokens, cost=cost)

            return {
                "analysis": analysis,
                "messages": [{"role": "assistant", "content": analysis}],
                "current_node": "analyze_results",
            }
        except Exception as e:
            logger.error(f"Analysis error: {e}")
            return {"error": str(e), "should_continue": False}

    async def _generate_report(self, state: WorkflowState) -> Dict[str, Any]:
        """Generate the final research report."""
        analysis = state.analysis or "No analysis available"
        query = state.input.get("query", "")

        system_prompt = """You are a research report writer. Generate a comprehensive research report with:
1. Executive Summary
2. Key Findings
3. Detailed Analysis
4. Conclusions
5. Recommendations

Use markdown formatting."""

        try:
            response = await self.llm_client.post(
                "/v1/chat/completions",
                json={
                    "model": "gpt-4o",
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": f"Query: {query}\n\nAnalysis:\n{analysis}"}
                    ],
                    "temperature": 0.7,
                    "max_tokens": 4000,
                }
            )

            data = response.json()
            report = data["choices"][0]["message"]["content"]

            usage = data.get("usage", {})
            tokens = usage.get("prompt_tokens", 0) + usage.get("completion_tokens", 0)
            cost = (usage.get("prompt_tokens", 0) * 0.0025 + usage.get("completion_tokens", 0) * 0.01) / 1000

            state.update_node_state("generate_report", "completed", tokens=tokens, cost=cost)

            return {
                "output": {"report": report, "query": query},
                "messages": [{"role": "assistant", "content": report}],
                "current_node": "generate_report",
                "should_continue": False,
            }
        except Exception as e:
            logger.error(f"Report generation error: {e}")
            return {"error": str(e), "should_continue": False}
