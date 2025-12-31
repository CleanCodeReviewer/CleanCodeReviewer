"""Detection utilities for AI coding assistants."""

from __future__ import annotations

import platform
import shutil
from pathlib import Path


def is_claude_code_installed() -> bool:
    """Check if Claude Code CLI is installed globally."""
    # Check if 'claude' command exists in PATH
    if shutil.which("claude"):
        return True

    # Check if ~/.claude directory exists (Claude Code config dir)
    claude_dir = Path.home() / ".claude"
    if claude_dir.exists():
        return True

    return False


def is_gemini_cli_installed() -> bool:
    """Check if Gemini CLI is installed globally."""
    # Check if 'gemini' command exists in PATH
    if shutil.which("gemini"):
        return True

    # Check if ~/.gemini directory exists (Gemini CLI config dir)
    gemini_dir = Path.home() / ".gemini"
    if gemini_dir.exists():
        return True

    return False


def is_cursor_installed() -> bool:
    """Check if Cursor IDE is installed."""
    system = platform.system()

    if system == "Darwin":  # macOS
        if Path("/Applications/Cursor.app").exists():
            return True
    elif system == "Windows":
        # Common Windows install path
        local_app = Path.home() / "AppData/Local/Programs/cursor/Cursor.exe"
        if local_app.exists():
            return True
    elif system == "Linux":
        # Check if cursor command exists (AppImage or installed)
        if shutil.which("cursor"):
            return True

    # Also check for user-level config directory
    cursor_dir = Path.home() / ".cursor"
    if cursor_dir.exists():
        return True

    return False


def project_uses_claude(project_path: Path) -> bool:
    """Check if project uses Claude Code (has .claude directory or CLAUDE.md file)."""
    return (project_path / ".claude").exists() or (project_path / "CLAUDE.md").exists()


def project_uses_gemini(project_path: Path) -> bool:
    """Check if project uses Gemini CLI (has .gemini directory)."""
    return (project_path / ".gemini").exists()


def project_uses_cursor(project_path: Path) -> bool:
    """Check if project uses Cursor (has .cursor directory or .cursorrules file)."""
    return (project_path / ".cursor").exists() or (project_path / ".cursorrules").exists()


def get_project_targets(project_path: Path) -> list[str]:
    """Get list of AI coding assistants that should be configured for this project.

    Returns targets where both:
    1. The CLI/IDE is installed globally
    2. The project has the corresponding directory/file
    """
    targets = []
    if is_claude_code_installed() and project_uses_claude(project_path):
        targets.append("claude")
    if is_gemini_cli_installed() and project_uses_gemini(project_path):
        targets.append("gemini")
    if is_cursor_installed() and project_uses_cursor(project_path):
        targets.append("cursor")
    return targets
