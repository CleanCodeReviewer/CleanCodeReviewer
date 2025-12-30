"""Pytest configuration and fixtures."""

from __future__ import annotations

from pathlib import Path
from typing import Generator

import pytest


@pytest.fixture
def temp_rules_dir(tmp_path: Path) -> Path:
    """Create a temporary rules directory."""
    rules_dir = tmp_path / ".cleancoderules"
    rules_dir.mkdir()
    return rules_dir


@pytest.fixture
def sample_rule_content() -> str:
    """Return sample rule content."""
    return """---
name: test-rule
language: python
tags: [test, style]
---

# Test Rule

This is a test rule for Python code.

## Guidelines

- Write clear code
- Use meaningful names
"""


@pytest.fixture
def sample_python_code() -> str:
    """Return sample Python code for testing."""
    return '''
def calculate_sum(a, b):
    """Calculate sum of two numbers."""
    return a + b


class Calculator:
    def __init__(self):
        self.history = []

    def add(self, x, y):
        result = x + y
        self.history.append(result)
        return result
'''


@pytest.fixture
def rules_dir_with_rules(temp_rules_dir: Path, sample_rule_content: str) -> Path:
    """Create a rules directory with sample rules."""
    # Create config
    config_content = """model: gpt-4
temperature: 0.3
max_tokens: 2000
"""
    (temp_rules_dir / "config.yaml").write_text(config_content)

    # Create sample rule
    (temp_rules_dir / "test-rule.md").write_text(sample_rule_content)

    # Create another rule
    another_rule = """---
name: security-rule
tags: [security]
---

# Security Guidelines

- Never log sensitive data
- Validate all inputs
"""
    (temp_rules_dir / "security.md").write_text(another_rule)

    return temp_rules_dir


@pytest.fixture
def mock_llm_response() -> dict:
    """Return a mock LLM response."""
    return {
        "choices": [
            {
                "message": {
                    "content": "The code looks good. No major issues found."
                },
                "finish_reason": "stop"
            }
        ],
        "usage": {
            "prompt_tokens": 100,
            "completion_tokens": 50,
            "total_tokens": 150
        }
    }
