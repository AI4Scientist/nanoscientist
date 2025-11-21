"""MSR-Scientist: A minimalist self-evolving researcher agent."""

__version__ = "0.1.0"

from .agent import ResearchAgent
from .research import ResearchWorkflow

__all__ = ["ResearchAgent", "ResearchWorkflow"]
