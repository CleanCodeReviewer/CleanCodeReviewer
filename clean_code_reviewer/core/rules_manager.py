"""Manager for downloading rules from the remote rules repository."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx

from clean_code_reviewer.utils.config import get_settings
from clean_code_reviewer.utils.file_ops import ensure_directory, write_file_safe
from clean_code_reviewer.utils.logger import get_logger

logger = get_logger(__name__)

# GitHub API base URL
GITHUB_API_URL = "https://api.github.com"
GITHUB_RAW_URL = "https://raw.githubusercontent.com"


@dataclass
class RemoteRule:
    """Represents a rule available in the remote repository."""

    namespace: str
    name: str
    description: str | None = None
    path: str | None = None


class RulesManager:
    """Manager for downloading and listing rules from remote repository."""

    def __init__(
        self,
        repo_owner: str | None = None,
        repo_name: str | None = None,
        timeout: float = 30.0,
    ):
        """
        Initialize the rules manager.

        Args:
            repo_owner: GitHub repository owner (default: CleanCodeReviewer)
            repo_name: GitHub repository name (default: Rules)
            timeout: Request timeout in seconds
        """
        settings = get_settings()
        self.repo_owner = repo_owner or settings.rules_repo_owner
        self.repo_name = repo_name or settings.rules_repo_name
        self.timeout = timeout
        self._client: httpx.Client | None = None

    @property
    def client(self) -> httpx.Client:
        """Get or create HTTP client."""
        if self._client is None:
            self._client = httpx.Client(timeout=self.timeout)
        return self._client

    def close(self) -> None:
        """Close the HTTP client."""
        if self._client is not None:
            self._client.close()
            self._client = None

    def __enter__(self) -> "RulesManager":
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()

    def _get_raw_url(self, path: str) -> str:
        """Build raw GitHub URL for a file."""
        return f"{GITHUB_RAW_URL}/{self.repo_owner}/{self.repo_name}/main/{path}"

    def _get_api_url(self, path: str = "") -> str:
        """Build GitHub API URL for contents."""
        base = f"{GITHUB_API_URL}/repos/{self.repo_owner}/{self.repo_name}/contents"
        if path:
            return f"{base}/{path}"
        return base

    def fetch_rule(self, rule_path: str) -> str | None:
        """
        Fetch a rule from the remote repository.

        Args:
            rule_path: Path to the rule (e.g., "google/python" or "base")

        Returns:
            Rule content as string, or None if not found
        """
        # Add .yml extension if not present
        if not rule_path.endswith(".yml"):
            rule_path = f"{rule_path}.yml"

        # Rules are stored under src/ in the repository
        url = self._get_raw_url(f"src/{rule_path}")
        logger.info(f"Fetching rule from: {url}")

        try:
            response = self.client.get(url)
            response.raise_for_status()
            return response.text
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                logger.warning(f"Rule not found: {rule_path}")
            else:
                logger.error(f"HTTP error fetching rule {rule_path}: {e}")
            return None
        except httpx.RequestError as e:
            logger.error(f"Request error fetching rule {rule_path}: {e}")
            return None

    def download_rule(
        self,
        rule_path: str,
        target_dir: Path | str | None = None,
    ) -> Path | None:
        """
        Download a rule and save it to the local rules directory.

        Args:
            rule_path: Path to the rule (e.g., "google/python" or "base")
            target_dir: Target directory (defaults to .cleancoderules)

        Returns:
            Path to the saved rule file, or None if download failed
        """
        if target_dir is None:
            target_dir = Path.cwd() / ".cleancoderules"
        target_dir = Path(target_dir)

        # Fetch the rule
        content = self.fetch_rule(rule_path)
        if content is None:
            return None

        # Determine the save path
        # "base" -> ".cleancoderules/base.yml"
        # "google/python" -> ".cleancoderules/community/google/python.yml"
        if not rule_path.endswith(".yml"):
            rule_path = f"{rule_path}.yml"

        # Namespace rules go under community/
        if "/" in rule_path:
            save_path = target_dir / "community" / rule_path
        else:
            save_path = target_dir / rule_path

        # Ensure directory exists
        ensure_directory(save_path.parent)

        # Save the file
        if write_file_safe(save_path, content):
            logger.info(f"Downloaded rule to: {save_path}")
            return save_path
        else:
            logger.error(f"Failed to save rule to: {save_path}")
            return None

    def list_available_rules(self) -> list[RemoteRule]:
        """
        List all available rules in the remote repository using GitHub API.

        Returns:
            List of available rules
        """
        rules: list[RemoteRule] = []

        try:
            # Fetch src/ directory contents (rules are stored under src/)
            src_contents = self._fetch_contents("src")
            if src_contents is None:
                return []

            for item in src_contents:
                if item["type"] == "file" and item["name"].endswith(".yml"):
                    # Root-level rule (e.g., base.yml)
                    name = item["name"].removesuffix(".yml")
                    rules.append(
                        RemoteRule(
                            namespace="",
                            name=name,
                            path=item["path"],
                        )
                    )
                elif item["type"] == "dir":
                    # Namespace directory (e.g., google/, airbnb/)
                    namespace = item["name"]
                    dir_contents = self._fetch_contents(f"src/{namespace}")
                    if dir_contents:
                        for sub_item in dir_contents:
                            if sub_item["type"] == "file" and sub_item["name"].endswith(".yml"):
                                name = sub_item["name"].removesuffix(".yml")
                                rules.append(
                                    RemoteRule(
                                        namespace=namespace,
                                        name=name,
                                        path=sub_item["path"],
                                    )
                                )

            return rules

        except Exception as e:
            logger.error(f"Error listing rules: {e}")
            return []

    def _fetch_contents(self, path: str) -> list[dict[str, Any]] | None:
        """Fetch directory contents from GitHub API."""
        url = self._get_api_url(path)

        try:
            response = self.client.get(url)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                logger.warning(f"Path not found: {path}")
            else:
                logger.error(f"HTTP error fetching contents {path}: {e}")
            return None
        except httpx.RequestError as e:
            logger.error(f"Request error fetching contents {path}: {e}")
            return None

    def check_rule_exists(self, rule_path: str) -> bool:
        """
        Check if a rule exists in the remote repository.

        Args:
            rule_path: Path to the rule

        Returns:
            True if rule exists, False otherwise
        """
        if not rule_path.endswith(".yml"):
            rule_path = f"{rule_path}.yml"

        # Rules are stored under src/ in the repository
        url = self._get_raw_url(f"src/{rule_path}")

        try:
            response = self.client.head(url)
            return response.status_code == 200
        except httpx.RequestError:
            return False
