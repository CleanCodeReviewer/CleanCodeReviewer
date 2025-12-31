# Trae IDE

Trae (The Real AI Engineer) is an AI-powered code editor developed by ByteDance, built on VS Code.

## Hooks Support

**Trae IDE does NOT have a hooks system** like Claude Code or Cursor as of December 2025.

Instead, Trae uses a rules-based system for AI behavior customization.

## Configuration Structure

| Item           | Location                           |
| -------------- | ---------------------------------- |
| Project rules  | `.trae/rules/project_rules.md`     |
| Personal rules | `user_rules.md` (in user settings) |
| Ignore file    | `.trae/.ignore`                    |

## AI Rules (Trae Rules)

Trae Rules are Markdown files that define how the AI should behave. They are declarative (tell AI what to follow) rather than event-driven (trigger scripts on file edits).

### Personal Rules

- Stored in user settings as `user_rules.md`
- Apply across all projects
- Examples: language style, OS preferences, response depth

### Project Rules

- Stored in `.trae/rules/project_rules.md`
- Apply only to the specific project
- Examples: code style, framework constraints, API limitations
- Project rules override conflicting personal rules

## Creating Rules

1. Click Settings icon in AI dialog
2. Select "Rules"
3. Click `+ Create project_rules.md` (or `user_rules.md`)
4. System auto-creates `.trae/rules/` folder
5. Enter rules in natural language Markdown
6. Save file

## Other Features

- **MCP Support**: Model Context Protocol for external tool integration
- **Custom Agents**: Specialized AI agents for specific workflows
- **File Indexing Control**: `.trae/.ignore` file to exclude files from AI awareness

## CCR Integration Status

**Not supported** - Trae lacks hooks/events system required for automatic code review on file edits.

There is an [open GitHub issue](https://github.com/Trae-AI/Trae/issues/42) requesting per-project settings configuration, which may eventually lead to hooks support.

## Detection (For Future Reference)

If hooks support is added, detection would check:

**Project-level:**

- `.trae/` directory
- `.trae/rules/` directory

**Global installation:**

- macOS: `/Applications/Trae.app`
- Windows: `%LOCALAPPDATA%/Programs/trae/`
- Linux: `trae` command in PATH

## References

- [Trae IDE Official Site](https://www.trae.ai/)
- [Trae Documentation](https://docs.trae.ai/)
