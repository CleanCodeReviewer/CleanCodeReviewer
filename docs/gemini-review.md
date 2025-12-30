# CleanCodeReviewer Codebase Review

## 1. Project Overview

**Clean Code Reviewer (CCR)** is a sophisticated tool designed to enforce coding standards through AI-powered reviews. It bridges the gap between static analysis and human code review by leveraging Large Language Models (LLMs) to understand context and intent.

### Key Features
-   **Multi-Platform Support**: Functions as both a CLI tool and an Model Context Protocol (MCP) server.
-   **Hierarchical Rules System**: Implements a 3-level cascading rule structure (Base -> Community -> Team) to allow flexible overrides.
-   **Model Agnostic**: Uses `litellm` to support OpenAI, Anthropic, Ollama, and others.
-   **Hybrid Rule Formats**: Supports both structured YAML rules (for granular merging) and legacy Markdown rules.

## 2. Architecture Analysis

The codebase adheres to a clean, modular architecture, separating concerns into distinct layers:

### Core Logic (`clean_code_reviewer/core`)
-   **`RulesEngine`**: The heart of the system.
    -   *Strengths*: efficiently handles rule discovery, parsing, and merging. The implementation of `_deep_merge` allows for fine-grained configuration overrides, which is a significant architectural win.
    -   *Design*: Uses a `Rule` dataclass to normalize data from different file formats.
-   **`LLMClient`**: A robust wrapper around `litellm`.
    -   *Features*: Supports sync, async, and streaming patterns. This makes it suitable for both real-time CLI usage and background CI processes.
    -   *Error Handling*: Abstractions here catch low-level API errors, preventing crashes.

### Interfaces
-   **CLI (`clean_code_reviewer/cli.py`)**: Built with `typer`.
    -   Provides a rich user experience using the `rich` library for formatted output (tables, markdown rendering).
    -   Commands like `init`, `add`, and `order` make setup easy.
-   **MCP Server (`adapters/mcp_server.py`)**:
    -   Uses `fastmcp` to expose tools to AI agents (Claude Code, Cursor).
    -   Exposes rules as "resources" (`rules://`), allowing agents to read rules directly as if they were files.

## 3. Detailed Component Review

### `RulesEngine` (`core/rules_engine.py`)
This is the most complex component. It handles the precedence logic:
1.  **Level 1 (Base)**: Universal principles.
2.  **Level 2 (Community)**: Language-specific standards (e.g., Google Python Style).
3.  **Level 3 (Team)**: Project-specific overrides.

**Observation**: The sorting logic (`_rules.sort`) is consistent, using `level`, `order`, and `name` to ensure deterministic rule application. The support for both YAML and Markdown ensures backward compatibility while paving the way for more structured configuration.

### `LLMClient` (`core/llm_client.py`)
The client implementation is solid. It includes:
-   **Streaming Support**: Essential for good UX in CLI tools reviewing large files.
-   **Async Implementation**: Allows for concurrent reviews of multiple files (though the current CLI loop processes sequentially, the lower level supports concurrency).

### `CLI` (`cli.py`)
The CLI is well-structured.
-   **`init` command**: intelligently detects existing configs and "safe writes" files.
-   **`review` command**: The core loop. It builds prompts dynamically based on the file type, ensuring the LLM has the necessary context.

## 4. Code Quality & Patterns

-   **Type Safety**: The project uses strict type hints throughout (`mypy` strict mode enabled in config).
-   **Modern Python**: usage of `pathlib` for file operations and `dataclasses` for data modeling.
-   **Dependencies**: Smart choice of libraries (`typer`, `rich`, `pydantic`, `litellm`) that are industry standards for modern Python CLI tools.

## 5. Improvement Recommendations

While the codebase is high quality, here are potential enhancements:

1.  **Concurrency in CLI**: The `review` command iterates files sequentially. Using `asyncio.gather` with the `review_async` method could significantly speed up multi-file reviews.
2.  **Caching**: There is no apparent caching of LLM responses. Adding a hash-based cache for file content + rule set could save API costs on repeated runs.
3.  **Token Counting**: While `ReviewResult` tracks usage, implementing a pre-check or budget limit could prevent accidental overspending.
4.  **Testing**:
    -   The `tests` directory exists, but ensuring high coverage for the `RulesEngine` merge logic is critical given its complexity.

## 6. Conclusion

CleanCodeReviewer is a robust, well-engineered tool. It solves a real problem (enforcing code quality beyond linting) with a flexible and scalable architecture. The support for MCP makes it future-proof for the upcoming era of agentic coding.
