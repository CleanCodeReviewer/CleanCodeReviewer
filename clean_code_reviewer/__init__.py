"""Clean Code Reviewer - A CLI tool for LLM-powered code review against customizable rules."""

__version__ = "0.1.0"
__author__ = "Clean Code Reviewer Contributors"

from clean_code_reviewer.core.rules_engine import RulesEngine
from clean_code_reviewer.core.llm_client import LLMClient
from clean_code_reviewer.core.prompt_builder import PromptBuilder

__all__ = [
    "__version__",
    "RulesEngine",
    "LLMClient",
    "PromptBuilder",
]
