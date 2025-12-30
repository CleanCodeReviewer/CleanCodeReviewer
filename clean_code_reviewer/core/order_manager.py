"""Manager for rule ordering via order.yml."""

from __future__ import annotations

from pathlib import Path

import yaml

from clean_code_reviewer.utils.file_ops import read_file_safe, write_file_safe
from clean_code_reviewer.utils.logger import get_logger

logger = get_logger(__name__)

# Default order.yml structure
DEFAULT_ORDER: dict[str, list[str]] = {
    "community": [],
    "team": [],
}


class OrderManager:
    """Manages rule ordering through order.yml file."""

    def __init__(self, rules_dir: Path | str):
        """
        Initialize the order manager.

        Args:
            rules_dir: Path to the .cleancoderules directory
        """
        self.rules_dir = Path(rules_dir)
        self.order_file = self.rules_dir / "order.yml"
        self._order: dict[str, list[str]] | None = None

    @property
    def order(self) -> dict[str, list[str]]:
        """Get the current order, loading from file if needed."""
        if self._order is None:
            self._order = self.load()
        return self._order

    def load(self) -> dict[str, list[str]]:
        """
        Load order from order.yml.

        Returns:
            Dictionary with directory -> list of rule names
        """
        if not self.order_file.exists():
            return DEFAULT_ORDER.copy()

        content = read_file_safe(self.order_file)
        if content is None:
            return DEFAULT_ORDER.copy()

        try:
            data = yaml.safe_load(content) or {}
            # Ensure all directories exist
            result = DEFAULT_ORDER.copy()
            for key in result:
                if key in data and isinstance(data[key], list):
                    result[key] = data[key]
            return result
        except yaml.YAMLError as e:
            logger.warning(f"Failed to parse order.yml: {e}")
            return DEFAULT_ORDER.copy()

    def save(self) -> bool:
        """
        Save current order to order.yml.

        Returns:
            True if saved successfully
        """
        content = "# Rule ordering - position determines priority\n"
        content += "# Later in list = higher priority = overrides earlier\n\n"
        content += yaml.dump(self.order, default_flow_style=False, sort_keys=False)
        return write_file_safe(self.order_file, content)

    def add_rule(self, directory: str, rule_name: str) -> None:
        """
        Add a rule to the order list.

        Args:
            directory: Target directory (lang, community, team)
            rule_name: Rule name (e.g., "google/python" or "my-rule")
        """
        if directory not in self.order:
            self.order[directory] = []

        # Don't add duplicates
        if rule_name not in self.order[directory]:
            self.order[directory].append(rule_name)
            self.save()

    def remove_rule(self, directory: str, rule_name: str) -> bool:
        """
        Remove a rule from the order list.

        Args:
            directory: Target directory
            rule_name: Rule name to remove

        Returns:
            True if rule was removed
        """
        if directory in self.order and rule_name in self.order[directory]:
            self.order[directory].remove(rule_name)
            self.save()
            return True
        return False

    def move_up(self, directory: str, rule_name: str) -> bool:
        """
        Move a rule up in the order (lower priority).

        Args:
            directory: Target directory
            rule_name: Rule name to move

        Returns:
            True if moved successfully
        """
        if directory not in self.order:
            return False

        rules = self.order[directory]
        if rule_name not in rules:
            return False

        idx = rules.index(rule_name)
        if idx == 0:
            return False  # Already at top

        rules[idx], rules[idx - 1] = rules[idx - 1], rules[idx]
        self.save()
        return True

    def move_down(self, directory: str, rule_name: str) -> bool:
        """
        Move a rule down in the order (higher priority).

        Args:
            directory: Target directory
            rule_name: Rule name to move

        Returns:
            True if moved successfully
        """
        if directory not in self.order:
            return False

        rules = self.order[directory]
        if rule_name not in rules:
            return False

        idx = rules.index(rule_name)
        if idx >= len(rules) - 1:
            return False  # Already at bottom

        rules[idx], rules[idx + 1] = rules[idx + 1], rules[idx]
        self.save()
        return True

    def get_order_value(self, directory: str, rule_name: str) -> int:
        """
        Get the order value for a rule.

        Args:
            directory: Target directory
            rule_name: Rule name

        Returns:
            Order value (position in list + 1), or 1000 if not found
        """
        if directory not in self.order:
            return 1000

        rules = self.order[directory]
        if rule_name in rules:
            return rules.index(rule_name) + 1

        return 1000  # Default for rules not in order.yml

    def get_all_rules(self) -> list[tuple[str, str, int]]:
        """
        Get all rules with their order values.

        Returns:
            List of (directory, rule_name, order) tuples
        """
        result = []
        for directory, rules in self.order.items():
            for idx, rule_name in enumerate(rules):
                result.append((directory, rule_name, idx + 1))
        return result
