"""Configuration management for Clean Code Reviewer."""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings with environment variable support."""

    model_config = SettingsConfigDict(
        env_prefix="CCR_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # LLM Configuration
    model: str = Field(default="gpt-4", description="Default LLM model to use")
    temperature: float = Field(default=0.3, ge=0.0, le=2.0, description="LLM temperature")
    max_tokens: int = Field(default=2000, gt=0, description="Maximum tokens for LLM response")

    # API Keys (read from environment)
    openai_api_key: str | None = Field(default=None, description="OpenAI API key")
    anthropic_api_key: str | None = Field(default=None, description="Anthropic API key")
    ollama_host: str = Field(default="http://localhost:11434", description="Ollama host URL")

    # Paths
    rules_dir: str = Field(default=".cleancoderules", description="Directory for rules")
    config_file: str = Field(default="config.yaml", description="Config file name in rules dir")

    # Remote rules repository (GitHub)
    rules_repo_owner: str = Field(
        default="CleanCodeReviewer",
        description="GitHub owner/org for rules repository",
    )
    rules_repo_name: str = Field(
        default="Rules",
        description="GitHub repository name for rules",
    )

    # Review settings
    rules_priority: list[str] = Field(
        default_factory=lambda: ["security", "style", "performance"],
        description="Priority order for rule categories",
    )

    # Reviewer configuration
    default_reviewer: str | None = Field(
        default=None,
        description="Default reviewer backend (litellm, claudecode, gemini, codex)",
    )

    def get_rules_path(self, base_path: Path | None = None) -> Path:
        """Get the full path to the rules directory."""
        if base_path is None:
            base_path = Path.cwd()
        return base_path / self.rules_dir

    def get_config_path(self, base_path: Path | None = None) -> Path:
        """Get the full path to the config file."""
        return self.get_rules_path(base_path) / self.config_file


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


def load_project_config(project_path: Path | None = None) -> dict[str, Any]:
    """Load project-specific configuration from .cleancoderules/config.yaml."""
    if project_path is None:
        project_path = Path.cwd()

    config_path = project_path / ".cleancoderules" / "config.yaml"

    if not config_path.exists():
        return {}

    with open(config_path, encoding="utf-8") as f:
        config = yaml.safe_load(f) or {}

    return config


def merge_settings(base: Settings, project_config: dict[str, Any]) -> Settings:
    """Merge project config into base settings."""
    if not project_config:
        return base

    # Create a new settings instance with merged values
    merged_data = base.model_dump()
    for key, value in project_config.items():
        if key in merged_data and value is not None:
            merged_data[key] = value

    return Settings(**merged_data)


def get_effective_settings(project_path: Path | None = None) -> Settings:
    """Get settings with project-specific overrides applied."""
    base = get_settings()
    project_config = load_project_config(project_path)
    return merge_settings(base, project_config)


def get_api_key_for_model(model: str, settings: Settings | None = None) -> str | None:
    """Get the appropriate API key for a given model."""
    if settings is None:
        settings = get_settings()

    model_lower = model.lower()

    # Check environment variables first (LiteLLM convention)
    if "gpt" in model_lower or "openai" in model_lower:
        return settings.openai_api_key or os.getenv("OPENAI_API_KEY")
    elif "claude" in model_lower or "anthropic" in model_lower:
        return settings.anthropic_api_key or os.getenv("ANTHROPIC_API_KEY")
    elif "ollama" in model_lower:
        return None  # Ollama doesn't need an API key
    else:
        # Default to OpenAI
        return settings.openai_api_key or os.getenv("OPENAI_API_KEY")
