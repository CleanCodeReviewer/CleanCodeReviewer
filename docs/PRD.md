# Clean Code Reviewer - Product Requirements Document

## Overview

**Product Name:** Clean Code Reviewer (CCR)
**Domain:** CleanCodeReviewer.com
**Version:** 1.0
**Author:** Yumin Gui
**Last Updated:** 2025-12-29

---

## Executive Summary

Clean Code Reviewer is an AI-powered code review tool that enforces customizable coding standards through a cascading rule system. It provides:

- **CLI** for direct usage and CI/CD integration
- **MCP Server** for integration with any MCP-compatible client (Claude Code, Cursor, etc.)
- **Multi-LLM Support** via LiteLLM (OpenAI, Anthropic, Ollama, and more)

All powered by Markdown-defined rules that cascade with clear override priority.

**Core Value Proposition:**

> "Code Quality Guardian for the Vibe Coding Era"

---

## Problem Statement

### Current Pain Points

1. **Rule Knowledge Silos**: Coding standards exist in Wiki pages nobody reads, or only in Senior developers' heads
2. **Inconsistent Reviews**: Different reviewers apply different standards
3. **Senior Dev Bottleneck**: Tech leads spend excessive time reviewing basic issues (naming, function length)
4. **Linter Limitations**: Traditional linters only catch syntax issues, not semantic problems like "this variable name is meaningless" or "this function does too many things"
5. **Configuration Hell**: Existing tools require complex XML/YAML configs that developers hate

### Solution

A "Rules as Markdown" approach where:

- Rules are version-controlled alongside code
- Rules cascade (General → Language → Team) with clear override priority
- LLM understands intent, not just syntax
- Zero-config friction: just drop `.md` files in a folder

---

## Target Users

| Persona              | Need                                                                |
| -------------------- | ------------------------------------------------------------------- |
| **Tech Lead**        | Encode team standards once, have them enforced automatically        |
| **Senior Developer** | Stop reviewing basic issues, focus on architecture                  |
| **Junior Developer** | Learn best practices through automated feedback before human review |
| **DevOps Engineer**  | Integrate quality gates into CI/CD pipelines                        |

---

## Core Features

### 1. Cascading Rule System

Rules are organized in three priority levels:

```
Level 1: General Clean Code Principles (Base)
    ↓ can be overridden by
Level 2: Language-Specific Rules (e.g., PEP8, Go Effective)
    ↓ can be overridden by
Level 3: Team/Project Custom Rules (Highest Priority)
```

**Conflict Resolution Rule:**

> If a Team Rule conflicts with General or Language rules, **OBEY THE TEAM RULE**.

**Example:**

- General says: "Keep functions under 20 lines"
- Team says: "Functions must include detailed logging headers (allow up to 40 lines)"
- Result: 40-line functions with logging headers are acceptable

### 2. Rule Storage Structure

```
project-root/
├── .cleancoderules/
│   ├── config.yaml            # Configuration
│   ├── base.yml               # Level 1 - Base principles
│   ├── order.yml              # Rule ordering within levels
│   ├── community/             # Level 2 - External/community rules
│   │   ├── google/
│   │   │   └── python.yml
│   │   └── airbnb/
│   │       └── javascript.yml
│   └── team/                  # Level 3 - Team rules (HIGHEST)
│       ├── security.yml
│       └── naming.yml
│
└── CLAUDE.md                  # Auto-trigger instructions
```

**Hierarchy:**

- `base.yml` → Level 1 (base principles)
- `<namespace>/*.yml` → Level 2 (style guides)
- `team/*.yml` → Level 3 (team overrides, highest priority)

**Remote Rules Repository (https://github.com/CleanCodeReviewer/Rules):**

```
Rules/                         # Separate GitHub repository
├── base.yml                   # Base principles (downloaded to base.yml)
├── google/
│   ├── python.md              # Google Python Style
│   ├── go.md
│   └── cpp.md
└── airbnb/
    ├── javascript.md
    └── react.md
```

Rules are discovered via GitHub API (no index file needed).

**Key Design Decision:** CCR does NOT bundle rules. All rules are either:

- Created by users in `.cleancoderules/` (Team rules - Level 3)
- Downloaded from the remote repository via `ccr add <namespace>/<rule>`

### 3. Rule Format

Rules are Markdown files with YAML frontmatter:

````markdown
---
name: google-python-naming
level: 2 # 1=Base, 2=Namespace, 3=Team (usually inferred)
language: python
order: 100 # Higher = loaded later = overrides earlier
tags: [naming, style]
---

# Python Naming Conventions

## Variables

- Use `snake_case` for variables and functions
- Use `UPPER_CASE` for constants
- Use `PascalCase` for classes

## Bad Examples

\```python
userName = "John" # Wrong: camelCase
\```
````

### 4. CLI Commands

| Command                    | Description                                           |
| -------------------------- | ----------------------------------------------------- |
| `ccr init`                 | Initialize `.cleancoderules/` directory with defaults |
| `ccr add <namespace/rule>` | Download rule (e.g., `ccr add google/python`)         |
| `ccr remove <rule>`        | Remove an installed rule                              |
| `ccr list`                 | List installed rules with priority info               |
| `ccr list --remote`        | List available rules from remote repository           |
| `ccr review <files>`       | Review code files against rules                       |
| `ccr mcp`                  | Start MCP server for IDE/agent integration            |
| `ccr ci`                   | Run review in CI mode (exit codes for pass/fail)      |
| `ccr config`               | Show effective configuration                          |

### 5. MCP Server Tools

When running as MCP server, exposes these tools to MCP clients:

| Tool                                           | Description                                |
| ---------------------------------------------- | ------------------------------------------ |
| `review_code(code, file_path, language)`       | Review code snippet against cascaded rules |
| `review_file(file_path)`                       | Review a file                              |
| `get_cascading_rules(file_path, project_root)` | Get merged rules with priority headers     |
| `list_rules(language, level)`                  | List applicable rules                      |
| `get_rule(name)`                               | Get specific rule content                  |

### 6. Auto-Review via CLAUDE.md

When `CLAUDE.md` exists in project root, MCP-compatible AI agents (Claude Code, Cursor, etc.) can automatically trigger review:

```markdown
# Project Guidelines

## Automatic Code Review Workflow

**Every time** you generate or modify code, you MUST:

1. Call `get_cascading_rules` tool with the file path
2. Review your code against the returned rules
3. Report any violations, noting which Level rule was violated
4. If Level 3 (Team) rule violated: ERROR (must fix)
5. If Level 1/2 violated: WARNING (suggest fix)
6. If all rules pass: "Code passes all cascaded rules"
```

---

## Technical Architecture

### Component Diagram

```
┌─────────────────────────────────────────────────────────────┐
│              MCP Client (Claude Code, Cursor, etc.)          │
│                    or CLI / CI Pipeline                      │
└─────────────────────────┬───────────────────────────────────┘
                          │ MCP Protocol
                          ▼
┌─────────────────────────────────────────────────────────────┐
│                    CCR MCP Server                            │
│  ┌─────────────┐  ┌──────────────┐  ┌────────────────────┐  │
│  │ Tool:       │  │ Tool:        │  │ Tool:              │  │
│  │ review_code │  │ list_rules   │  │ get_cascading_rules│  │
│  └──────┬──────┘  └──────┬───────┘  └─────────┬──────────┘  │
│         │                │                    │              │
│         └────────────────┼────────────────────┘              │
│                          ▼                                   │
│  ┌───────────────────────────────────────────────────────┐  │
│  │                   Rules Engine                         │  │
│  │  - Load rules from .cleancoderules/                    │  │
│  │  - Infer level from path (namespace → L2, root → L3)   │  │
│  │  - Merge with cascade priority                         │  │
│  └───────────────────────────────────────────────────────┘  │
│                          │                                   │
│                          ▼                                   │
│  ┌───────────────────────────────────────────────────────┐  │
│  │                  Prompt Builder                        │  │
│  │  - Format rules with Level headers                     │  │
│  │  - Add conflict resolution instructions                │  │
│  │  - Combine with code context                           │  │
│  └───────────────────────────────────────────────────────┘  │
│                          │                                   │
│                          ▼                                   │
│  ┌───────────────────────────────────────────────────────┐  │
│  │                   LLM Client                           │  │
│  │  - LiteLLM wrapper                                     │  │
│  │  - Supports: OpenAI, Anthropic, Ollama                 │  │
│  └───────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

### Package Structure

```
clean_code_reviewer/
├── __init__.py
├── __main__.py
├── cli.py                    # Typer CLI application
│
├── core/
│   ├── rules_engine.py       # Rule loading, parsing, cascading
│   ├── prompt_builder.py     # Build LLM prompts with level headers
│   ├── llm_client.py         # LiteLLM wrapper
│   └── rules_manager.py      # Download rules from remote repository
│
├── adapters/
│   ├── mcp_server.py         # FastMCP server implementation
│   └── ci_runner.py          # CI/CD integration
│
└── utils/
    ├── config.py             # Pydantic settings
    ├── file_ops.py           # Safe file operations
    └── logger.py             # Logging utilities
```

---

## Detailed Requirements

### FR-1: Cascading Rule Engine

**FR-1.1** System SHALL load rules from `.cleancoderules/` directory:

- Downloaded rules (Levels 1 & 2) - via `ccr add`
- User-created project rules (Level 3) - created manually

**FR-1.2** Each rule SHALL have a `level` attribute (1, 2, or 3)

**FR-1.3** Rules SHALL be sorted by: Level (ascending) → Priority (ascending) → Filename (ascending)

**FR-1.4** When merging rules, system SHALL clearly demarcate levels in output:

```
### LEVEL 1: General Clean Code Principles (Base)
[rules...]

### LEVEL 2: Language Specific Rules - Python (Overrides Level 1)
[rules...]

### LEVEL 3: Team Custom Rules (HIGHEST PRIORITY - Overrides All)
[rules...]
```

**FR-1.5** System SHALL include conflict resolution instructions in merged output

### FR-2: Rule Format

**FR-2.1** Rules SHALL be Markdown files with YAML frontmatter

**FR-2.2** Required frontmatter fields:

- `name`: Unique identifier

**FR-2.3** Optional frontmatter fields:

- `level`: 1, 2, or 3 (default: inferred from location)
- `language`: Target language (null = universal)
- `order`: Sort order within level (default: 100, higher = loaded later = overrides)
- `tags`: Categorization tags

**FR-2.4** Filename prefix SHALL influence sort order within same level:

- `00_critical.md` sorts before `10_naming.md`

**FR-2.5** Level inference from file path:

- `.cleancoderules/base.yml` → Level 1 (base principles)
- `.cleancoderules/community/**/*.yml` → Level 2 (community/external rules)
- `.cleancoderules/team/*.yml` → Level 3 (team rules, highest priority)

### FR-3: CLI

**FR-3.1** `ccr init` SHALL:

- Create `.cleancoderules/` with `community/` and `team/` subdirectories
- Generate `config.yaml` with defaults
- Download `base.yml` from remote (or create sample)
- Prompt user to select languages and download to namespace folders
- Create sample `team/example.yml`
- Optionally create/update CLAUDE.md or .cursorrules

**FR-3.2** `ccr add <namespace/rule>` SHALL:

- Validate rule exists at https://github.com/CleanCodeReviewer/Rules
- Download to `.cleancoderules/<namespace>/<rule>.md`
- Level is automatically Level 2 (namespace folder)

**FR-3.3** `ccr review <files>` SHALL:

- Support glob patterns (`src/**/*.py`)
- Output review with rule source attribution
- Exit code 0 = pass, 1 = violations found

**FR-3.4** `ccr list` SHALL show:

- Rule name
- Level (1/2/3)
- Language
- Source file

### FR-4: MCP Server

**FR-4.1** `get_cascading_rules(file_path, project_root)` SHALL:

- Auto-detect language from file extension
- Load applicable rules from all three levels
- Return formatted prompt with level headers and conflict resolution instructions

**FR-4.2** `review_code(code, file_path, language, project_root)` SHALL:

- Build cascading rules prompt
- Submit to LLM
- Return structured review result

**FR-4.3** Server SHALL support `stdio` and `sse` transports for MCP clients

**FR-4.4** Server SHALL auto-detect `project_root` from current working directory if not provided

### FR-5: Configuration

**FR-5.1** Configuration sources (priority order):

1. Environment variables (`CCR_*`)
2. `.cleancoderules/config.yaml`
3. Default values

**FR-5.2** Configurable options:
| Key | Default | Description |
|-----|---------|-------------|
| `model` | `gpt-4` | LLM model identifier |
| `temperature` | `0.3` | LLM temperature |
| `max_tokens` | `2000` | Max response tokens |
| `rules_repo_owner` | `CleanCodeReviewer` | GitHub owner/org for rules |
| `rules_repo_name` | `Rules` | GitHub repository name |

---

## Non-Functional Requirements

### Performance

- **NFR-1**: Rule loading SHALL complete in < 100ms for typical project (< 20 rule files)
- **NFR-2**: MCP server startup SHALL complete in < 2 seconds

### Reliability

- **NFR-3**: System SHALL gracefully handle missing/malformed rule files (log warning, skip file)
- **NFR-4**: System SHALL work offline using previously downloaded rules

### Usability

- **NFR-5**: Zero configuration required for basic usage (`ccr init && ccr review`)
- **NFR-6**: All error messages SHALL include actionable remediation steps

### Compatibility

- **NFR-7**: Python 3.12+ required
- **NFR-8**: Cross-platform: macOS, Linux, Windows

---

## Rules Repository Content Plan

**Repository:** https://github.com/CleanCodeReviewer/Rules

### Phase 1 (MVP)

| Namespace | Rules                                          |
| --------- | ---------------------------------------------- |
| (root)    | `general.md` - Universal clean code principles |
| google    | `python.md`, `go.md`                           |
| airbnb    | `javascript.md`, `react.md`                    |

### Phase 2

| Namespace | Rules                                |
| --------- | ------------------------------------ |
| google    | `cpp.md`, `java.md`, `typescript.md` |
| microsoft | `csharp.md`                          |
| uber      | `go.md`                              |
| django    | `security.md`                        |

### Phase 3 (Community)

- Open contribution model via GitHub PRs to the Rules repository
- Rule quality review process
- Versioned rules (semantic versioning)

---

## Implementation Status

### Completed

- [x] Package structure
- [x] CLI commands (`init`, `add`, `remove`, `list`, `review`, `mcp`, `ci`, `config`)
- [x] MCP server with FastMCP
- [x] LiteLLM integration
- [x] Rules manager (remote download via GitHub API)
- [x] Test suite (65 tests)
- [x] **FR-1.2**: Add `level` field to rule schema
- [x] **FR-1.3**: Implement cascading sort (Level → Order)
- [x] **FR-1.4**: Update prompt builder with Level headers
- [x] **FR-1.5**: Add conflict resolution instructions to prompts
- [x] **FR-2.5**: Implement level inference (`base.yml`=L1, `team/`=L3, else=L2)
- [x] **FR-3.1**: Enhanced `ccr init` with simplified structure, language selection
- [x] **FR-3.2**: `ccr add` downloads to namespace folders

### TODO (v1.0)

- [ ] **FR-3.1**: Generate `CLAUDE.md` template in `ccr init` (optional)
- [ ] **FR-4.1**: Add `get_cascading_rules` MCP tool
- [ ] **FR-4.4**: Auto-detect project root in MCP server
- [ ] Create `base.yml` in Rules repository as Level 1 base rules
- [ ] Create initial rules in https://github.com/CleanCodeReviewer/Rules

---

## Success Metrics

| Metric                 | Target (6 months) |
| ---------------------- | ----------------- |
| GitHub Stars           | 1,000+            |
| PyPI Downloads/month   | 5,000+            |
| Rules Available        | 20+               |
| Community Contributors | 10+               |

---

## Risks & Mitigations

| Risk                 | Impact                          | Mitigation                                       |
| -------------------- | ------------------------------- | ------------------------------------------------ |
| LLM hallucinations   | False positives frustrate users | Prompt engineering; "uncertain" confidence level |
| MCP adoption limited | Small addressable market        | Future: VS Code extension, GitHub Action         |
| Rule quality varies  | Inconsistent experience         | Curated official rules; contribution guidelines  |
| API costs for users  | Adoption friction               | Support Ollama (local); response caching         |

---

## Appendix A: CLAUDE.md Template

```markdown
# Project Guidelines

## Automatic Code Review

**After every code generation or modification**, you MUST:

1. Call the `get_cascading_rules` tool with the file path
2. Review your generated code against the returned rules
3. Report findings using this format:
   - **ERROR** (Level 3 violation): Must fix before proceeding
   - **WARNING** (Level 1/2 violation): Suggest improvement
   - **PASS**: "Code passes all cascaded rules"

## Conflict Resolution

If rules conflict, higher levels override lower levels:

- Level 3 (Team) > Level 2 (Language) > Level 1 (General)

Example: If Team says "allow long functions for logging" but General says "functions < 20 lines", allow the long functions.
```

## Appendix B: Conflict Resolution Prompt Template

```
**CONFLICT RESOLUTION INSTRUCTIONS:**

Rules are organized in 3 levels. Higher levels OVERRIDE lower levels:
- Level 3 (Team Custom) - HIGHEST PRIORITY
- Level 2 (Language Specific)
- Level 1 (General Principles) - BASE

When rules conflict:
1. If Team Rule (L3) allows X but General Rule (L1) forbids X → ALLOW X
2. If Language Rule (L2) requires Y but Team Rule (L3) exempts Y → EXEMPT Y
3. Always cite the specific rule and level when reporting violations

If uncertain whether code violates a rule, do NOT report it as a violation.
```
