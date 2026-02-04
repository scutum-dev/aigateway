"""
Conditional edge functions for LangGraph workflows.
"""

from typing import Literal
from models.state import WorkflowState


def should_continue(state: WorkflowState) -> Literal["continue", "end"]:
    """
    Check if workflow should continue or end.

    Args:
        state: Current workflow state

    Returns:
        "continue" or "end"
    """
    if state.error:
        return "end"
    if not state.should_continue:
        return "end"
    return "continue"


def check_iteration_limit(
    state: WorkflowState,
    max_iterations: int = 5
) -> Literal["continue", "end"]:
    """
    Check if iteration limit has been reached.

    Args:
        state: Current workflow state
        max_iterations: Maximum allowed iterations

    Returns:
        "continue" or "end"
    """
    if state.iteration_count >= max_iterations:
        return "end"
    return "continue"


def coding_router(state: WorkflowState) -> Literal["analyze", "finalize"]:
    """
    Router for coding workflow - decide if code needs more work.

    Args:
        state: Current workflow state

    Returns:
        "analyze" to iterate, "finalize" to complete
    """
    # Check iteration limit
    if state.iteration_count >= 5:
        return "finalize"

    # Check if analysis indicates issues
    if state.code_analysis:
        analysis_lower = state.code_analysis.lower()
        if any(word in analysis_lower for word in ["error", "bug", "issue", "fix", "improve"]):
            return "analyze"

    return "finalize"


def research_router(state: WorkflowState) -> Literal["search_more", "analyze", "report"]:
    """
    Router for research workflow - decide next step.

    Args:
        state: Current workflow state

    Returns:
        Next node name
    """
    # If no search results yet, search
    if not state.search_results:
        return "search_more"

    # If we have results but no analysis, analyze
    if not state.analysis:
        return "analyze"

    # If results are insufficient, search more
    if len(state.search_results) < 3 and state.iteration_count < 3:
        return "search_more"

    # Generate report
    return "report"


def data_analysis_router(state: WorkflowState) -> Literal["query", "analyze", "visualize", "summarize"]:
    """
    Router for data analysis workflow.

    Args:
        state: Current workflow state

    Returns:
        Next node name
    """
    # If no query results, run query
    if not state.query_results:
        return "query"

    # If no analysis yet, analyze
    if not state.analysis:
        return "analyze"

    # If no visualization and data supports it
    if not state.visualization and state.query_results:
        return "visualize"

    return "summarize"


def error_router(state: WorkflowState) -> Literal["retry", "escalate", "end"]:
    """
    Router for error handling.

    Args:
        state: Current workflow state

    Returns:
        Next action
    """
    if not state.error:
        return "end"

    # Check retry count
    if state.iteration_count < 3:
        return "retry"

    return "escalate"
