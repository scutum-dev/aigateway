"""
Pre-built workflow templates.
"""

from .research_agent import ResearchAgentWorkflow
from .coding_agent import CodingAgentWorkflow
from .data_analysis_agent import DataAnalysisWorkflow

__all__ = [
    "ResearchAgentWorkflow",
    "CodingAgentWorkflow",
    "DataAnalysisWorkflow",
]
