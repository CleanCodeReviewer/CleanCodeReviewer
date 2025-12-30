"""Unit tests for the prompt builder."""

from __future__ import annotations

from pathlib import Path

import pytest

from clean_code_reviewer.core.prompt_builder import CodeContext, PromptBuilder
from clean_code_reviewer.core.rules_engine import RulesEngine


class TestCodeContext:
    """Tests for the CodeContext class."""

    def test_code_context_creation(self) -> None:
        """Test basic CodeContext creation."""
        context = CodeContext(
            content="def hello(): pass",
            file_path="test.py",
            language="python",
        )

        assert context.content == "def hello(): pass"
        assert context.file_path == "test.py"
        assert context.language == "python"

    def test_code_context_from_file(self, tmp_path: Path) -> None:
        """Test creating CodeContext from a file."""
        test_file = tmp_path / "example.py"
        test_file.write_text("print('hello')")

        context = CodeContext.from_file(test_file)

        assert context is not None
        assert context.content == "print('hello')"
        assert context.language == "python"

    def test_code_context_from_nonexistent_file(self, tmp_path: Path) -> None:
        """Test CodeContext from non-existent file returns None."""
        context = CodeContext.from_file(tmp_path / "nonexistent.py")
        assert context is None


class TestPromptBuilder:
    """Tests for the PromptBuilder class."""

    def test_prompt_builder_creation(self, rules_dir_with_rules: Path) -> None:
        """Test PromptBuilder creation."""
        engine = RulesEngine(rules_dir_with_rules)
        builder = PromptBuilder(engine)

        assert builder.rules_engine == engine
        assert builder.system_prompt is not None

    def test_build_review_prompt(
        self, rules_dir_with_rules: Path, sample_python_code: str
    ) -> None:
        """Test building a review prompt."""
        engine = RulesEngine(rules_dir_with_rules)
        builder = PromptBuilder(engine)

        system_prompt, user_prompt = builder.build_review_prompt(
            code=sample_python_code,
            file_path="example.py",
            language="python",
        )

        # Check system prompt
        assert "code reviewer" in system_prompt.lower()

        # Check user prompt
        assert sample_python_code in user_prompt
        assert "example.py" in user_prompt
        assert "python" in user_prompt.lower()

    def test_build_review_prompt_with_context(
        self, rules_dir_with_rules: Path, sample_python_code: str
    ) -> None:
        """Test building a review prompt with CodeContext."""
        engine = RulesEngine(rules_dir_with_rules)
        builder = PromptBuilder(engine)

        context = CodeContext(
            content=sample_python_code,
            file_path="test.py",
            language="python",
        )

        system_prompt, user_prompt = builder.build_review_prompt(code=context)

        assert sample_python_code in user_prompt
        assert "test.py" in user_prompt

    def test_build_review_prompt_with_tags(
        self, rules_dir_with_rules: Path, sample_python_code: str
    ) -> None:
        """Test building a review prompt with tag filters."""
        engine = RulesEngine(rules_dir_with_rules)
        builder = PromptBuilder(engine)

        system_prompt, user_prompt = builder.build_review_prompt(
            code=sample_python_code,
            tags=["security"],
        )

        # Should include security rules
        assert len(user_prompt) > 0

    def test_build_multi_file_prompt(
        self, rules_dir_with_rules: Path
    ) -> None:
        """Test building a prompt for multiple files."""
        engine = RulesEngine(rules_dir_with_rules)
        builder = PromptBuilder(engine)

        files = [
            ("file1.py", "def func1(): pass"),
            ("file2.js", "function func2() {}"),
        ]

        system_prompt, user_prompt = builder.build_multi_file_prompt(files)

        assert "file1.py" in user_prompt
        assert "file2.js" in user_prompt
        assert "func1" in user_prompt
        assert "func2" in user_prompt

    def test_build_focused_prompt(
        self, rules_dir_with_rules: Path, sample_python_code: str
    ) -> None:
        """Test building a focused review prompt."""
        engine = RulesEngine(rules_dir_with_rules)
        builder = PromptBuilder(engine)

        system_prompt, user_prompt = builder.build_focused_prompt(
            code=sample_python_code,
            focus_areas=["security"],
        )

        assert len(user_prompt) > 0

    def test_get_rules_summary(self, rules_dir_with_rules: Path) -> None:
        """Test getting rules summary."""
        engine = RulesEngine(rules_dir_with_rules)
        builder = PromptBuilder(engine)

        summary = builder.get_rules_summary()

        assert "Available Rules" in summary
        assert "test-rule" in summary or "security" in summary

    def test_auto_detect_language(
        self, rules_dir_with_rules: Path, sample_python_code: str
    ) -> None:
        """Test auto-detection of language from file extension."""
        engine = RulesEngine(rules_dir_with_rules)
        builder = PromptBuilder(engine)

        system_prompt, user_prompt = builder.build_review_prompt(
            code=sample_python_code,
            file_path="example.py",
            # No language specified - should be auto-detected
        )

        assert "python" in user_prompt.lower()
