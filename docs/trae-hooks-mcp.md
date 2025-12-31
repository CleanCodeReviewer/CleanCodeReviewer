# Trae IDE Hooks and MCP Configuration

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

- **Custom Agents**: Specialized AI agents for specific workflows
- **File Indexing Control**: `.trae/.ignore` file to exclude files from AI awareness

---

## MCP Configuration

Trae v1.3.0+ supports MCP (Model Context Protocol) for connecting to external tools, databases, and APIs.

### Setup Steps

1. Click Settings icon in AI dialog
2. Enter "AI Management" settings
3. Select "Agents" → "MCP" option
4. Choose "Add Manually"
5. Enter JSON configuration

### Configuration Location

| Scope | Location |
|-------|----------|
| Project-specific | `.mcp.json` in project root |

### Configuration Format

```json
{
  "mcpServers": {
    "server-name": {
      "command": "executable",
      "args": ["arg1", "arg2"],
      "env": {
        "API_KEY": "value"
      }
    }
  }
}
```

### Transport Types

| Transport | Configuration |
|-----------|---------------|
| `stdio` | `command` + `args` (local) |
| `SSE` | `url` field (remote) |

### Local Server Example

```json
{
  "mcpServers": {
    "my-tool": {
      "command": "npx",
      "args": ["-y", "@example/mcp-server"],
      "env": {
        "API_KEY": "your-key"
      }
    }
  }
}
```

### Remote Server Example

```json
{
  "mcpServers": {
    "my-api": {
      "url": "https://api.example.com/mcp?key=your-api-key"
    }
  }
}
```

### CCR MCP Integration

Configure CCR as an MCP server in `.mcp.json`:

```json
{
  "mcpServers": {
    "clean-code-reviewer": {
      "command": "ccr",
      "args": ["mcp"]
    }
  }
}
```

After configuration, switch to "Builder with MCP" agent to use CCR for on-demand code reviews.

### MCP Marketplace

Trae includes a built-in MCP Marketplace UI for one-click installation of official MCP servers. Access it via Settings → Agents → MCP.

### Troubleshooting

- Check status indicators next to each server (green = connected)
- Ensure `npx` command is available in PATH
- Restart Trae after configuration changes
- Verify JSON format is correct

---

## CCR Integration Status

**Hooks: Not supported** - Trae lacks hooks/events system required for automatic code review on file edits.

**MCP: Supported** - Use CCR via MCP for on-demand reviews. Run `ccr init` to auto-configure.

There is an [open GitHub issue](https://github.com/Trae-AI/Trae/issues/42) requesting per-project settings configuration, which may eventually lead to hooks support.

## Detection

CCR detects Trae by checking:

**Project-level:**

- `.trae/` directory

**Global installation:**

- macOS: `/Applications/Trae.app`
- Windows: `%LOCALAPPDATA%/Programs/trae/`
- Linux: `trae` command in PATH

## References

- [Trae IDE Official Site](https://www.trae.ai/)
- [Trae Documentation](https://docs.trae.ai/)
- [Trae MCP Documentation](https://docs.trae.ai/ide/model-context-protocol)
