"""Grounded account research: reads a company's own website, answers ICP
questions with quoted evidence, and verifies every quote before scoring."""
from .icp import ICP, load_icp
from .pipeline import research
from .report import to_markdown

__all__ = ["ICP", "load_icp", "research", "to_markdown"]
__version__ = "1.0.0"
