"""Prompt builder for constructing LLM prompts from code and rules."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from clean_code_reviewer.core.rules_engine import RulesEngine
from clean_code_reviewer.utils.file_ops import (
    get_file_extension,
    get_language_from_extension,
    read_file_safe,
)
from clean_code_reviewer.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class CodeContext:
    """Context information about the code being reviewed."""

    content: str
    file_path: str | None = None
    language: str | None = None
    start_line: int | None = None
    end_line: int | None = None

    @classmethod
    def from_file(cls, file_path: Path | str) -> "CodeContext | None":
        """Create a CodeContext from a file path."""
        path = Path(file_path)
        content = read_file_safe(path)

        if content is None:
            return None

        extension = get_file_extension(path)
        language = get_language_from_extension(extension)

        return cls(
            content=content,
            file_path=str(path),
            language=language,
        )


class PromptBuilder:
    """Builder for constructing code review prompts."""

    DEFAULT_SYSTEM_PROMPT = """You are an expert code reviewer. Your task is to review the provided code
according to the specified coding rules and best practices.

For each issue found, provide:
1. The specific line or section with the issue
2. A clear explanation of why it's an issue
3. A suggested fix or improvement

Be constructive and educational in your feedback. Focus on:
- Code quality and maintainability
- Adherence to the provided coding rules
- Potential bugs or security issues
- Performance considerations where relevant

If the code follows all rules and best practices, acknowledge that and optionally
suggest minor improvements if any.
"""

    REVIEW_PROMPT_TEMPLATE = """Please review the following code according to the coding rules provided.

## Coding Rules to Apply

{rules}

## Code to Review

File: {file_path}
Language: {language}

```{language_hint}
{code}
```

## Review Instructions

Analyze the code above and provide a detailed review. For each issue:
1. Quote the problematic code
2. Explain the issue referencing the specific rule
3. Provide a corrected version

If the code is well-written and follows all rules, state that clearly.
"""

    def __init__(
        self,
        rules_engine: RulesEngine | None = None,
        system_prompt: str | None = None,
    ):
        """
        Initialize the prompt builder.

        Args:
            rules_engine: RulesEngine instance for loading rules
            system_prompt: Custom system prompt (uses default if None)
        """
        self.rules_engine = rules_engine or RulesEngine()
        self.system_prompt = system_prompt or self.DEFAULT_SYSTEM_PROMPT

    def build_review_prompt(
        self,
        code: CodeContext | str,
        file_path: str | None = None,
        language: str | None = None,
        tags: list[str] | None = None,
        tag_order: list[str] | None = None,
    ) -> tuple[str, str]:
        """
        Build a complete review prompt from code and rules.

        Args:
            code: Code content or CodeContext object
            file_path: File path (used if code is string)
            language: Programming language (auto-detected if not specified)
            tags: Rule tags to include
            tag_order: Custom tag ordering for rules

        Returns:
            Tuple of (system_prompt, user_prompt)
        """
        # Normalize code to CodeContext
        if isinstance(code, str):
            context = CodeContext(
                content=code,
                file_path=file_path,
                language=language,
            )
        else:
            context = code
            if language:
                context.language = language
            if file_path:
                context.file_path = file_path

        # Auto-detect language from file extension if not specified
        if context.language is None and context.file_path:
            ext = get_file_extension(context.file_path)
            context.language = get_language_from_extension(ext)

        # Get merged rules
        rules_content = self.rules_engine.merge_rules(
            language=context.language,
            tags=tags,
            tag_order=tag_order,
        )

        if not rules_content:
            rules_content = "No specific rules loaded. Apply general best practices."

        # Build the user prompt
        user_prompt = self.REVIEW_PROMPT_TEMPLATE.format(
            rules=rules_content,
            file_path=context.file_path or "unknown",
            language=context.language or "unknown",
            language_hint=context.language or "",
            code=context.content,
        )

        return self.system_prompt, user_prompt

    def build_multi_file_prompt(
        self,
        files: list[CodeContext | tuple[str, str]],
        tags: list[str] | None = None,
        tag_order: list[str] | None = None,
    ) -> tuple[str, str]:
        """
        Build a prompt for reviewing multiple files.

        Args:
            files: List of CodeContext objects or (file_path, content) tuples
            tags: Rule tags to include
            tag_order: Custom tag ordering for rules

        Returns:
            Tuple of (system_prompt, user_prompt)
        """
        # Normalize files to CodeContext
        contexts: list[CodeContext] = []
        for item in files:
            if isinstance(item, CodeContext):
                contexts.append(item)
            else:
                file_path, content = item
                ext = get_file_extension(file_path)
                language = get_language_from_extension(ext)
                contexts.append(
                    CodeContext(
                        content=content,
                        file_path=file_path,
                        language=language,
                    )
                )

        # Collect unique languages
        languages = {c.language for c in contexts if c.language}

        # Get rules for all languages
        all_rules_parts = []
        for lang in languages:
            rules = self.rules_engine.merge_rules(
                language=lang,
                tags=tags,
                tag_order=tag_order,
            )
            if rules:
                all_rules_parts.append(f"### Rules for {lang}\n\n{rules}")

        # Also get universal rules
        universal_rules = self.rules_engine.merge_rules(
            language=None,
            tags=tags,
            tag_order=tag_order,
        )
        if universal_rules:
            all_rules_parts.insert(0, f"### Universal Rules\n\n{universal_rules}")

        rules_content = "\n\n---\n\n".join(all_rules_parts) if all_rules_parts else "No specific rules loaded."

        # Build code sections
        code_sections = []
        for ctx in contexts:
            section = f"""### File: {ctx.file_path or "unknown"}
Language: {ctx.language or "unknown"}

```{ctx.language or ""}
{ctx.content}
```"""
            code_sections.append(section)

        user_prompt = f"""Please review the following files according to the coding rules provided.

## Coding Rules to Apply

{rules_content}

## Files to Review

{chr(10).join(code_sections)}

## Review Instructions

Analyze each file and provide a detailed review. For each issue:
1. Identify the file and line
2. Quote the problematic code
3. Explain the issue referencing the specific rule
4. Provide a corrected version

Provide a summary at the end with the overall code quality assessment.
"""

        return self.system_prompt, user_prompt

    def build_focused_prompt(
        self,
        code: CodeContext | str,
        focus_areas: list[str],
        file_path: str | None = None,
        language: str | None = None,
    ) -> tuple[str, str]:
        """
        Build a prompt focused on specific areas.

        Args:
            code: Code content or CodeContext
            focus_areas: Areas to focus on (e.g., ["security", "performance"])
            file_path: File path
            language: Programming language

        Returns:
            Tuple of (system_prompt, user_prompt)
        """
        # Use tags to filter rules
        return self.build_review_prompt(
            code=code,
            file_path=file_path,
            language=language,
            tags=focus_areas,
            tag_order=focus_areas,
        )

    def get_rules_summary(
        self,
        language: str | None = None,
        tags: list[str] | None = None,
    ) -> str:
        """
        Get a summary of applicable rules.

        Args:
            language: Target language
            tags: Tags to filter by

        Returns:
            Summary string
        """
        rules = self.rules_engine.get_rules_for_language(language)

        if tags:
            rules = [r for r in rules if any(r.has_tag(t) for t in tags)]

        if not rules:
            return "No rules available for the specified criteria."

        lines = ["Available Rules:", ""]
        for rule in rules:
            tags_str = f" [{', '.join(rule.tags)}]" if rule.tags else ""
            lang_str = f" ({rule.language})" if rule.language else ""
            lines.append(f"- {rule.name}{lang_str}{tags_str}")

        return "\n".join(lines)
