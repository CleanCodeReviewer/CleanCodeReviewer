"""CI/CD runner for automated code review in pipelines."""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Sequence

from clean_code_reviewer.core.llm_client import LLMClient
from clean_code_reviewer.core.prompt_builder import CodeContext, PromptBuilder
from clean_code_reviewer.core.rules_engine import RulesEngine
from clean_code_reviewer.utils.config import get_effective_settings
from clean_code_reviewer.utils.file_ops import find_files, read_file_safe
from clean_code_reviewer.utils.logger import get_logger

logger = get_logger(__name__)


class Severity(str, Enum):
    """Issue severity levels."""

    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


@dataclass
class ReviewIssue:
    """Represents a single review issue."""

    file_path: str
    line: int | None
    severity: Severity
    message: str
    rule: str | None = None
    suggestion: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "file": self.file_path,
            "line": self.line,
            "severity": self.severity.value,
            "message": self.message,
            "rule": self.rule,
            "suggestion": self.suggestion,
        }

    def to_github_annotation(self) -> str:
        """Format as GitHub Actions annotation."""
        level = "error" if self.severity == Severity.ERROR else "warning"
        location = f"file={self.file_path}"
        if self.line:
            location += f",line={self.line}"
        return f"::{level} {location}::{self.message}"


@dataclass
class CIReviewResult:
    """Result from a CI review run."""

    success: bool
    issues: list[ReviewIssue] = field(default_factory=list)
    files_reviewed: int = 0
    error_count: int = 0
    warning_count: int = 0
    summary: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "success": self.success,
            "files_reviewed": self.files_reviewed,
            "error_count": self.error_count,
            "warning_count": self.warning_count,
            "summary": self.summary,
            "issues": [issue.to_dict() for issue in self.issues],
        }

    def to_json(self, indent: int = 2) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict(), indent=indent)


class CIRunner:
    """Runner for CI/CD code review."""

    def __init__(
        self,
        rules_dir: Path | str | None = None,
        model: str | None = None,
        fail_on_error: bool = True,
        fail_on_warning: bool = False,
    ):
        """
        Initialize the CI runner.

        Args:
            rules_dir: Directory containing rules
            model: LLM model to use
            fail_on_error: Fail CI if errors are found
            fail_on_warning: Fail CI if warnings are found
        """
        self.settings = get_effective_settings()
        self.rules_engine = RulesEngine(rules_dir or self.settings.rules_dir)
        self.prompt_builder = PromptBuilder(self.rules_engine)
        self.model = model or self.settings.model
        self.fail_on_error = fail_on_error
        self.fail_on_warning = fail_on_warning

    def review_files(
        self,
        files: Sequence[Path | str],
        tags: list[str] | None = None,
        output_format: str = "text",
    ) -> CIReviewResult:
        """
        Review multiple files for CI.

        Args:
            files: List of file paths to review
            tags: Rule tags to apply
            output_format: Output format ("text", "json", "github")

        Returns:
            CIReviewResult with all issues
        """
        all_issues: list[ReviewIssue] = []
        files_reviewed = 0

        client = LLMClient(model=self.model, settings=self.settings)

        for file_path in files:
            path = Path(file_path)
            if not path.exists():
                logger.warning(f"File not found: {path}")
                continue

            content = read_file_safe(path)
            if content is None:
                continue

            logger.info(f"Reviewing: {path}")
            files_reviewed += 1

            # Build prompt and review
            context = CodeContext.from_file(path)
            if context is None:
                continue

            system_prompt, user_prompt = self.prompt_builder.build_review_prompt(
                code=context,
                tags=tags,
            )

            try:
                result = client.review(system_prompt, user_prompt)
                issues = self._parse_review_result(result.content, str(path))
                all_issues.extend(issues)
            except Exception as e:
                logger.error(f"Error reviewing {path}: {e}")
                all_issues.append(
                    ReviewIssue(
                        file_path=str(path),
                        line=None,
                        severity=Severity.ERROR,
                        message=f"Review failed: {e}",
                    )
                )

        # Calculate counts
        error_count = sum(1 for i in all_issues if i.severity == Severity.ERROR)
        warning_count = sum(1 for i in all_issues if i.severity == Severity.WARNING)

        # Determine success
        success = True
        if self.fail_on_error and error_count > 0:
            success = False
        if self.fail_on_warning and warning_count > 0:
            success = False

        # Build summary
        summary = f"Reviewed {files_reviewed} files. Found {error_count} errors, {warning_count} warnings."

        return CIReviewResult(
            success=success,
            issues=all_issues,
            files_reviewed=files_reviewed,
            error_count=error_count,
            warning_count=warning_count,
            summary=summary,
        )

    def review_directory(
        self,
        directory: Path | str,
        patterns: list[str] | None = None,
        exclude_patterns: list[str] | None = None,
        tags: list[str] | None = None,
    ) -> CIReviewResult:
        """
        Review all matching files in a directory.

        Args:
            directory: Directory to scan
            patterns: File patterns to include (e.g., ["*.py", "*.js"])
            exclude_patterns: Patterns to exclude
            tags: Rule tags to apply

        Returns:
            CIReviewResult with all issues
        """
        directory = Path(directory)

        if patterns is None:
            patterns = ["*.py", "*.js", "*.ts", "*.java", "*.go", "*.rs"]

        # Find all matching files
        files: list[Path] = []
        for file_path in find_files(directory, patterns=patterns):
            # Check exclusions
            if exclude_patterns:
                excluded = False
                for pattern in exclude_patterns:
                    if file_path.match(pattern):
                        excluded = True
                        break
                if excluded:
                    continue

            files.append(file_path)

        logger.info(f"Found {len(files)} files to review in {directory}")
        return self.review_files(files, tags=tags)

    def _parse_review_result(
        self,
        review_content: str,
        file_path: str,
    ) -> list[ReviewIssue]:
        """
        Parse LLM review output into structured issues.

        This is a simplified parser - production implementations might
        want to use a more structured output format from the LLM.
        """
        issues: list[ReviewIssue] = []

        # Simple heuristic parsing
        lines = review_content.split("\n")

        current_severity = Severity.INFO
        current_message_lines: list[str] = []

        for line in lines:
            line_lower = line.lower()

            # Detect severity markers
            if "error" in line_lower or "critical" in line_lower or "bug" in line_lower:
                current_severity = Severity.ERROR
            elif "warning" in line_lower or "issue" in line_lower:
                current_severity = Severity.WARNING

            # Look for line number references
            if "line" in line_lower and any(c.isdigit() for c in line):
                # Extract line number
                import re
                match = re.search(r"line\s*(\d+)", line_lower)
                line_num = int(match.group(1)) if match else None

                if current_message_lines:
                    message = " ".join(current_message_lines).strip()
                    if message:
                        issues.append(
                            ReviewIssue(
                                file_path=file_path,
                                line=line_num,
                                severity=current_severity,
                                message=message,
                            )
                        )
                    current_message_lines = []
                    current_severity = Severity.INFO

            current_message_lines.append(line)

        # If no structured issues found, create a general summary
        if not issues and review_content.strip():
            # Check if the review indicates code is good
            good_indicators = ["looks good", "no issues", "well written", "follows", "clean code"]
            if any(indicator in review_content.lower() for indicator in good_indicators):
                issues.append(
                    ReviewIssue(
                        file_path=file_path,
                        line=None,
                        severity=Severity.INFO,
                        message="Code review passed - no significant issues found.",
                    )
                )
            else:
                # Create a general warning with the review content
                issues.append(
                    ReviewIssue(
                        file_path=file_path,
                        line=None,
                        severity=Severity.WARNING,
                        message=review_content[:500] + ("..." if len(review_content) > 500 else ""),
                    )
                )

        return issues

    def print_results(
        self,
        result: CIReviewResult,
        output_format: str = "text",
        output_file: Path | str | None = None,
    ) -> None:
        """
        Print or save review results.

        Args:
            result: Review result to print
            output_format: Format ("text", "json", "github")
            output_file: Optional file to write output to
        """
        if output_format == "json":
            output = result.to_json()
        elif output_format == "github":
            lines = [result.summary]
            for issue in result.issues:
                lines.append(issue.to_github_annotation())
            output = "\n".join(lines)
        else:
            lines = [f"\n{'='*60}", result.summary, "="*60]
            for issue in result.issues:
                severity_icon = {
                    Severity.ERROR: "",
                    Severity.WARNING: "",
                    Severity.INFO: "",
                }.get(issue.severity, "")

                location = issue.file_path
                if issue.line:
                    location += f":{issue.line}"

                lines.append(f"\n{severity_icon} [{issue.severity.value.upper()}] {location}")
                lines.append(f"   {issue.message}")

            output = "\n".join(lines)

        if output_file:
            Path(output_file).write_text(output, encoding="utf-8")
            logger.info(f"Results written to: {output_file}")
        else:
            print(output)

    def run_and_exit(
        self,
        files: list[Path | str] | None = None,
        directory: Path | str | None = None,
        **kwargs: Any,
    ) -> None:
        """
        Run review and exit with appropriate code.

        Args:
            files: Files to review (if specified)
            directory: Directory to review (if no files specified)
            **kwargs: Additional arguments for review methods
        """
        if files:
            result = self.review_files(files, **kwargs)
        elif directory:
            result = self.review_directory(directory, **kwargs)
        else:
            result = self.review_directory(Path.cwd(), **kwargs)

        self.print_results(result, output_format=kwargs.get("output_format", "text"))

        sys.exit(0 if result.success else 1)
