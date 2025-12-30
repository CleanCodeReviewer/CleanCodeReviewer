"""LLM client for code review using LiteLLM."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Iterator

import litellm
from litellm import acompletion, completion

from clean_code_reviewer.utils.config import Settings, get_effective_settings
from clean_code_reviewer.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class ReviewResult:
    """Result from a code review."""

    content: str
    model: str
    usage: dict[str, int] = field(default_factory=dict)
    finish_reason: str | None = None
    raw_response: Any = None

    @property
    def total_tokens(self) -> int:
        """Get total tokens used."""
        return self.usage.get("total_tokens", 0)

    @property
    def prompt_tokens(self) -> int:
        """Get prompt tokens used."""
        return self.usage.get("prompt_tokens", 0)

    @property
    def completion_tokens(self) -> int:
        """Get completion tokens used."""
        return self.usage.get("completion_tokens", 0)


class LLMClient:
    """Client for interacting with LLMs via LiteLLM."""

    def __init__(
        self,
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        settings: Settings | None = None,
    ):
        """
        Initialize the LLM client.

        Args:
            model: Model to use (e.g., "gpt-4", "claude-3-opus")
            temperature: Temperature for generation
            max_tokens: Maximum tokens for response
            settings: Settings instance (uses default if None)
        """
        if settings is None:
            settings = get_effective_settings()

        self.model = model or settings.model
        self.temperature = temperature if temperature is not None else settings.temperature
        self.max_tokens = max_tokens if max_tokens is not None else settings.max_tokens
        self.ollama_host = settings.ollama_host

        # Configure LiteLLM
        self._configure_litellm()

    def _configure_litellm(self) -> None:
        """Configure LiteLLM settings."""
        import os

        # Suppress verbose logging from LiteLLM
        litellm.set_verbose = False

        # Set Ollama host for LiteLLM
        if self.ollama_host:
            os.environ["OLLAMA_API_BASE"] = self.ollama_host

    def review(
        self,
        system_prompt: str,
        user_prompt: str,
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> ReviewResult:
        """
        Perform a synchronous code review.

        Args:
            system_prompt: System prompt with instructions
            user_prompt: User prompt with code and rules
            model: Override model for this request
            temperature: Override temperature for this request
            max_tokens: Override max_tokens for this request

        Returns:
            ReviewResult with the review content
        """
        model = model or self.model
        temperature = temperature if temperature is not None else self.temperature
        max_tokens = max_tokens if max_tokens is not None else self.max_tokens

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        logger.info(f"Sending review request to {model}")

        try:
            response = completion(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )

            # Extract response content
            content = response.choices[0].message.content or ""
            usage = {
                "prompt_tokens": response.usage.prompt_tokens if response.usage else 0,
                "completion_tokens": response.usage.completion_tokens if response.usage else 0,
                "total_tokens": response.usage.total_tokens if response.usage else 0,
            }
            finish_reason = response.choices[0].finish_reason

            logger.info(f"Review completed. Tokens used: {usage.get('total_tokens', 0)}")

            return ReviewResult(
                content=content,
                model=model,
                usage=usage,
                finish_reason=finish_reason,
                raw_response=response,
            )

        except Exception as e:
            logger.error(f"Error during review: {e}")
            raise

    async def review_async(
        self,
        system_prompt: str,
        user_prompt: str,
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> ReviewResult:
        """
        Perform an asynchronous code review.

        Args:
            system_prompt: System prompt with instructions
            user_prompt: User prompt with code and rules
            model: Override model for this request
            temperature: Override temperature for this request
            max_tokens: Override max_tokens for this request

        Returns:
            ReviewResult with the review content
        """
        model = model or self.model
        temperature = temperature if temperature is not None else self.temperature
        max_tokens = max_tokens if max_tokens is not None else self.max_tokens

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        logger.info(f"Sending async review request to {model}")

        try:
            response = await acompletion(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )

            content = response.choices[0].message.content or ""
            usage = {
                "prompt_tokens": response.usage.prompt_tokens if response.usage else 0,
                "completion_tokens": response.usage.completion_tokens if response.usage else 0,
                "total_tokens": response.usage.total_tokens if response.usage else 0,
            }
            finish_reason = response.choices[0].finish_reason

            logger.info(f"Async review completed. Tokens used: {usage.get('total_tokens', 0)}")

            return ReviewResult(
                content=content,
                model=model,
                usage=usage,
                finish_reason=finish_reason,
                raw_response=response,
            )

        except Exception as e:
            logger.error(f"Error during async review: {e}")
            raise

    def review_stream(
        self,
        system_prompt: str,
        user_prompt: str,
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> Iterator[str]:
        """
        Perform a streaming code review.

        Args:
            system_prompt: System prompt with instructions
            user_prompt: User prompt with code and rules
            model: Override model for this request
            temperature: Override temperature for this request
            max_tokens: Override max_tokens for this request

        Yields:
            Chunks of the review content
        """
        model = model or self.model
        temperature = temperature if temperature is not None else self.temperature
        max_tokens = max_tokens if max_tokens is not None else self.max_tokens

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        logger.info(f"Starting streaming review with {model}")

        try:
            response = completion(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                stream=True,
            )

            for chunk in response:
                if chunk.choices and chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content

        except Exception as e:
            logger.error(f"Error during streaming review: {e}")
            raise

    async def review_stream_async(
        self,
        system_prompt: str,
        user_prompt: str,
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> AsyncIterator[str]:
        """
        Perform an async streaming code review.

        Args:
            system_prompt: System prompt with instructions
            user_prompt: User prompt with code and rules
            model: Override model for this request
            temperature: Override temperature for this request
            max_tokens: Override max_tokens for this request

        Yields:
            Chunks of the review content
        """
        model = model or self.model
        temperature = temperature if temperature is not None else self.temperature
        max_tokens = max_tokens if max_tokens is not None else self.max_tokens

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        logger.info(f"Starting async streaming review with {model}")

        try:
            response = await acompletion(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                stream=True,
            )

            async for chunk in response:
                if chunk.choices and chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content

        except Exception as e:
            logger.error(f"Error during async streaming review: {e}")
            raise

    def validate_connection(self) -> bool:
        """
        Validate that the LLM connection is working.

        Returns:
            True if connection is valid, False otherwise
        """
        try:
            response = completion(
                model=self.model,
                messages=[{"role": "user", "content": "Hello"}],
                max_tokens=5,
            )
            return bool(response.choices)
        except Exception as e:
            logger.warning(f"Connection validation failed: {e}")
            return False

    @staticmethod
    def list_available_models() -> list[str]:
        """
        List commonly available models.

        Returns:
            List of model names
        """
        return [
            # OpenAI
            "gpt-4",
            "gpt-4-turbo",
            "gpt-4o",
            "gpt-4o-mini",
            "gpt-3.5-turbo",
            # Anthropic
            "claude-3-opus-20240229",
            "claude-3-sonnet-20240229",
            "claude-3-haiku-20240307",
            "claude-3-5-sonnet-20240620",
            # Ollama (local)
            "ollama/llama2",
            "ollama/codellama",
            "ollama/mistral",
            "ollama/mixtral",
        ]
