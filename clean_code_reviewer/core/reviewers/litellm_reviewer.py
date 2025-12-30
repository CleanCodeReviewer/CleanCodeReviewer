"""LiteLLM-based reviewer implementation."""

from __future__ import annotations

import os
from typing import Iterator

from clean_code_reviewer.core.llm_client import LLMClient
from clean_code_reviewer.core.reviewers.base import ReviewRequest, ReviewResponse, Reviewer
from clean_code_reviewer.utils.config import Settings, get_effective_settings


class LiteLLMReviewer(Reviewer):
    """Reviewer using LiteLLM API."""

    def __init__(
        self,
        model: str | None = None,
        settings: Settings | None = None,
    ):
        """
        Initialize the LiteLLM reviewer.

        Args:
            model: Model to use (e.g., "gpt-4", "claude-3-opus")
            settings: Settings instance
        """
        self._settings = settings or get_effective_settings()
        self._client = LLMClient(model=model, settings=self._settings)

    @property
    def name(self) -> str:
        """Return the reviewer name."""
        return "litellm"

    def review(self, request: ReviewRequest) -> ReviewResponse:
        """Perform a synchronous review."""
        try:
            result = self._client.review(request.system_prompt, request.user_prompt)
            return ReviewResponse(
                content=result.content,
                reviewer=self.name,
                model=result.model,
                usage=result.usage,
            )
        except Exception as e:
            return ReviewResponse(
                content="",
                reviewer=self.name,
                error=str(e),
            )

    def review_stream(self, request: ReviewRequest) -> Iterator[str]:
        """Perform a streaming review."""
        yield from self._client.review_stream(request.system_prompt, request.user_prompt)

    def is_available(self) -> bool:
        """Check if LiteLLM is available (API keys configured)."""
        # Check for any API key
        has_openai = bool(
            self._settings.openai_api_key or os.getenv("OPENAI_API_KEY")
        )
        has_anthropic = bool(
            self._settings.anthropic_api_key or os.getenv("ANTHROPIC_API_KEY")
        )
        has_ollama = bool(self._settings.ollama_host)

        return has_openai or has_anthropic or has_ollama
