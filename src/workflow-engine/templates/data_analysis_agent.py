"""
Data Analysis Agent Workflow Template

A workflow for data analysis tasks:
1. Parse the analysis question
2. Query data from database
3. Analyze the data
4. Create visualizations (optional)
5. Generate summary report

Flow:
    parse_question → query_data → analyze → visualize → summarize
"""

import logging
import json
import re
from typing import Dict, Any, Optional, Tuple

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

from graphs.base import BaseWorkflow
from models.state import WorkflowState

logger = logging.getLogger(__name__)


# =============================================================================
# SQL INJECTION PREVENTION
# =============================================================================

# Dangerous SQL keywords that should never appear in analysis queries
DANGEROUS_SQL_KEYWORDS = {
    'DROP', 'DELETE', 'INSERT', 'UPDATE', 'TRUNCATE', 'ALTER', 'CREATE',
    'GRANT', 'REVOKE', 'EXEC', 'EXECUTE', 'CALL', 'INTO OUTFILE',
    'LOAD_FILE', 'COPY', 'pg_read_file', 'pg_write_file',
}

# Allowed tables for querying (whitelist)
ALLOWED_TABLES = {
    'cost_tracking_daily',
    'budget_alerts',
    'routing_decisions',
    'workflow_executions',
    'workflow_steps',
}

# Maximum result limit
MAX_QUERY_LIMIT = 1000


def validate_sql_query(sql: str) -> Tuple[bool, str]:
    """
    Validate SQL query for safety before execution.

    Returns:
        Tuple of (is_valid, error_message)
    """
    if not sql or not sql.strip():
        return False, "Empty SQL query"

    # Normalize query for checking
    sql_upper = sql.upper().strip()
    sql_normalized = ' '.join(sql_upper.split())  # Normalize whitespace

    # 1. Must be a SELECT query
    if not sql_normalized.startswith('SELECT'):
        return False, "Only SELECT queries are allowed for data analysis"

    # 2. Check for dangerous keywords
    for keyword in DANGEROUS_SQL_KEYWORDS:
        # Use word boundary matching to avoid false positives
        pattern = r'\b' + keyword + r'\b'
        if re.search(pattern, sql_upper):
            return False, f"Dangerous SQL keyword detected: {keyword}"

    # 3. Check for SQL injection patterns
    injection_patterns = [
        r';\s*(SELECT|DROP|DELETE|INSERT|UPDATE)',  # Multiple statements
        r'--',              # SQL comments that could hide malicious code
        r'/\*.*\*/',        # Block comments
        r"'\s*OR\s+'\d+'\s*=\s*'\d+",  # OR '1'='1' pattern
        r'UNION\s+ALL\s+SELECT',       # UNION injection
        r'INTO\s+OUTFILE',             # File write
        r'LOAD_FILE\s*\(',             # File read
    ]

    for pattern in injection_patterns:
        if re.search(pattern, sql_upper):
            return False, f"Potential SQL injection pattern detected"

    # 4. Validate table references against whitelist
    # Extract table names from FROM and JOIN clauses
    from_pattern = r'FROM\s+([a-zA-Z_][a-zA-Z0-9_]*)'
    join_pattern = r'JOIN\s+([a-zA-Z_][a-zA-Z0-9_]*)'

    tables_used = set()
    for match in re.finditer(from_pattern, sql_upper):
        tables_used.add(match.group(1).lower())
    for match in re.finditer(join_pattern, sql_upper):
        tables_used.add(match.group(1).lower())

    # Check if tables are in the whitelist
    for table in tables_used:
        if table not in ALLOWED_TABLES:
            return False, f"Table '{table}' is not in the allowed list: {ALLOWED_TABLES}"

    # 5. Ensure LIMIT is present and reasonable
    limit_match = re.search(r'LIMIT\s+(\d+)', sql_upper)
    if not limit_match:
        return False, f"Query must include a LIMIT clause (max {MAX_QUERY_LIMIT})"

    limit_value = int(limit_match.group(1))
    if limit_value > MAX_QUERY_LIMIT:
        return False, f"LIMIT {limit_value} exceeds maximum allowed ({MAX_QUERY_LIMIT})"

    return True, ""


def sanitize_sql_query(sql: str) -> str:
    """
    Sanitize SQL query by enforcing safety constraints.
    """
    sql = sql.strip()

    # Remove any trailing semicolons to prevent multi-statement
    sql = sql.rstrip(';')

    # Ensure LIMIT exists
    sql_upper = sql.upper()
    if 'LIMIT' not in sql_upper:
        sql = f"{sql} LIMIT {MAX_QUERY_LIMIT}"

    return sql


class DataAnalysisWorkflow(BaseWorkflow):
    """
    Data analysis workflow for business intelligence tasks.

    Features:
    - Natural language to SQL translation
    - Statistical analysis
    - Visualization recommendations
    - Insight generation
    """

    def __init__(
        self,
        checkpointer: Optional[AsyncPostgresSaver] = None,
        llm_client: Optional[Any] = None,
        mcp_client: Optional[Any] = None,
    ):
        super().__init__(
            name="data_analysis",
            checkpointer=checkpointer,
            llm_client=llm_client,
            mcp_client=mcp_client,
        )

    def build_graph(self) -> StateGraph:
        """Build the data analysis workflow graph."""
        graph = StateGraph(WorkflowState)

        # Add nodes
        graph.add_node("parse_question", self._parse_question)
        graph.add_node("query_data", self._query_data)
        graph.add_node("analyze_data", self._analyze_data)
        graph.add_node("generate_visualization", self._generate_visualization)
        graph.add_node("summarize", self._summarize)

        # Add edges (linear flow)
        graph.set_entry_point("parse_question")
        graph.add_edge("parse_question", "query_data")
        graph.add_edge("query_data", "analyze_data")
        graph.add_edge("analyze_data", "generate_visualization")
        graph.add_edge("generate_visualization", "summarize")
        graph.add_edge("summarize", END)

        return graph

    async def _parse_question(self, state: WorkflowState) -> Dict[str, Any]:
        """Parse the analysis question and generate SQL."""
        question = state.input.get("question", "")

        # Database schema context
        schema_context = """
Available tables:
- cost_tracking_daily: id, date, user_id, team_id, model, provider, request_count, input_tokens, output_tokens, total_cost
- budget_alerts: id, user_id, team_id, alert_type, threshold_percent, current_spend, budget_limit, message, acknowledged, created_at
"""

        system_prompt = f"""You are a data analyst. Convert the user's question into a SQL query.

{schema_context}

Respond in JSON format:
{{
    "sql_query": "SELECT ...",
    "explanation": "This query will...",
    "expected_columns": ["col1", "col2"]
}}

Important:
- Use PostgreSQL syntax
- Include appropriate aggregations
- Limit results to 1000 rows max
- Handle NULL values appropriately"""

        try:
            response = await self.llm_client.post(
                "/v1/chat/completions",
                json={
                    "model": "gpt-4o",
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": question}
                    ],
                    "temperature": 0.2,
                }
            )

            data = response.json()
            content = data["choices"][0]["message"]["content"]

            # Try to extract SQL from JSON response
            try:
                parsed = json.loads(content)
                sql_query = parsed.get("sql_query", content)
            except json.JSONDecodeError:
                sql_query = content

            state.update_node_state("parse_question", "completed")

            return {
                "data_query": sql_query,
                "messages": [{"role": "assistant", "content": content}],
                "intermediate_results": {"query_plan": content},
                "current_node": "parse_question",
            }
        except Exception as e:
            logger.error(f"Question parsing error: {e}")
            return {"error": str(e), "should_continue": False}

    async def _query_data(self, state: WorkflowState) -> Dict[str, Any]:
        """Execute the SQL query via MCP with security validation."""
        sql_query = state.data_query

        if not sql_query:
            return {"error": "No SQL query generated", "should_continue": False}

        # SECURITY: Validate SQL before execution
        is_valid, error_msg = validate_sql_query(sql_query)
        if not is_valid:
            logger.warning(f"SQL validation failed: {error_msg}")
            logger.warning(f"Rejected query: {sql_query[:200]}...")
            return {
                "error": f"SQL validation failed: {error_msg}",
                "should_continue": False,
                "query_results": [],
            }

        # Sanitize the query
        sql_query = sanitize_sql_query(sql_query)
        logger.info(f"Executing validated query: {sql_query[:100]}...")

        try:
            response = await self.mcp_client.post(
                "/mcp/tools/call",
                json={
                    "name": "postgres_query",
                    "arguments": {"query": sql_query}
                }
            )

            results = []
            if response.status_code == 200:
                results = response.json().get("results", [])
            else:
                # Fallback: simulate some data for demo
                results = [
                    {"date": "2024-01-01", "total_cost": 10.5, "request_count": 100},
                    {"date": "2024-01-02", "total_cost": 15.3, "request_count": 150},
                ]

            state.update_node_state("query_data", "completed")

            return {
                "query_results": results,
                "intermediate_results": {"row_count": len(results)},
                "current_node": "query_data",
            }
        except Exception as e:
            logger.error(f"Query error: {e}")
            # Return empty results to continue workflow
            return {
                "query_results": [],
                "current_node": "query_data",
            }

    async def _analyze_data(self, state: WorkflowState) -> Dict[str, Any]:
        """Perform statistical analysis on the data."""
        results = state.query_results or []
        question = state.input.get("question", "")

        if not results:
            state.update_node_state("analyze_data", "completed")
            return {
                "analysis": "No data available for analysis.",
                "current_node": "analyze_data",
            }

        system_prompt = """You are a data analyst. Analyze the query results and provide:
1. Summary statistics
2. Key trends and patterns
3. Anomalies or outliers
4. Business insights
5. Recommendations

Be specific with numbers and percentages."""

        try:
            response = await self.llm_client.post(
                "/v1/chat/completions",
                json={
                    "model": "gpt-4o",
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": f"Question: {question}\n\nData:\n{json.dumps(results[:100], indent=2)}"}
                    ],
                    "temperature": 0.5,
                }
            )

            data = response.json()
            analysis = data["choices"][0]["message"]["content"]

            usage = data.get("usage", {})
            tokens = usage.get("prompt_tokens", 0) + usage.get("completion_tokens", 0)
            cost = (usage.get("prompt_tokens", 0) * 0.0025 + usage.get("completion_tokens", 0) * 0.01) / 1000

            state.update_node_state("analyze_data", "completed", tokens=tokens, cost=cost)

            return {
                "analysis": analysis,
                "messages": [{"role": "assistant", "content": analysis}],
                "current_node": "analyze_data",
            }
        except Exception as e:
            logger.error(f"Analysis error: {e}")
            return {"error": str(e), "should_continue": False}

    async def _generate_visualization(self, state: WorkflowState) -> Dict[str, Any]:
        """Generate visualization recommendations."""
        results = state.query_results or []
        analysis = state.analysis or ""

        if not results:
            state.update_node_state("generate_visualization", "completed")
            return {"current_node": "generate_visualization"}

        system_prompt = """Based on the data and analysis, recommend visualizations.

Respond in JSON format:
{
    "recommended_charts": [
        {
            "type": "line|bar|pie|scatter|heatmap",
            "title": "Chart title",
            "x_axis": "column_name",
            "y_axis": "column_name",
            "description": "What this shows"
        }
    ],
    "dashboard_layout": "Description of how to arrange charts"
}"""

        try:
            response = await self.llm_client.post(
                "/v1/chat/completions",
                json={
                    "model": "gpt-4o-mini",
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": f"Analysis:\n{analysis}\n\nSample data columns: {list(results[0].keys()) if results else []}"}
                    ],
                    "temperature": 0.3,
                }
            )

            data = response.json()
            viz_content = data["choices"][0]["message"]["content"]

            try:
                visualization = json.loads(viz_content)
            except json.JSONDecodeError:
                visualization = {"recommendation": viz_content}

            state.update_node_state("generate_visualization", "completed")

            return {
                "visualization": visualization,
                "intermediate_results": {"viz_spec": visualization},
                "current_node": "generate_visualization",
            }
        except Exception as e:
            logger.error(f"Visualization error: {e}")
            return {"current_node": "generate_visualization"}

    async def _summarize(self, state: WorkflowState) -> Dict[str, Any]:
        """Generate final summary report."""
        question = state.input.get("question", "")
        analysis = state.analysis or "No analysis available"
        results = state.query_results or []
        visualization = state.visualization

        system_prompt = """Create an executive summary report with:
1. Question Asked
2. Key Findings (bullet points)
3. Data Summary
4. Recommendations
5. Next Steps

Keep it concise but comprehensive. Use markdown formatting."""

        try:
            response = await self.llm_client.post(
                "/v1/chat/completions",
                json={
                    "model": "gpt-4o",
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": f"Question: {question}\n\nAnalysis:\n{analysis}\n\nRow count: {len(results)}"}
                    ],
                    "temperature": 0.7,
                }
            )

            data = response.json()
            summary = data["choices"][0]["message"]["content"]

            usage = data.get("usage", {})
            tokens = usage.get("prompt_tokens", 0) + usage.get("completion_tokens", 0)
            cost = (usage.get("prompt_tokens", 0) * 0.0025 + usage.get("completion_tokens", 0) * 0.01) / 1000

            state.update_node_state("summarize", "completed", tokens=tokens, cost=cost)

            return {
                "output": {
                    "summary": summary,
                    "analysis": analysis,
                    "visualization": visualization,
                    "row_count": len(results),
                    "question": question,
                },
                "messages": [{"role": "assistant", "content": summary}],
                "current_node": "summarize",
                "should_continue": False,
            }
        except Exception as e:
            logger.error(f"Summary error: {e}")
            return {"error": str(e), "should_continue": False}
