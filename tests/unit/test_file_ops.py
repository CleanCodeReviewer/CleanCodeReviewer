"""Unit tests for file operations."""

from __future__ import annotations

from pathlib import Path

import pytest

from clean_code_reviewer.utils.file_ops import (
    ensure_directory,
    find_files,
    get_file_extension,
    get_language_from_extension,
    get_relative_path,
    is_text_file,
    read_file_safe,
    write_file_safe,
)


class TestReadFileSafe:
    """Tests for read_file_safe function."""

    def test_read_existing_file(self, tmp_path: Path) -> None:
        """Test reading an existing file."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("Hello, World!")

        content = read_file_safe(test_file)
        assert content == "Hello, World!"

    def test_read_nonexistent_file(self, tmp_path: Path) -> None:
        """Test reading a non-existent file."""
        content = read_file_safe(tmp_path / "nonexistent.txt")
        assert content is None

    def test_read_directory(self, tmp_path: Path) -> None:
        """Test reading a directory returns None."""
        content = read_file_safe(tmp_path)
        assert content is None


class TestWriteFileSafe:
    """Tests for write_file_safe function."""

    def test_write_to_new_file(self, tmp_path: Path) -> None:
        """Test writing to a new file."""
        test_file = tmp_path / "new.txt"
        result = write_file_safe(test_file, "Test content")

        assert result is True
        assert test_file.read_text() == "Test content"

    def test_write_creates_directories(self, tmp_path: Path) -> None:
        """Test that write creates parent directories."""
        test_file = tmp_path / "subdir" / "nested" / "file.txt"
        result = write_file_safe(test_file, "Nested content")

        assert result is True
        assert test_file.exists()

    def test_write_overwrite_existing(self, tmp_path: Path) -> None:
        """Test overwriting an existing file."""
        test_file = tmp_path / "existing.txt"
        test_file.write_text("Original")

        result = write_file_safe(test_file, "Updated")

        assert result is True
        assert test_file.read_text() == "Updated"


class TestEnsureDirectory:
    """Tests for ensure_directory function."""

    def test_create_new_directory(self, tmp_path: Path) -> None:
        """Test creating a new directory."""
        new_dir = tmp_path / "newdir"
        result = ensure_directory(new_dir)

        assert result is True
        assert new_dir.is_dir()

    def test_create_nested_directories(self, tmp_path: Path) -> None:
        """Test creating nested directories."""
        nested_dir = tmp_path / "a" / "b" / "c"
        result = ensure_directory(nested_dir)

        assert result is True
        assert nested_dir.is_dir()

    def test_existing_directory(self, tmp_path: Path) -> None:
        """Test with an existing directory."""
        result = ensure_directory(tmp_path)
        assert result is True


class TestFindFiles:
    """Tests for find_files function."""

    def test_find_files_with_pattern(self, tmp_path: Path) -> None:
        """Test finding files with a pattern."""
        (tmp_path / "file1.py").write_text("")
        (tmp_path / "file2.py").write_text("")
        (tmp_path / "file3.txt").write_text("")

        py_files = list(find_files(tmp_path, patterns=["*.py"]))

        assert len(py_files) == 2
        assert all(f.suffix == ".py" for f in py_files)

    def test_find_files_recursive(self, tmp_path: Path) -> None:
        """Test recursive file finding."""
        subdir = tmp_path / "subdir"
        subdir.mkdir()

        (tmp_path / "root.py").write_text("")
        (subdir / "nested.py").write_text("")

        all_files = list(find_files(tmp_path, patterns=["*.py"], recursive=True))
        assert len(all_files) == 2

    def test_find_files_non_recursive(self, tmp_path: Path) -> None:
        """Test non-recursive file finding."""
        subdir = tmp_path / "subdir"
        subdir.mkdir()

        (tmp_path / "root.py").write_text("")
        (subdir / "nested.py").write_text("")

        root_files = list(find_files(tmp_path, patterns=["*.py"], recursive=False))
        assert len(root_files) == 1

    def test_find_files_multiple_patterns(self, tmp_path: Path) -> None:
        """Test finding files with multiple patterns."""
        (tmp_path / "file.py").write_text("")
        (tmp_path / "file.js").write_text("")
        (tmp_path / "file.txt").write_text("")

        files = list(find_files(tmp_path, patterns=["*.py", "*.js"]))
        assert len(files) == 2

    def test_find_files_nonexistent_dir(self, tmp_path: Path) -> None:
        """Test finding files in non-existent directory."""
        files = list(find_files(tmp_path / "nonexistent"))
        assert len(files) == 0


class TestGetRelativePath:
    """Tests for get_relative_path function."""

    def test_relative_path(self, tmp_path: Path) -> None:
        """Test getting relative path."""
        file_path = tmp_path / "subdir" / "file.txt"
        relative = get_relative_path(file_path, tmp_path)

        assert relative == "subdir/file.txt" or relative == "subdir\\file.txt"

    def test_relative_path_not_under_base(self, tmp_path: Path) -> None:
        """Test with path not under base."""
        file_path = Path("/some/other/path/file.txt")
        relative = get_relative_path(file_path, tmp_path)

        # Should return the absolute path
        assert "file.txt" in relative


class TestIsTextFile:
    """Tests for is_text_file function."""

    def test_text_file(self, tmp_path: Path) -> None:
        """Test detecting a text file."""
        text_file = tmp_path / "test.py"
        text_file.write_text("print('hello')")

        assert is_text_file(text_file) is True

    def test_binary_file(self, tmp_path: Path) -> None:
        """Test detecting a binary file."""
        binary_file = tmp_path / "test.bin"
        binary_file.write_bytes(b"\x00\x01\x02\x03")

        assert is_text_file(binary_file) is False

    def test_nonexistent_file(self, tmp_path: Path) -> None:
        """Test with non-existent file."""
        assert is_text_file(tmp_path / "nonexistent") is False

    def test_file_with_text_extension(self, tmp_path: Path) -> None:
        """Test file with known text extension."""
        js_file = tmp_path / "script.js"
        js_file.write_text("console.log('hi');")

        assert is_text_file(js_file) is True


class TestGetFileExtension:
    """Tests for get_file_extension function."""

    def test_simple_extension(self) -> None:
        """Test getting simple extension."""
        assert get_file_extension("file.py") == "py"
        assert get_file_extension("file.js") == "js"

    def test_no_extension(self) -> None:
        """Test file without extension."""
        assert get_file_extension("Makefile") == ""

    def test_double_extension(self) -> None:
        """Test file with double extension."""
        assert get_file_extension("file.test.py") == "py"


class TestGetLanguageFromExtension:
    """Tests for get_language_from_extension function."""

    def test_python(self) -> None:
        """Test Python extension."""
        assert get_language_from_extension("py") == "python"

    def test_javascript(self) -> None:
        """Test JavaScript extensions."""
        assert get_language_from_extension("js") == "javascript"
        assert get_language_from_extension("jsx") == "javascript"

    def test_typescript(self) -> None:
        """Test TypeScript extensions."""
        assert get_language_from_extension("ts") == "typescript"
        assert get_language_from_extension("tsx") == "typescript"

    def test_unknown(self) -> None:
        """Test unknown extension."""
        assert get_language_from_extension("xyz") is None

    def test_case_insensitive(self) -> None:
        """Test case insensitivity."""
        assert get_language_from_extension("PY") == "python"
        assert get_language_from_extension("Js") == "javascript"
