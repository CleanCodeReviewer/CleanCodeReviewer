"""File selection utilities for code review."""

from __future__ import annotations

import subprocess
from pathlib import Path

from clean_code_reviewer.utils.logger import get_logger

logger = get_logger(__name__)

# Common code file extensions
CODE_EXTENSIONS = {
    ".py",
    ".js",
    ".ts",
    ".tsx",
    ".jsx",
    ".java",
    ".go",
    ".rs",
    ".c",
    ".cpp",
    ".h",
    ".hpp",
    ".cs",
    ".rb",
    ".php",
    ".swift",
    ".kt",
    ".scala",
    ".vue",
    ".svelte",
}


def get_changed_files(
    base_ref: str = "HEAD",
    compare_ref: str | None = None,
    staged_only: bool = False,
    base_path: Path | None = None,
) -> list[Path]:
    """
    Get files changed in git.

    Args:
        base_ref: Base git reference (default: HEAD)
        compare_ref: Compare reference (for comparing branches)
        staged_only: Only get staged files
        base_path: Base path for relative file paths

    Returns:
        List of changed file paths
    """
    base = base_path or Path.cwd()

    try:
        if staged_only:
            cmd = ["git", "diff", "--cached", "--name-only"]
        elif compare_ref:
            cmd = ["git", "diff", "--name-only", base_ref, compare_ref]
        else:
            # Get both staged and unstaged changes
            cmd = ["git", "diff", "--name-only", base_ref]

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=base,
        )

        if result.returncode != 0:
            logger.warning(f"Git diff failed: {result.stderr}")
            return []

        files = []
        for line in result.stdout.strip().split("\n"):
            if line:
                file_path = base / line
                if file_path.exists():
                    files.append(file_path)

        return files

    except Exception as e:
        logger.error(f"Error getting changed files: {e}")
        return []


def get_uncommitted_files(base_path: Path | None = None) -> list[Path]:
    """
    Get all uncommitted files (staged + unstaged + untracked).

    Args:
        base_path: Base path for relative file paths

    Returns:
        List of uncommitted file paths
    """
    base = base_path or Path.cwd()
    files: set[Path] = set()

    try:
        # Get staged files
        staged = subprocess.run(
            ["git", "diff", "--cached", "--name-only"],
            capture_output=True,
            text=True,
            cwd=base,
        )
        if staged.returncode == 0:
            for line in staged.stdout.strip().split("\n"):
                if line:
                    files.add(base / line)

        # Get unstaged files
        unstaged = subprocess.run(
            ["git", "diff", "--name-only"],
            capture_output=True,
            text=True,
            cwd=base,
        )
        if unstaged.returncode == 0:
            for line in unstaged.stdout.strip().split("\n"):
                if line:
                    files.add(base / line)

        return [f for f in files if f.exists()]

    except Exception as e:
        logger.error(f"Error getting uncommitted files: {e}")
        return []


def is_code_file(path: Path) -> bool:
    """
    Check if path is a code file based on extension.

    Args:
        path: File path to check

    Returns:
        True if it's a code file
    """
    return path.suffix.lower() in CODE_EXTENSIONS


class FileSelector:
    """Flexible file selection with multiple strategies."""

    def __init__(self, base_path: Path | None = None):
        """
        Initialize the file selector.

        Args:
            base_path: Base path for file operations
        """
        self.base_path = base_path or Path.cwd()

    def select(
        self,
        files: list[Path] | None = None,
        patterns: list[str] | None = None,
        changed: bool = False,
        staged: bool = False,
        base_ref: str = "HEAD",
        compare_ref: str | None = None,
    ) -> list[Path]:
        """
        Select files using various strategies.

        Args:
            files: Explicit files or directories
            patterns: Glob patterns (e.g., "**/*.py")
            changed: Include git changed files
            staged: Include only git staged files
            base_ref: Git base reference for comparison
            compare_ref: Git compare reference

        Returns:
            List of selected file paths
        """
        result: set[Path] = set()

        # Explicit files and directories
        if files:
            for f in files:
                path = self.base_path / f if not f.is_absolute() else f
                if path.exists():
                    if path.is_file():
                        result.add(path)
                    elif path.is_dir():
                        result.update(self._expand_directory(path))
                else:
                    logger.warning(f"Path not found: {path}")

        # Glob patterns
        if patterns:
            for pattern in patterns:
                matched = list(self.base_path.glob(pattern))
                result.update(f for f in matched if f.is_file())

        # Git changed files
        if changed:
            changed_files = get_changed_files(
                base_ref=base_ref,
                compare_ref=compare_ref,
                base_path=self.base_path,
            )
            result.update(changed_files)

        # Git staged files only
        if staged:
            staged_files = get_changed_files(
                staged_only=True,
                base_path=self.base_path,
            )
            result.update(staged_files)

        # Filter to only code files
        return sorted([f for f in result if is_code_file(f)])

    def _expand_directory(self, path: Path) -> list[Path]:
        """
        Expand directory to code files recursively.

        Args:
            path: Directory path

        Returns:
            List of code files in the directory
        """
        files = []
        for ext in CODE_EXTENSIONS:
            files.extend(path.rglob(f"*{ext}"))
        return files
