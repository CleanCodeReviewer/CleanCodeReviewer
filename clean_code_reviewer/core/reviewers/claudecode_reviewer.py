"""Claude Code CLI reviewer implementation."""

from __future__ import annotations

from clean_code_reviewer.core.reviewers.cli_reviewer_base import CLIReviewerBase


class ClaudeCodeReviewer(CLIReviewerBase):
    """Reviewer using Claude Code CLI."""

    @property
    def name(self) -> str:
        """Return the reviewer name."""
        return "claudecode"

    @property
    def cli_command(self) -> str:
        """Return the CLI command name."""
        return "claude"

    @property
    def install_hint(self) -> str:
        """Return installation instructions."""
        return "npm install -g @anthropic-ai/claude-code"
