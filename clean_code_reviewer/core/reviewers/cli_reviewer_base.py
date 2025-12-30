"""Base class for CLI-based reviewers."""

from __future__ import annotations

import shutil
import subprocess
from abc import abstractmethod
from typing import Iterator

from clean_code_reviewer.core.reviewers.base import ReviewRequest, ReviewResponse, Reviewer
from clean_code_reviewer.utils.logger import get_logger

logger = get_logger(__name__)


class CLIReviewerBase(Reviewer):
    """Base class for CLI-based reviewers (claude, gemini, codex)."""

    # Timeout for CLI commands in seconds
    TIMEOUT = 600  # 10 minutes

    @property
    @abstractmethod
    def cli_command(self) -> str:
        """Return the CLI command name."""
        ...

    @property
    @abstractmethod
    def install_hint(self) -> str:
        """Return installation instructions."""
        ...

    def is_available(self) -> bool:
        """Check if CLI tool is installed."""
        return shutil.which(self.cli_command) is not None

    def _build_prompt(self, request: ReviewRequest) -> str:
        """Build the full prompt from system and user prompts."""
        return f"{request.system_prompt}\n\n{request.user_prompt}"

    def review(self, request: ReviewRequest) -> ReviewResponse:
        """Execute CLI and return result."""
        if not self.is_available():
            return ReviewResponse(
                content="",
                reviewer=self.name,
                error=f"{self.cli_command} CLI not found. Install with: {self.install_hint}",
            )

        full_prompt = self._build_prompt(request)

        logger.info(f"Running {self.cli_command} CLI for review")

        try:
            result = subprocess.run(
                [self.cli_command],
                input=full_prompt,
                capture_output=True,
                text=True,
                timeout=self.TIMEOUT,
            )

            if result.returncode != 0:
                error_msg = result.stderr.strip() if result.stderr else f"Exit code: {result.returncode}"
                return ReviewResponse(
                    content="",
                    reviewer=self.name,
                    error=f"CLI error: {error_msg}",
                )

            return ReviewResponse(
                content=result.stdout.strip(),
                reviewer=self.name,
            )

        except subprocess.TimeoutExpired:
            return ReviewResponse(
                content="",
                reviewer=self.name,
                error=f"CLI timeout after {self.TIMEOUT} seconds",
            )
        except Exception as e:
            logger.error(f"Error running {self.cli_command}: {e}")
            return ReviewResponse(
                content="",
                reviewer=self.name,
                error=str(e),
            )

    def review_stream(self, request: ReviewRequest) -> Iterator[str]:
        """
        Perform a streaming review.

        Note: CLI tools don't support true streaming, so we run the command
        and yield the result in chunks.
        """
        response = self.review(request)
        if response.error:
            yield f"Error: {response.error}"
        else:
            # Yield in chunks to simulate streaming
            chunk_size = 100
            content = response.content
            for i in range(0, len(content), chunk_size):
                yield content[i : i + chunk_size]
