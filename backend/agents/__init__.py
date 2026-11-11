"""
Agents Package for Support Engineer Dashboard
Exports CodeAnalysisAgent and system prompt utilities for Alex Turner.
"""
from .code_analysis_agent import CodeAnalysisAgent
from .system_prompt import build_system_prompt, SYSTEM_PROMPT_TEMPLATE

__all__ = ["CodeAnalysisAgent", "build_system_prompt", "SYSTEM_PROMPT_TEMPLATE"]
