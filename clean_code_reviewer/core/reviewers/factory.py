"""Factory functions for creating reviewers."""

from __future__ import annotations

from typing import Any, Literal

from clean_code_reviewer.core.reviewers.base import Reviewer
from clean_code_reviewer.core.reviewers.claudecode_reviewer import ClaudeCodeReviewer
from clean_code_reviewer.core.reviewers.codex_reviewer import CodexReviewer
from clean_code_reviewer.core.reviewers.gemini_reviewer import GeminiReviewer
from clean_code_reviewer.core.reviewers.litellm_reviewer import LiteLLMReviewer

ReviewerType = Literal["litellm", "claudecode", "gemini", "codex"]

REVIEWER_CLASSES: dict[str, type[Reviewer]] = {
    "litellm": LiteLLMReviewer,
    "claudecode": ClaudeCodeReviewer,
    "gemini": GeminiReviewer,
    "codex": CodexReviewer,
}


def get_reviewer(reviewer_type: str, **kwargs: Any) -> Reviewer:
    """
    Factory function to create a reviewer.

    Args:
        reviewer_type: Type of reviewer (litellm, claudecode, gemini, codex)
        **kwargs: Additional arguments passed to the reviewer constructor

    Returns:
        A Reviewer instance

    Raises:
        ValueError: If reviewer_type is not recognized
    """
    cls = REVIEWER_CLASSES.get(reviewer_type)
    if cls is None:
        available = ", ".join(REVIEWER_CLASSES.keys())
        raise ValueError(f"Unknown reviewer type: {reviewer_type}. Available: {available}")

    # Only pass kwargs that the constructor accepts
    if reviewer_type == "litellm":
        return cls(**kwargs)
    else:
        # CLI reviewers don't take constructor arguments
        return cls()


def get_available_reviewers() -> list[str]:
    """
    Return list of available/configured reviewers.

    Returns:
        List of reviewer names that are available
    """
    available = []
    for name, cls in REVIEWER_CLASSES.items():
        try:
            instance = cls() if name != "litellm" else cls()
            if instance.is_available():
                available.append(name)
        except Exception:
            # Skip reviewers that fail to instantiate
            pass
    return available


def get_all_reviewer_types() -> list[str]:
    """
    Return list of all supported reviewer types.

    Returns:
        List of all reviewer type names
    """
    return list(REVIEWER_CLASSES.keys())
