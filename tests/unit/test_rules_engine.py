"""Unit tests for the rules engine."""

from __future__ import annotations

from pathlib import Path

import pytest

from clean_code_reviewer.core.rules_engine import Rule, RulesEngine


class TestRule:
    """Tests for the Rule dataclass."""

    def test_rule_creation(self) -> None:
        """Test basic rule creation."""
        rule = Rule(
            name="test-rule",
            content="Test content",
            language="python",
            tags=["style", "test"],
        )

        assert rule.name == "test-rule"
        assert rule.content == "Test content"
        assert rule.order == 1000  # Default; actual order from order.yml
        assert rule.language == "python"
        assert rule.tags == ["style", "test"]

    def test_rule_matches_language(self) -> None:
        """Test language matching."""
        python_rule = Rule(name="python", content="", language="python")
        universal_rule = Rule(name="universal", content="", language=None)

        assert python_rule.matches_language("python")
        assert python_rule.matches_language("Python")
        assert not python_rule.matches_language("javascript")

        # Universal rules match any language
        assert universal_rule.matches_language("python")
        assert universal_rule.matches_language("javascript")
        assert universal_rule.matches_language(None)

    def test_rule_has_tag(self) -> None:
        """Test tag checking."""
        rule = Rule(name="test", content="", tags=["security", "Style"])

        assert rule.has_tag("security")
        assert rule.has_tag("Security")
        assert rule.has_tag("style")
        assert not rule.has_tag("performance")


class TestRulesEngine:
    """Tests for the RulesEngine class."""

    def test_engine_creation(self, temp_rules_dir: Path) -> None:
        """Test engine creation."""
        engine = RulesEngine(temp_rules_dir)
        assert engine.rules_dir == temp_rules_dir
        assert engine.rules == []

    def test_load_rules_from_empty_dir(self, temp_rules_dir: Path) -> None:
        """Test loading rules from empty directory."""
        engine = RulesEngine(temp_rules_dir)
        rules = engine.load_rules()
        assert rules == []

    def test_load_rules_from_nonexistent_dir(self, tmp_path: Path) -> None:
        """Test loading rules from non-existent directory."""
        engine = RulesEngine(tmp_path / "nonexistent")
        rules = engine.load_rules()
        assert rules == []

    def test_load_rules_with_content(self, rules_dir_with_rules: Path) -> None:
        """Test loading rules from directory with rules."""
        engine = RulesEngine(rules_dir_with_rules)
        rules = engine.load_rules()

        assert len(rules) == 2

        # Check rules are sorted by level then order
        assert (rules[0].level, rules[0].order) <= (rules[1].level, rules[1].order)

    def test_get_rules_for_language(self, rules_dir_with_rules: Path) -> None:
        """Test filtering rules by language."""
        engine = RulesEngine(rules_dir_with_rules)

        python_rules = engine.get_rules_for_language("python")
        all_rules = engine.get_rules_for_language(None)

        # Python-specific + universal rules
        assert len(python_rules) >= 1
        assert len(all_rules) >= len(python_rules)

    def test_get_rules_by_tags(self, rules_dir_with_rules: Path) -> None:
        """Test filtering rules by tags."""
        engine = RulesEngine(rules_dir_with_rules)

        security_rules = engine.get_rules_by_tags(["security"])
        style_rules = engine.get_rules_by_tags(["style"])

        assert len(security_rules) >= 1
        assert all(r.has_tag("security") for r in security_rules)

    def test_get_rule_by_name(self, rules_dir_with_rules: Path) -> None:
        """Test getting a specific rule by name."""
        engine = RulesEngine(rules_dir_with_rules)

        rule = engine.get_rule_by_name("test-rule")
        assert rule is not None
        assert rule.name == "test-rule"

        # Case insensitive
        rule2 = engine.get_rule_by_name("TEST-RULE")
        assert rule2 is not None

        # Non-existent
        none_rule = engine.get_rule_by_name("nonexistent")
        assert none_rule is None

    def test_merge_rules(self, rules_dir_with_rules: Path) -> None:
        """Test merging rules into a single string."""
        engine = RulesEngine(rules_dir_with_rules)

        merged = engine.merge_rules()
        assert "test-rule" in merged.lower() or "security" in merged.lower()
        assert len(merged) > 0

        # Merge with language filter
        python_merged = engine.merge_rules(language="python")
        assert len(python_merged) > 0

    def test_list_rules(self, rules_dir_with_rules: Path) -> None:
        """Test getting rule summaries."""
        engine = RulesEngine(rules_dir_with_rules)

        summaries = engine.list_rules()
        assert len(summaries) == 2

        for summary in summaries:
            assert "name" in summary
            assert "order" in summary

    def test_reload(self, rules_dir_with_rules: Path) -> None:
        """Test reloading rules."""
        engine = RulesEngine(rules_dir_with_rules)

        # Initial load
        rules1 = engine.rules
        assert len(rules1) == 2

        # Add a new rule
        new_rule = """---
name: new-rule
---

# New Rule

New content.
"""
        (rules_dir_with_rules / "new-rule.md").write_text(new_rule)

        # Reload
        engine.reload()
        rules2 = engine.rules

        assert len(rules2) == 3


class TestRulesParsing:
    """Tests for rule file parsing."""

    def test_parse_rule_with_frontmatter(self, temp_rules_dir: Path) -> None:
        """Test parsing a rule with YAML frontmatter."""
        content = """---
name: custom-name
language: javascript
tags: [a, b, c]
custom_field: value
---

# Rule Content

This is the rule body.
"""
        (temp_rules_dir / "test.md").write_text(content)

        engine = RulesEngine(temp_rules_dir)
        rules = engine.load_rules()

        assert len(rules) == 1
        rule = rules[0]

        assert rule.name == "custom-name"
        assert rule.order == 1000  # Default; order comes from order.yml
        assert rule.language == "javascript"
        assert rule.tags == ["a", "b", "c"]
        assert rule.metadata.get("custom_field") == "value"
        assert "Rule Content" in rule.content

    def test_parse_rule_without_frontmatter(self, temp_rules_dir: Path) -> None:
        """Test parsing a rule without frontmatter."""
        content = """# Simple Rule

Just content, no frontmatter.
"""
        (temp_rules_dir / "simple.md").write_text(content)

        engine = RulesEngine(temp_rules_dir)
        rules = engine.load_rules()

        assert len(rules) == 1
        rule = rules[0]

        assert rule.name == "simple"  # Uses filename
        assert rule.order == 1000  # Default; order comes from order.yml
        assert rule.language is None
        assert "Simple Rule" in rule.content

    def test_parse_rule_with_invalid_frontmatter(self, temp_rules_dir: Path) -> None:
        """Test parsing a rule with invalid YAML frontmatter."""
        content = """---
invalid: yaml: content
---

# Content
"""
        (temp_rules_dir / "invalid.md").write_text(content)

        engine = RulesEngine(temp_rules_dir)
        rules = engine.load_rules()

        # Should still load, just without parsed frontmatter
        assert len(rules) == 1
