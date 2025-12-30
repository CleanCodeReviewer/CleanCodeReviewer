"""Integration tests for the CLI."""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from clean_code_reviewer.cli import app


runner = CliRunner()


class TestCLIInit:
    """Tests for the init command."""

    def test_init_creates_directory(self, tmp_path: Path) -> None:
        """Test that init creates the rules directory with proper structure."""
        result = runner.invoke(app, ["init", str(tmp_path), "--non-interactive", "--skip-download"])

        assert result.exit_code == 0
        assert (tmp_path / ".cleancoderules").is_dir()
        assert (tmp_path / ".cleancoderules" / "community").is_dir()
        assert (tmp_path / ".cleancoderules" / "team").is_dir()
        assert (tmp_path / ".cleancoderules" / "config.yaml").exists()
        assert (tmp_path / ".cleancoderules" / "base.md").exists()
        assert (tmp_path / ".cleancoderules" / "team" / "example.md").exists()

    def test_init_existing_directory(self, tmp_path: Path) -> None:
        """Test init with existing rules directory."""
        rules_dir = tmp_path / ".cleancoderules"
        rules_dir.mkdir()

        result = runner.invoke(app, ["init", str(tmp_path)])

        assert result.exit_code == 1
        assert "already exists" in result.stdout.lower()

    def test_init_force_overwrite(self, tmp_path: Path) -> None:
        """Test init with --force flag."""
        rules_dir = tmp_path / ".cleancoderules"
        rules_dir.mkdir()

        result = runner.invoke(app, ["init", str(tmp_path), "--force", "--non-interactive", "--skip-download"])

        assert result.exit_code == 0
        assert (rules_dir / "config.yaml").exists()


class TestCLIList:
    """Tests for the list command."""

    def test_list_no_rules(self, tmp_path: Path) -> None:
        """Test list with no rules installed."""
        rules_dir = tmp_path / ".cleancoderules"
        rules_dir.mkdir()

        result = runner.invoke(app, ["list", "-d", str(rules_dir)])

        assert result.exit_code == 0
        assert "no rules" in result.stdout.lower()

    def test_list_with_rules(self, tmp_path: Path) -> None:
        """Test list with rules installed."""
        # Initialize first
        runner.invoke(app, ["init", str(tmp_path), "-y", "--skip-download"])

        result = runner.invoke(app, ["list", "-d", str(tmp_path / ".cleancoderules")])

        assert result.exit_code == 0
        # Should show the base rule from init
        assert "base" in result.stdout.lower() or "rule" in result.stdout.lower()


class TestCLIConfig:
    """Tests for the config command."""

    def test_config_no_file(self, tmp_path: Path) -> None:
        """Test config with no config file."""
        rules_dir = tmp_path / ".cleancoderules"
        rules_dir.mkdir()

        result = runner.invoke(app, ["config", "-d", str(rules_dir)])

        assert result.exit_code == 1
        assert "no configuration" in result.stdout.lower()

    def test_config_show(self, tmp_path: Path) -> None:
        """Test config show."""
        # Initialize first
        runner.invoke(app, ["init", str(tmp_path), "-y", "--skip-download"])

        result = runner.invoke(app, ["config", "-d", str(tmp_path / ".cleancoderules")])

        assert result.exit_code == 0
        assert "model" in result.stdout.lower()


class TestCLIVersion:
    """Tests for version option."""

    def test_version_flag(self) -> None:
        """Test --version flag."""
        result = runner.invoke(app, ["--version"])

        assert result.exit_code == 0
        assert "clean code reviewer" in result.stdout.lower()

    def test_version_short_flag(self) -> None:
        """Test -v flag."""
        result = runner.invoke(app, ["-v"])

        assert result.exit_code == 0


class TestCLIHelp:
    """Tests for help option."""

    def test_help(self) -> None:
        """Test --help flag."""
        result = runner.invoke(app, ["--help"])

        assert result.exit_code == 0
        assert "init" in result.stdout
        assert "review" in result.stdout
        assert "list" in result.stdout
