"""Safe file operations for Clean Code Reviewer."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Generator

from clean_code_reviewer.utils.logger import get_logger

logger = get_logger(__name__)


def read_file_safe(path: Path | str, encoding: str = "utf-8") -> str | None:
    """
    Safely read a file's contents.

    Args:
        path: Path to the file
        encoding: File encoding (default: utf-8)

    Returns:
        File contents as string, or None if file cannot be read
    """
    path = Path(path)

    if not path.exists():
        logger.warning(f"File not found: {path}")
        return None

    if not path.is_file():
        logger.warning(f"Path is not a file: {path}")
        return None

    try:
        return path.read_text(encoding=encoding)
    except PermissionError:
        logger.error(f"Permission denied reading file: {path}")
        return None
    except UnicodeDecodeError:
        logger.error(f"Unicode decode error reading file: {path}")
        return None
    except OSError as e:
        logger.error(f"OS error reading file {path}: {e}")
        return None


def write_file_safe(
    path: Path | str,
    content: str,
    encoding: str = "utf-8",
    create_dirs: bool = True,
) -> bool:
    """
    Safely write content to a file.

    Args:
        path: Path to the file
        content: Content to write
        encoding: File encoding (default: utf-8)
        create_dirs: Create parent directories if they don't exist

    Returns:
        True if write was successful, False otherwise
    """
    path = Path(path)

    try:
        if create_dirs:
            path.parent.mkdir(parents=True, exist_ok=True)

        path.write_text(content, encoding=encoding)
        logger.debug(f"Successfully wrote file: {path}")
        return True
    except PermissionError:
        logger.error(f"Permission denied writing file: {path}")
        return False
    except OSError as e:
        logger.error(f"OS error writing file {path}: {e}")
        return False


def ensure_directory(path: Path | str) -> bool:
    """
    Ensure a directory exists, creating it if necessary.

    Args:
        path: Path to the directory

    Returns:
        True if directory exists or was created, False on error
    """
    path = Path(path)

    try:
        path.mkdir(parents=True, exist_ok=True)
        return True
    except PermissionError:
        logger.error(f"Permission denied creating directory: {path}")
        return False
    except OSError as e:
        logger.error(f"OS error creating directory {path}: {e}")
        return False


def find_files(
    directory: Path | str,
    patterns: list[str] | None = None,
    recursive: bool = True,
) -> Generator[Path, None, None]:
    """
    Find files matching given patterns in a directory.

    Args:
        directory: Directory to search in
        patterns: List of glob patterns (e.g., ["*.py", "*.js"])
        recursive: Search recursively in subdirectories

    Yields:
        Paths to matching files
    """
    directory = Path(directory)

    if not directory.exists():
        logger.warning(f"Directory not found: {directory}")
        return

    if not directory.is_dir():
        logger.warning(f"Path is not a directory: {directory}")
        return

    if patterns is None:
        patterns = ["*"]

    for pattern in patterns:
        if recursive:
            glob_pattern = f"**/{pattern}"
        else:
            glob_pattern = pattern

        try:
            for file_path in directory.glob(glob_pattern):
                if file_path.is_file():
                    yield file_path
        except OSError as e:
            logger.error(f"Error searching directory {directory}: {e}")


def get_relative_path(path: Path | str, base: Path | str | None = None) -> str:
    """
    Get a relative path from a base directory.

    Args:
        path: The path to make relative
        base: Base directory (defaults to cwd)

    Returns:
        Relative path as string
    """
    path = Path(path)
    base = Path(base) if base else Path.cwd()

    try:
        return str(path.relative_to(base))
    except ValueError:
        return str(path)


def is_text_file(path: Path | str, sample_size: int = 8192) -> bool:
    """
    Check if a file appears to be a text file.

    Args:
        path: Path to the file
        sample_size: Number of bytes to sample

    Returns:
        True if file appears to be text, False otherwise
    """
    path = Path(path)

    if not path.exists() or not path.is_file():
        return False

    # Common text file extensions
    text_extensions = {
        ".py", ".js", ".ts", ".jsx", ".tsx", ".java", ".c", ".cpp", ".h",
        ".hpp", ".cs", ".go", ".rs", ".rb", ".php", ".swift", ".kt", ".scala",
        ".md", ".txt", ".json", ".yaml", ".yml", ".xml", ".html", ".css",
        ".scss", ".sass", ".less", ".sql", ".sh", ".bash", ".zsh", ".fish",
        ".toml", ".ini", ".cfg", ".conf", ".env", ".gitignore", ".dockerignore",
    }

    if path.suffix.lower() in text_extensions:
        return True

    # Sample the file for binary content
    try:
        with open(path, "rb") as f:
            sample = f.read(sample_size)

        # Check for null bytes (common in binary files)
        if b"\x00" in sample:
            return False

        # Try to decode as UTF-8
        try:
            sample.decode("utf-8")
            return True
        except UnicodeDecodeError:
            return False

    except OSError:
        return False


def get_file_extension(path: Path | str) -> str:
    """Get the file extension without the leading dot."""
    return Path(path).suffix.lstrip(".")


def get_language_from_extension(extension: str) -> str | None:
    """
    Map file extension to programming language.

    Args:
        extension: File extension (without dot)

    Returns:
        Language name or None if unknown
    """
    extension_map = {
        "py": "python",
        "js": "javascript",
        "ts": "typescript",
        "jsx": "javascript",
        "tsx": "typescript",
        "java": "java",
        "c": "c",
        "cpp": "cpp",
        "cc": "cpp",
        "cxx": "cpp",
        "h": "c",
        "hpp": "cpp",
        "cs": "csharp",
        "go": "go",
        "rs": "rust",
        "rb": "ruby",
        "php": "php",
        "swift": "swift",
        "kt": "kotlin",
        "kts": "kotlin",
        "scala": "scala",
        "md": "markdown",
        "json": "json",
        "yaml": "yaml",
        "yml": "yaml",
        "xml": "xml",
        "html": "html",
        "htm": "html",
        "css": "css",
        "scss": "scss",
        "sass": "sass",
        "less": "less",
        "sql": "sql",
        "sh": "bash",
        "bash": "bash",
        "zsh": "zsh",
        "fish": "fish",
    }

    return extension_map.get(extension.lower())
