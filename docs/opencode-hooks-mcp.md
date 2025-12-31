# OpenCode Hooks and MCP Configuration

OpenCode is an open-source AI coding agent (100% open source, MIT licensed) available as a terminal-based TUI, desktop app, or IDE extension. It's provider-agnostic, supporting Claude, OpenAI, Google, and local models.

> **Note**: There were two projects named "opencode". The original `opencode-ai/opencode` (Go-based, Bubble Tea TUI) is now archived and moved to [Crush](https://github.com/charmbracelet/crush). The active project is `sst/opencode` (TypeScript-based) documented here.

## Hooks System (via Plugins)

Unlike Claude Code's shell script-based hooks, OpenCode uses a **plugin-based hook system** with JavaScript/TypeScript modules. This provides more flexibility with 30+ event types compared to Claude Code's 4 hook events.

### Plugin Locations

Plugins are loaded from two directories:

| Location | Scope |
|----------|-------|
| `~/.config/opencode/plugin/` | Global (all projects) |
| `.opencode/plugin/` | Project-specific |

Load order: Global config → Project config → Global plugins → Project plugins

### Plugin Structure

A plugin exports an async function that receives a context object and returns hooks:

```javascript
// .opencode/plugin/my-plugin.js
export const MyPlugin = async ({ project, client, $, directory, worktree }) => {
  return {
    event: async ({ event }) => {
      if (event.type === "session.idle") {
        await $`say "Session is now idle"`
      }
    }
  }
}
```

**Context parameters:**
- `project` - Current project info
- `client` - OpenCode SDK client for AI interaction
- `$` - Bun's shell API for command execution
- `directory` - Working directory path
- `worktree` - Git worktree path

### Available Events

OpenCode supports 27+ plugin events across multiple categories:

| Category | Events |
|----------|--------|
| **Command** | `command.executed` |
| **File** | `file.edited`, `file.watcher.updated` |
| **Installation** | `installation.updated` |
| **LSP** | `lsp.client.diagnostics`, `lsp.updated` |
| **Message** | `message.part.removed`, `message.part.updated`, `message.removed`, `message.updated` |
| **Permission** | `permission.replied`, `permission.updated` |
| **Server** | `server.connected` |
| **Session** | `session.created`, `session.compacted`, `session.deleted`, `session.diff`, `session.error`, `session.idle`, `session.status`, `session.updated` |
| **Todo** | `todo.updated` |
| **Tool** | `tool.execute.before`, `tool.execute.after` |
| **TUI** | `tui.prompt.append`, `tui.command.execute`, `tui.toast.show` |

**Experimental**: `experimental.session.compacting` - fires before LLM generates continuation summary

### Plugin Examples

#### Notification on Session Idle

```typescript
// .opencode/plugin/notification.ts
export const NotificationPlugin = async ({ $ }) => {
  return {
    event: async ({ event }) => {
      if (event.type === "session.idle") {
        await $`osascript -e 'display notification "OpenCode task completed" with title "OpenCode"'`
      }
    }
  }
}
```

#### Tool Execution Logging

```javascript
// .opencode/plugin/audit.js
export const AuditPlugin = async ({ $ }) => {
  return {
    event: async ({ event }) => {
      if (event.type === "tool.execute.before") {
        console.log(`Tool executing: ${event.tool}`)
      }
      if (event.type === "tool.execute.after") {
        console.log(`Tool completed: ${event.tool}`)
      }
    }
  }
}
```

### Plugin Dependencies

Add a `package.json` to `.opencode/` to use external npm packages. OpenCode runs `bun install` automatically at startup.

```json
{
  "dependencies": {
    "execa": "^8.0.0"
  }
}
```

## MCP Server Configuration

OpenCode supports both local and remote MCP (Model Context Protocol) servers for extending tool capabilities.

### Configuration Location

MCP servers are defined in `opencode.json` under the `mcp` key:

```json
{
  "$schema": "https://opencode.ai/config.json",
  "mcp": {
    "server-name": {
      "type": "local",
      "enabled": true
    }
  }
}
```

### Config File Locations (Priority Order)

1. **Global**: `~/.config/opencode/opencode.json`
2. **Project**: `opencode.json` in project root (traverses up to nearest Git directory)
3. **Custom path**: Set via `OPENCODE_CONFIG` environment variable

### Local MCP Servers

Local servers run as child processes:

```json
{
  "mcp": {
    "filesystem": {
      "type": "local",
      "command": ["npx", "-y", "@modelcontextprotocol/server-filesystem", "/path/to/dir"],
      "environment": {
        "MY_VAR": "value"
      },
      "timeout": 5000
    }
  }
}
```

**Options:**
- `command` (required) - Array of command and arguments
- `environment` - Environment variables for the process
- `timeout` - Timeout in milliseconds

### Remote MCP Servers

Remote servers are accessed via HTTP:

```json
{
  "mcp": {
    "my-api": {
      "type": "remote",
      "url": "https://mcp-server.example.com",
      "headers": {
        "Authorization": "Bearer {env:API_KEY}"
      }
    }
  }
}
```

### OAuth Authentication

OpenCode provides three OAuth approaches:

**1. Automatic** (default) - OpenCode detects 401 responses and initiates OAuth flow automatically

**2. Pre-registered credentials:**

```json
{
  "mcp": {
    "my-oauth-server": {
      "type": "remote",
      "url": "https://mcp.example.com",
      "oauth": {
        "clientId": "{env:CLIENT_ID}",
        "clientSecret": "{env:CLIENT_SECRET}",
        "scope": "tools:read tools:execute"
      }
    }
  }
}
```

**3. API Keys** (disable OAuth):

```json
{
  "mcp": {
    "my-server": {
      "type": "remote",
      "url": "https://api.example.com",
      "oauth": false,
      "headers": {
        "X-API-Key": "{env:API_KEY}"
      }
    }
  }
}
```

### MCP CLI Commands

```bash
# Add MCP server interactively
opencode mcp add

# List all configured MCP servers
opencode mcp list
opencode mcp ls

# Authenticate with OAuth-enabled server
opencode mcp auth [server-name]
opencode mcp auth list

# Remove stored credentials
opencode mcp logout [server-name]

# Debug MCP server connection
opencode mcp debug <server-name>
```

Auth tokens are stored in `~/.local/share/opencode/mcp-auth.json`

### Tool Management

Enable/disable MCP tools globally or per-agent using glob patterns:

```json
{
  "tools": {
    "my-mcp*": false
  },
  "agent": {
    "my-agent": {
      "tools": {
        "my-mcp*": true
      }
    }
  }
}
```

Glob syntax: `*` (zero or more characters), `?` (exactly one character)

### Example MCP Configurations

**Sentry (OAuth):**
```json
{
  "mcp": {
    "sentry": {
      "type": "remote",
      "url": "https://mcp.sentry.dev/mcp"
    }
  }
}
```

**Context7 (documentation search):**
```json
{
  "mcp": {
    "context7": {
      "type": "remote",
      "url": "https://mcp.context7.com",
      "headers": {
        "Authorization": "Bearer {env:CONTEXT7_API_KEY}"
      }
    }
  }
}
```

**Grep.app (code search):**
```json
{
  "mcp": {
    "grep": {
      "type": "remote",
      "url": "https://mcp.grep.app"
    }
  }
}
```

## Variable Substitution

OpenCode supports variable substitution in config files:

- **Environment variables**: `{env:VARIABLE_NAME}`
- **File contents**: `{file:path/to/file}` (supports relative, absolute, and `~` paths)

## Comparison with Claude Code

| Feature | OpenCode | Claude Code |
|---------|----------|-------------|
| Hook System | Plugin-based (JS/TS modules) | Shell script-based |
| Event Types | 27+ events | 4 events |
| Configuration | JSON/JSONC | JSON |
| MCP Support | Local + Remote + OAuth | Local (stdio) |
| MCP CLI | `opencode mcp add/list/auth` | Manual config |

## CCR Integration

### Via Plugin (Recommended)

Create a plugin that runs CCR after file edits:

```javascript
// .opencode/plugin/ccr-review.js
import { execSync } from 'child_process'

export const CCRReviewPlugin = async ({ project }) => {
  return {
    event: async ({ event }) => {
      if (event.type === "file.edited" && event.path) {
        try {
          execSync(`ccr review "${event.path}"`, {
            cwd: project.path,
            stdio: 'inherit'
          })
        } catch (e) {
          // Review failed, continue anyway
        }
      }
    }
  }
}
```

### Via MCP Server

Configure CCR as an MCP server in `opencode.json`:

```json
{
  "mcp": {
    "ccr": {
      "type": "local",
      "command": ["ccr", "mcp"]
    }
  }
}
```

## Plugin Collection: oh-my-opencode

[oh-my-opencode](https://github.com/code-yeongyu/oh-my-opencode) is a comprehensive plugin providing 25+ hooks including:

- Todo continuation enforcement
- Context window monitoring
- Session recovery and notification
- Output truncation (grep, tools)
- Thinking mode auto-detection
- Preemptive session compaction
- Directory-based agent injection
- Rules injection via glob patterns

Installation:
```bash
bunx oh-my-opencode install --no-tui
```

## References

- [OpenCode Documentation](https://opencode.ai/docs/)
- [OpenCode GitHub (sst/opencode)](https://github.com/sst/opencode)
- [MCP Servers Documentation](https://opencode.ai/docs/mcp-servers/)
- [Plugins Documentation](https://opencode.ai/docs/plugins/)
- [CLI Reference](https://opencode.ai/docs/cli/)
- [oh-my-opencode Plugin](https://github.com/code-yeongyu/oh-my-opencode)
