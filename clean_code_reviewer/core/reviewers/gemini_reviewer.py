"""Gemini CLI reviewer implementation."""

from __future__ import annotations

from clean_code_reviewer.core.reviewers.cli_reviewer_base import CLIReviewerBase


class GeminiReviewer(CLIReviewerBase):
    """Reviewer using Gemini CLI."""

    @property
    def name(self) -> str:
        """Return the reviewer name."""
        return "gemini"

    @property
    def cli_command(self) -> str:
        """Return the CLI command name."""
        return "gemini"

    @property
    def install_hint(self) -> str:
        """Return installation instructions."""
        return "npm install -g @anthropic-ai/gemini-cli or pip install google-genai"
