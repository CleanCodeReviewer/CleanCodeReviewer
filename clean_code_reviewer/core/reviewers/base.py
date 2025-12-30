"""Base classes for code reviewers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Iterator


@dataclass
class ReviewRequest:
    """Encapsulates a review request."""

    system_prompt: str
    user_prompt: str
    file_path: str | None = None
    language: str | None = None


@dataclass
class ReviewResponse:
    """Encapsulates a review response."""

    content: str
    reviewer: str
    model: str | None = None
    usage: dict[str, int] = field(default_factory=dict)
    error: str | None = None


class Reviewer(ABC):
    """Abstract base class for code reviewers."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Return the reviewer name."""
        ...

    @abstractmethod
    def review(self, request: ReviewRequest) -> ReviewResponse:
        """Perform a synchronous review."""
        ...

    @abstractmethod
    def review_stream(self, request: ReviewRequest) -> Iterator[str]:
        """Perform a streaming review. Yields chunks of text."""
        ...

    @abstractmethod
    def is_available(self) -> bool:
        """Check if this reviewer is available/configured."""
        ...
