"""Rules engine for scanning, parsing, and merging coding rules.

Supports both YAML (.yml) and Markdown (.md) rule files.
YAML files use structured keys for field-level merging.
Markdown files are legacy format with YAML frontmatter.
"""

from __future__ import annotations

import copy
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from clean_code_reviewer.core.order_manager import OrderManager
from clean_code_reviewer.utils.file_ops import find_files, read_file_safe
from clean_code_reviewer.utils.logger import get_logger

logger = get_logger(__name__)


# Level hierarchy: base (1) < community (2) < team (3)
# Inferred from: base.md/base.yml = L1, community/ = L2, team/ = L3
LEVEL_NAMES = {1: "Base", 2: "Community", 3: "Team"}


@dataclass
class Rule:
    """Represents a single coding rule.

    For YAML rules: `data` contains the structured rule content.
    For Markdown rules: `content` contains the markdown text (legacy).
    """

    name: str
    content: str = ""  # Legacy: markdown content (for .md files)
    data: dict[str, Any] = field(default_factory=dict)  # Structured: YAML content
    level: int = 2  # Default to community level (inferred from path)
    order: int = 1000  # From order.yml only (NOT frontmatter); higher = loaded later
    language: str | None = None
    tags: list[str] = field(default_factory=list)
    source_file: Path | None = None
    is_yaml: bool = False  # True if parsed from .yml file

    # Frontmatter metadata (for .md files)
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def level_name(self) -> str:
        """Get human-readable level name."""
        return LEVEL_NAMES.get(self.level, "Unknown")

    def matches_language(self, language: str | None) -> bool:
        """Check if this rule applies to the given language."""
        if self.language is None:
            return True  # Universal rule
        if language is None:
            return True  # No language specified, include all
        return self.language.lower() == language.lower()

    def has_tag(self, tag: str) -> bool:
        """Check if this rule has the given tag."""
        return tag.lower() in [t.lower() for t in self.tags]


class RulesEngine:
    """Engine for managing and processing coding rules."""

    # Regex for YAML frontmatter (for .md files)
    FRONTMATTER_PATTERN = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)

    def __init__(self, rules_dir: Path | str | None = None):
        """
        Initialize the rules engine.

        Args:
            rules_dir: Directory containing rule files (defaults to .cleancoderules)
        """
        if rules_dir is None:
            rules_dir = Path.cwd() / ".cleancoderules"
        self.rules_dir = Path(rules_dir)
        self._rules: list[Rule] = []
        self._loaded = False

    @property
    def rules(self) -> list[Rule]:
        """Get all loaded rules."""
        if not self._loaded:
            self.load_rules()
        return self._rules

    def load_rules(self) -> list[Rule]:
        """
        Load all rules from the rules directory.

        Supports both .yml (structured) and .md (legacy) files.
        If both exist for the same rule, .yml takes precedence.

        Returns:
            List of loaded Rule objects
        """
        self._rules = []

        if not self.rules_dir.exists():
            logger.warning(f"Rules directory not found: {self.rules_dir}")
            self._loaded = True
            return self._rules

        # Load order from order.yml
        order_manager = OrderManager(self.rules_dir)

        # Find all rule files (.yml preferred, .md as fallback)
        yml_files = set(find_files(self.rules_dir, patterns=["*.yml", "*.yaml"], recursive=True))
        md_files = set(find_files(self.rules_dir, patterns=["*.md"], recursive=True))

        # Build a map of rule stems to avoid duplicates (prefer .yml over .md)
        rule_files: dict[str, Path] = {}
        for file_path in md_files:
            if file_path.name.lower() == "readme.md":
                continue
            stem = str(file_path.with_suffix(""))
            rule_files[stem] = file_path

        for file_path in yml_files:
            # Skip order.yml and config.yaml
            if file_path.name.lower() in ["order.yml", "order.yaml", "config.yml", "config.yaml"]:
                continue
            stem = str(file_path.with_suffix(""))
            rule_files[stem] = file_path  # Override .md with .yml

        for file_path in rule_files.values():
            rule = self._parse_rule_file(file_path)
            if rule:
                # Get order from order.yml based on directory and rule name
                directory = self._get_directory_for_rule(file_path)
                rule_key = self._get_rule_key(file_path, directory)
                rule.order = order_manager.get_order_value(directory, rule_key)

                self._rules.append(rule)
                logger.debug(f"Loaded rule: {rule.name} from {file_path}")

        # Sort rules by level (ascending), then order (ascending), then filename (ascending)
        # Lower level/order loaded first, higher loaded later (overrides)
        # Filename provides deterministic tiebreaker for same level+order
        self._rules.sort(key=lambda r: (r.level, r.order, r.name.lower()))

        self._loaded = True
        logger.info(f"Loaded {len(self._rules)} rules from {self.rules_dir}")
        return self._rules

    def _get_directory_for_rule(self, file_path: Path) -> str:
        """Get the directory category for a rule file."""
        try:
            rel_path = file_path.relative_to(self.rules_dir)
            parts = rel_path.parts
            if parts and parts[0].lower() in ["community", "team"]:
                return parts[0].lower()
        except ValueError:
            pass
        return "community"  # Default

    def _get_rule_key(self, file_path: Path, directory: str) -> str:
        """Get the rule key for order.yml lookup."""
        try:
            rel_path = file_path.relative_to(self.rules_dir)
            parts = rel_path.parts

            if parts and parts[0].lower() == directory:
                # Remove directory prefix and .md extension
                sub_path = "/".join(parts[1:])
                if sub_path.endswith(".md"):
                    sub_path = sub_path[:-3]
                return sub_path

            # For base.md or other root files
            if len(parts) == 1:
                return parts[0].replace(".md", "")

        except ValueError:
            pass
        return file_path.stem

    def _parse_rule_file(self, file_path: Path) -> Rule | None:
        """
        Parse a rule file into a Rule object.

        Supports both .yml (structured) and .md (legacy) files.

        Args:
            file_path: Path to the rule file

        Returns:
            Rule object or None if parsing failed
        """
        content = read_file_safe(file_path)
        if content is None:
            return None

        # Check if this is a YAML file
        if file_path.suffix.lower() in [".yml", ".yaml"]:
            return self._parse_yaml_rule(file_path, content)
        else:
            return self._parse_markdown_rule(file_path, content)

    def _parse_yaml_rule(self, file_path: Path, content: str) -> Rule | None:
        """Parse a YAML rule file."""
        try:
            data = yaml.safe_load(content) or {}
        except yaml.YAMLError as e:
            logger.warning(f"Failed to parse YAML in {file_path}: {e}")
            return None

        # Extract metadata from _meta section
        meta = data.pop("_meta", {})
        name = meta.get("name", file_path.stem)
        language = meta.get("language")
        tags = meta.get("tags", [])

        if isinstance(tags, str):
            tags = [tags]

        # Infer level from file path
        level = self._infer_level(file_path)

        return Rule(
            name=name,
            content="",  # No markdown content for YAML rules
            data=data,  # Structured rule data
            level=level,
            order=1000,  # Default; actual order set from order.yml in load_rules()
            language=language,
            tags=tags,
            source_file=file_path,
            is_yaml=True,
            metadata=meta,
        )

    def _parse_markdown_rule(self, file_path: Path, content: str) -> Rule | None:
        """Parse a Markdown rule file (legacy format)."""
        # Extract frontmatter if present
        frontmatter: dict[str, Any] = {}
        rule_content = content

        match = self.FRONTMATTER_PATTERN.match(content)
        if match:
            try:
                frontmatter = yaml.safe_load(match.group(1)) or {}
                rule_content = content[match.end() :]
            except yaml.YAMLError as e:
                logger.warning(f"Failed to parse frontmatter in {file_path}: {e}")

        # Extract rule properties (order is NOT in frontmatter - managed via order.yml)
        name = frontmatter.get("name", file_path.stem)
        language = frontmatter.get("language")
        tags = frontmatter.get("tags", [])

        if isinstance(tags, str):
            tags = [tags]

        # Infer level from file path: base.md = L1, teams/ = L3, else = L2
        level = frontmatter.get("level", self._infer_level(file_path))

        return Rule(
            name=name,
            content=rule_content.strip(),
            data={},  # No structured data for markdown rules
            level=level,
            order=1000,  # Default; actual order set from order.yml in load_rules()
            language=language,
            tags=tags,
            source_file=file_path,
            is_yaml=False,
            metadata=frontmatter,
        )

    def _infer_level(self, file_path: Path) -> int:
        """
        Infer rule level from file path.

        Convention:
        - base.md (exact filename at root) -> Level 1 (base principles)
        - community/**/*.md -> Level 2 (all external/community rules)
        - team/**/*.md -> Level 3 (team rules, highest priority)

        Args:
            file_path: Path to the rule file

        Returns:
            Level number (1, 2, or 3)
        """
        try:
            # Get path relative to rules_dir
            rel_path = file_path.relative_to(self.rules_dir)
            parts = rel_path.parts

            # base.md at root = Level 1
            if len(parts) == 1 and parts[0].lower() == "base.md":
                return 1

            if parts:
                first_dir = parts[0].lower()
                if first_dir == "community":
                    return 2
                if first_dir == "team":
                    return 3

            # Default to community level
            return 2
        except ValueError:
            return 2

    def get_rules_for_language(self, language: str | None = None) -> list[Rule]:
        """
        Get rules applicable to a specific language.

        Args:
            language: Target language (e.g., "python", "javascript")

        Returns:
            List of applicable rules
        """
        return [rule for rule in self.rules if rule.matches_language(language)]

    def get_rules_by_tags(self, tags: list[str]) -> list[Rule]:
        """
        Get rules that have any of the specified tags.

        Args:
            tags: List of tags to filter by

        Returns:
            List of matching rules
        """
        if not tags:
            return self.rules

        return [rule for rule in self.rules if any(rule.has_tag(tag) for tag in tags)]

    def get_rule_by_name(self, name: str) -> Rule | None:
        """
        Get a specific rule by name.

        Args:
            name: Rule name

        Returns:
            Rule object or None if not found
        """
        for rule in self.rules:
            if rule.name.lower() == name.lower():
                return rule
        return None

    def merge_rules(
        self,
        language: str | None = None,
        tags: list[str] | None = None,
        tag_order: list[str] | None = None,
    ) -> str:
        """
        Merge applicable rules into a single string.

        For YAML rules: performs field-level deep merging (higher levels override lower).
        For Markdown rules: concatenates content with level headers (legacy behavior).

        Args:
            language: Target language to filter by
            tags: Tags to filter by
            tag_order: Custom tag ordering (tags listed first have lower order)

        Returns:
            Merged rules as a YAML string (for YAML rules) or markdown string (for legacy)
        """
        # Get applicable rules
        rules = self.get_rules_for_language(language)

        # Filter by tags if specified
        if tags:
            rules = [r for r in rules if any(r.has_tag(tag) for tag in tags)]

        # Apply custom tag ordering if specified
        if tag_order:
            rules = self._sort_by_tag_order(rules, tag_order)

        # Check if we have any YAML rules
        yaml_rules = [r for r in rules if r.is_yaml]
        md_rules = [r for r in rules if not r.is_yaml]

        # If we have YAML rules, do field-level merging
        if yaml_rules:
            return self._merge_yaml_rules(yaml_rules, md_rules)
        else:
            return self._merge_markdown_rules(md_rules)

    def _merge_yaml_rules(
        self, yaml_rules: list[Rule], md_rules: list[Rule]
    ) -> str:
        """
        Merge YAML rules using field-level deep merging.

        Rules are merged in order (level ASC, order ASC).
        Higher level/order rules override lower ones at the field level.

        Args:
            yaml_rules: List of YAML rules to merge
            md_rules: List of legacy markdown rules (appended as-is)

        Returns:
            Merged rules as YAML string
        """
        # Start with empty merged data
        merged: dict[str, Any] = {}

        # Merge each rule's data (already sorted by level, order)
        for rule in yaml_rules:
            merged = self._deep_merge(merged, rule.data)

        # Convert to YAML string
        output_parts = []

        # Add header comment
        output_parts.append("# Merged Coding Rules")
        output_parts.append("# Higher-level rules have already overridden lower-level rules.")
        output_parts.append("")

        # Dump merged YAML
        yaml_output = yaml.dump(
            merged,
            default_flow_style=False,
            allow_unicode=True,
            sort_keys=False,
            width=100,
        )
        output_parts.append(yaml_output)

        # Append any legacy markdown rules
        if md_rules:
            output_parts.append("")
            output_parts.append("# --- Legacy Markdown Rules ---")
            for rule in md_rules:
                output_parts.append(f"\n## {rule.name}")
                if rule.language:
                    output_parts.append(f"Language: {rule.language}")
                output_parts.append("")
                output_parts.append(rule.content)

        return "\n".join(output_parts)

    def _deep_merge(self, base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
        """
        Deep merge two dictionaries with field-level override semantics.

        - If both values are dicts: recursively merge
        - If override has a value: it replaces base (field-level override)
        - If override is missing a field: inherit from base

        Args:
            base: Base dictionary (lower priority)
            override: Override dictionary (higher priority)

        Returns:
            Merged dictionary
        """
        result = copy.deepcopy(base)

        for key, override_value in override.items():
            if key in result:
                base_value = result[key]

                # Both are dicts: recursive merge
                if isinstance(base_value, dict) and isinstance(override_value, dict):
                    result[key] = self._deep_merge(base_value, override_value)
                else:
                    # Override replaces base (including lists, scalars, rich values)
                    result[key] = copy.deepcopy(override_value)
            else:
                # New key from override
                result[key] = copy.deepcopy(override_value)

        return result

    def _merge_markdown_rules(self, rules: list[Rule]) -> str:
        """
        Merge markdown rules using legacy concatenation approach.

        Args:
            rules: List of markdown rules

        Returns:
            Merged rules as markdown string with level headers
        """
        # Group rules by level
        rules_by_level: dict[int, list[Rule]] = {1: [], 2: [], 3: []}
        for rule in rules:
            rules_by_level.setdefault(rule.level, []).append(rule)

        # Build merged output with level headers
        merged_parts = []

        level_headers = {
            1: "## LEVEL 1: Base Principles",
            2: "## LEVEL 2: Community Rules",
            3: "## LEVEL 3: Team Rules (HIGHEST PRIORITY)",
        }

        for level in [1, 2, 3]:
            level_rules = rules_by_level.get(level, [])
            if not level_rules:
                continue

            # Add level header
            merged_parts.append(level_headers[level])

            # Add each rule in this level
            for rule in level_rules:
                header = f"### {rule.name}"
                if rule.language:
                    header += f" ({rule.language})"

                merged_parts.append(f"{header}\n\n{rule.content}")

        # Add conflict resolution note
        if merged_parts:
            merged_parts.append(
                "---\n\n"
                "**CONFLICT RESOLUTION:** If rules conflict, higher levels override lower levels. "
                "Team rules (Level 3) always take precedence."
            )

        return "\n\n".join(merged_parts)

    def _sort_by_tag_order(
        self, rules: list[Rule], tag_order: list[str]
    ) -> list[Rule]:
        """Sort rules by tag order (tags listed first = lower order = loaded first)."""

        def get_tag_position(rule: Rule) -> int:
            for i, tag in enumerate(tag_order):
                if rule.has_tag(tag):
                    return i
            return len(tag_order)  # Rules without listed tags go last

        return sorted(rules, key=lambda r: (get_tag_position(r), r.order, r.name.lower()))

    def list_rules(self) -> list[dict[str, Any]]:
        """
        Get a summary list of all rules.

        Returns:
            List of rule summaries
        """
        return [
            {
                "name": rule.name,
                "level": rule.level,
                "level_name": rule.level_name,
                "language": rule.language,
                "tags": rule.tags,
                "order": rule.order,
                "source": str(rule.source_file) if rule.source_file else None,
            }
            for rule in self.rules
        ]

    def reload(self) -> None:
        """Force reload of all rules."""
        self._loaded = False
        self._rules = []
        self.load_rules()
