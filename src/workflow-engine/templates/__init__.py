"""
Pre-built workflow templates.
"""

from .coding_agent import CodingAgentWorkflow
from .data_analysis_agent import DataAnalysisWorkflow
from .research_agent import ResearchAgentWorkflow

__all__ = [
    "ResearchAgentWorkflow",
    "CodingAgentWorkflow",
    "DataAnalysisWorkflow",
]
