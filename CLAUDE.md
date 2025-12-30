# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Clean Code Reviewer (CCR) is an AI-powered CLI tool that reviews code against customizable rules using LLMs. It features a 3-level cascading rule system, MCP server integration for Claude Code/Cursor, and supports multiple LLM providers via LiteLLM.

## Commands

```bash
# Installation
uv tool install clean-code-reviewer    # Install from PyPI

# CLI
ccr --help                        # Show CLI help
ccr review <file>                 # Review a file
ccr mcp                           # Start MCP server
ccr order                         # Interactive rule ordering TUI

# Development Setup
uv sync                           # Install dev dependencies
uv tool install -e .              # Install ccr command (editable)

# Testing & Linting
uv run pytest                     # Run all tests
uv run pytest tests/unit/test_rules_engine.py::test_name  # Single test
uv run ruff check clean_code_reviewer/   # Lint
uv run mypy clean_code_reviewer/         # Type check
```

## Architecture

### Core Components

**RulesEngine** (`core/rules_engine.py`) - Central rule processing:

- Scans `.cleancoderules/` directory for Markdown rules with YAML frontmatter
- Loads ordering from `order.yml`
- Sorts rules by: level (ASC) → order (ASC) → name (ASC)
- `merge_rules()` combines rules into a single string with level headers

**LLMClient** (`core/llm_client.py`) - LiteLLM wrapper:

- Supports sync, async, and streaming operations
- Methods: `review()`, `review_async()`, `review_stream()`, `review_stream_async()`

**PromptBuilder** (`core/prompt_builder.py`) - Constructs LLM prompts:

- `build_review_prompt()` for single files
- `build_multi_file_prompt()` for multiple files
- Auto-detects language from file extension

### 3-Level Rule Hierarchy

Rules cascade with higher levels overriding lower levels:

| Level | Location     | Purpose                                |
| ----- | ------------ | -------------------------------------- |
| 1     | `base.md`    | Universal principles (lowest priority) |
| 2     | `community/` | External rules (Google, Airbnb, etc.)  |
| 3     | `team/`      | Team overrides (HIGHEST priority)      |

File path determines level automatically. Rule order within each level is controlled by `order.yml`, not frontmatter.

### Rule File Format

```markdown
---
name: rule-identifier
language: python # optional, null = all languages
tags: [security, style] # optional
---

# Rule Title

Content with guidelines and examples...
```

### Adapters

- **MCP Server** (`adapters/mcp_server.py`) - FastMCP server for Claude Code/Cursor integration
- **CI Runner** (`adapters/ci_runner.py`) - CI/CD integration with GitHub Actions support

### Configuration

Priority: environment variables > `.cleancoderules/config.yaml` > defaults

Key env vars: `CCR_MODEL`, `CCR_TEMPERATURE`, `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`

## Code Patterns

- All file operations use `Path` objects via `utils/file_ops.py`
- Pydantic models for data validation (`Settings`, `Rule` dataclass)
- Type hints throughout; strict mypy enabled
- Async tests use `pytest-asyncio` with `asyncio_mode = "auto"`
