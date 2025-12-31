# Clean Code Reviewer (CCR)

**Code Quality Guardian for the Vibe Coding Era**

- AI-powered MCP server acting as an immediate quality gate for AI-generated code

- A CLI tool for reviewing code against customizable clean code rules using LLMs.

- Supports integration with any MCP-compatible client (Claude Code, Cursor, etc.) and multiple LLM providers via LiteLLM.

## Disclaimer

CleanCodeReviewer is an independent, open-source tool inspired by widely accepted software engineering principles. It is not affiliated with, endorsed by, or connected to Robert C. Martin or the authors of the book 'Clean Code'.

## Features

- **Rule-based Code Review**: Define custom coding standards in yml files
- **LLM-powered Analysis**: Uses LiteLLM to support multiple LLM providers (OpenAI, Anthropic, Ollama, etc.)
- **MCP Integration**: Works with any MCP-compatible client (Claude Code, Cursor, etc.)
- **Community Rules**: Download shared rules or create your own
- **CI/CD Ready**: Can be integrated into your CI pipeline

## Installation

```bash
# Quick install (auto-detects uv/pipx)
curl -sSL https://raw.githubusercontent.com/CleanCodeReviewer/CleanCodeReviewer/main/install.sh | bash

# Using uv (recommended)
uv tool install clean-code-reviewer

# Using pipx
pipx install clean-code-reviewer

# macOS (Homebrew) - coming soon
brew tap CleanCodeReviewer/tap && brew install ccr

# Windows (Scoop) - coming soon
scoop bucket add ccr https://github.com/CleanCodeReviewer/scoop-bucket && scoop install ccr

# From source
git clone https://github.com/CleanCodeReviewer/CleanCodeReviewer.git
cd clean-code-reviewer
uv sync
```

## Quick Start

### 1. Initialize in your project

```bash
ccr init
```

This creates a `.cleancoderules/` directory with the cascading rule structure:

```
.cleancoderules/
├── config.yaml          # Configuration
├── base.md              # Level 1 - Base principles
├── google/              # Level 2 - Namespace rules
│   └── python.md
└── teams/               # Level 3 - Team rules (HIGHEST PRIORITY)
    └── example.md
```

**Rule Hierarchy:**

- `base.md` → Level 1 (base principles, loaded first)
- `<namespace>/*.md` → Level 2 (style guides, e.g., google/, airbnb/)
- `teams/*.md` → Level 3 (team overrides, highest priority)

### 2. Add rules

```bash
# Add language-specific rules (downloaded to lang/)
ccr add google/python
ccr add airbnb/javascript

# Create team rules in .cleancoderules/team/
```

### 3. Review code

```bash
# Review a specific file
ccr review src/main.py

# Review multiple files
ccr review src/*.py

# Review with specific rules
ccr review --rules python,security src/
```

## Configuration

### Environment Variables

```bash
# LLM Provider Configuration
export OPENAI_API_KEY="your-api-key"
# Or for other providers:
export ANTHROPIC_API_KEY="your-api-key"
export OLLAMA_HOST="http://localhost:11434"

# Optional: Default model
export CCR_MODEL="gpt-4"
```

### Local Configuration

Create a `.cleancoderules/config.yaml`:

```yaml
model: gpt-4
temperature: 0.3
max_tokens: 2000
rules_priority:
  - security
  - style
  - performance
```

## Rules Format

Rules are written in Markdown with YAML frontmatter:

````markdown
---
name: python-naming
order: 100
language: python
tags: [style, naming]
---

# Python Naming Conventions

## Variables

- Use snake_case for variables and functions
- Use UPPER_CASE for constants
- Use PascalCase for classes

## Examples

### Good

```python
user_name = "John"
MAX_RETRIES = 3
class UserAccount:
    pass
```
````

### Bad

```python
userName = "John"  # camelCase
maxRetries = 3     # should be constant
class user_account:  # should be PascalCase
    pass
```

````

## MCP Server (Claude Code Integration)

To use with Claude Code, add to your MCP configuration:

```json
{
  "mcpServers": {
    "clean-code-reviewer": {
      "command": "ccr",
      "args": ["mcp"]
    }
  }
}
````

Then in Claude Code, you can use:

- `review_code` - Review code against rules
- `list_rules` - List available rules
- `get_rule` - Get details of a specific rule

## CLI Reference

```bash
ccr --help              # Show help
ccr init                # Initialize rules directory
ccr add <rule>          # Add rule (e.g., google/python)
ccr remove <rule>       # Remove a rule
ccr list                # List installed rules
ccr review <files>      # Review code files
ccr mcp                 # Start MCP server
ccr config              # Show/edit configuration
ccr hooks install       # Install AI assistant hooks
ccr hooks status        # Show hook status
ccr update              # Update rules, agent files, and hooks
```

### `ccr review` Options

| Option      | Short | Description                                 |
|-------------|-------|---------------------------------------------|
| `FILES`     |       | Files or directories to review              |
| `--pattern` | `-p`  | Glob patterns (e.g., `**/*.py`)             |
| `--changed` | `-c`  | Git changed files only                      |
| `--staged`  |       | Git staged files only                       |
| `--base`    | `-b`  | Git base ref (default: HEAD)                |
| `--compare` |       | Git compare ref                             |
| `--reviewer`| `-r`  | Backend: litellm, claudecode, gemini, codex |
| `--rules-dir`| `-d` | Rules directory                             |
| `--model`   | `-m`  | LLM model (for litellm)                     |
| `--tags`    | `-t`  | Rule tags (comma-separated)                 |
| `--output`  | `-o`  | Output file                                 |
| `--stream`  | `-s`  | Stream output                               |

### `ccr hooks` - AI Assistant Integration

CCR can automatically review code when AI coding assistants (Claude Code, Gemini CLI) edit files:

```bash
ccr hooks install              # Install for detected CLIs
ccr hooks install -t claude    # Claude Code only
ccr hooks install -t gemini    # Gemini CLI only
ccr hooks install -g           # Install globally
ccr hooks uninstall            # Remove hooks
ccr hooks status               # Show installation status
```

**How it works:**
- **Before edit**: Shows rules to the AI to follow during coding
- **After edit**: Reviews the code and suggests fixes

## Development

```bash
# Install dev dependencies
uv sync

# Run tests
uv run pytest

# Run linting
uv run ruff check src/
uv run mypy src/
```

## License

MIT License - see [LICENSE](LICENSE) for details.
