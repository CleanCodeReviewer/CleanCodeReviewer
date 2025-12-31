# Cursor Hooks

Cursor hooks enable developers to observe, control, and extend Cursor's agent loop using custom scripts. They are spawned processes that communicate via JSON over stdio, running before or after defined stages of the agent workflow.

## Use Cases

- Running code formatters after edits
- Implementing analytics for tracked events
- Scanning for sensitive data or secrets
- Gating risky operations like database writes

## Agent vs Tab Hooks

Cursor distinguishes between two operation modes:

**Agent (Cmd+K/Agent Chat)** supports:
- Shell execution hooks (before/after)
- MCP tool execution hooks (before/after)
- File access and edit hooks
- Prompt submission validation
- Agent completion and response tracking

**Tab (inline completions)** uses specialized hooks:
- File read interception
- Post-edit processing

## Available Hook Events

| Hook | Purpose |
|------|---------|
| `beforeShellExecution` | Control terminal commands before execution |
| `afterShellExecution` | Audit terminal commands after execution |
| `beforeMCPExecution` | Monitor MCP tool usage before execution |
| `afterMCPExecution` | Monitor MCP tool usage after execution |
| `afterFileEdit` | Process agent-written code changes |
| `beforeSubmitPrompt` | Validate user prompts before submission |
| `beforeTabFileRead` | Tab-specific file read interception |
| `afterTabFileEdit` | Tab-specific post-edit processing |
| `stop` | Triggers on agent loop completion |
| `afterAgentResponse` | Observe agent outputs |
| `afterAgentThought` | Observe agent reasoning |

## Configuration

Hooks are defined in `hooks.json` files:

```json
{
  "version": 1,
  "hooks": {
    "hookName": [{ "command": "./path/to/script.sh" }]
  }
}
```

### Configuration Locations (Priority Order)

1. **Enterprise-managed** (highest priority)
   - macOS: `/Library/Application Support/Cursor/hooks.json`
   - Linux/WSL: `/etc/cursor/hooks.json`
   - Windows: `C:\ProgramData\Cursor\hooks.json`

2. **Project-specific** (checked into version control)
   - `<project-root>/.cursor/hooks.json`
   - Runs in trusted workspaces only

3. **User-specific** (lowest priority)
   - `~/.cursor/hooks.json`

## Hook Input/Output Protocol

### Input

All hooks receive a JSON payload via stdin including:

```json
{
  "conversation_id": "stable-conversation-id",
  "generation_id": "changes-with-each-message",
  "model": "configured-model-name",
  "hook_event_name": "afterFileEdit",
  "cursor_version": "0.x.x",
  "workspace_roots": ["/path/to/project"],
  "user_email": "user@example.com"
}
```

### Output

Permission-based hooks return:

```json
{
  "permission": "allow",
  "user_message": "Text shown to user",
  "agent_message": "Guidance for the agent"
}
```

Permission values: `"allow"` | `"deny"` | `"ask"`

## Examples

### Audit Hook

Log all hook events with timestamps:

```bash
#!/bin/bash
json_input=$(cat)
timestamp=$(date '+%Y-%m-%d %H:%M:%S')
mkdir -p "$(dirname /tmp/agent-audit.log)"
echo "[$timestamp] $json_input" >> /tmp/agent-audit.log
exit 0
```

### Auto-format After Edit

```json
{
  "version": 1,
  "hooks": {
    "afterFileEdit": [{ "command": "./scripts/format.sh" }]
  }
}
```

### Block Sensitive File Access

```bash
#!/bin/bash
json_input=$(cat)
file_path=$(echo "$json_input" | jq -r '.file_path // empty')

if [[ "$file_path" == *".env"* ]] || [[ "$file_path" == *"secrets"* ]]; then
  echo '{"permission": "deny", "user_message": "Blocked access to sensitive file"}'
  exit 0
fi

echo '{"permission": "allow"}'
exit 0
```

## CCR Integration

To integrate Clean Code Reviewer with Cursor hooks, you can create an `afterFileEdit` hook that runs CCR on modified files:

```json
{
  "version": 1,
  "hooks": {
    "afterFileEdit": [{ "command": "./scripts/ccr-review.sh" }]
  }
}
```

Example `ccr-review.sh`:

```bash
#!/bin/bash
json_input=$(cat)
file_path=$(echo "$json_input" | jq -r '.file_path // empty')

if [[ -n "$file_path" ]] && [[ -f "$file_path" ]]; then
  ccr review "$file_path" 2>/dev/null || true
fi

exit 0
```

## Troubleshooting

- Use the **Hooks tab** in Cursor Settings for debugging
- Check the **Hooks output channel** for error messages
- Restart Cursor if hooks don't activate
- Verify script paths are relative to `hooks.json` location

## References

- [Cursor Hooks Documentation](https://cursor.com/docs/agent/hooks)
