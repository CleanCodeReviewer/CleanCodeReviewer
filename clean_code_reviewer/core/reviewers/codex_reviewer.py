"""OpenAI Codex CLI reviewer implementation."""

from __future__ import annotations

from clean_code_reviewer.core.reviewers.cli_reviewer_base import CLIReviewerBase


class CodexReviewer(CLIReviewerBase):
    """Reviewer using OpenAI Codex CLI."""

    @property
    def name(self) -> str:
        """Return the reviewer name."""
        return "codex"

    @property
    def cli_command(self) -> str:
        """Return the CLI command name."""
        return "codex"

    @property
    def install_hint(self) -> str:
        """Return installation instructions."""
        return "npm install -g @openai/codex"
