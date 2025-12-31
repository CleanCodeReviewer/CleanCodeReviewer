"""FastMCP server for Claude Code integration."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

from clean_code_reviewer.core.rules_engine import RulesEngine
from clean_code_reviewer.utils.logger import get_logger

logger = get_logger(__name__)


def create_mcp_server(
    rules_dir: Path | str | None = None,
    name: str = "clean-code-reviewer",
    host: str = "127.0.0.1",
    port: int = 8000,
) -> FastMCP:
    """
    Create and configure the MCP server.

    Args:
        rules_dir: Directory containing rules
        name: Server name
        host: Host to bind to (for SSE transport)
        port: Port to listen on (for SSE transport)

    Returns:
        Configured FastMCP server instance
    """
    mcp = FastMCP(name, host=host, port=port)

    # Initialize components
    if rules_dir is None:
        rules_dir = Path.cwd() / ".cleancoderules"
    rules_engine = RulesEngine(rules_dir)

    @mcp.tool()
    def list_rules(
        language: str | None = None,
        tags: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        """
        List available coding rules.

        Args:
            language: Filter by programming language
            tags: Filter by tags

        Returns:
            List of rule summaries
        """
        # Reload rules to get latest
        rules_engine.reload()

        rules = rules_engine.get_rules_for_language(language)

        if tags:
            rules = [r for r in rules if any(r.has_tag(t) for t in tags)]

        return [
            {
                "name": rule.name,
                "language": rule.language,
                "tags": rule.tags,
                "level": rule.level,
            }
            for rule in rules
        ]

    @mcp.tool()
    def get_rule(name: str) -> dict[str, Any] | str:
        """
        Get details of a specific rule.

        Args:
            name: Rule name

        Returns:
            Rule details including content
        """
        rule = rules_engine.get_rule_by_name(name)

        if rule is None:
            return f"Rule not found: {name}"

        return {
            "name": rule.name,
            "language": rule.language,
            "tags": rule.tags,
            "level": rule.level,
            "content": rule.content,
            "source_file": str(rule.source_file) if rule.source_file else None,
        }

    @mcp.tool()
    def get_merged_rules(
        language: str | None = None,
        tags: list[str] | None = None,
    ) -> str:
        """
        Get all applicable rules merged into a single document.

        Args:
            language: Filter by programming language
            tags: Filter by tags

        Returns:
            Merged rules content
        """
        return rules_engine.merge_rules(language=language, tags=tags)

    @mcp.resource("rules://list")
    def get_rules_resource() -> str:
        """Get all available rules as a resource."""
        rules = rules_engine.list_rules()
        lines = ["# Available Rules\n"]
        for rule in rules:
            tags_str = f" [{', '.join(rule['tags'])}]" if rule.get("tags") else ""
            lang_str = f" ({rule['language']})" if rule.get("language") else ""
            lines.append(f"- {rule['name']}{lang_str}{tags_str}")
        return "\n".join(lines)

    @mcp.resource("rules://{name}")
    def get_rule_resource(name: str) -> str:
        """Get a specific rule as a resource."""
        rule = rules_engine.get_rule_by_name(name)
        if rule is None:
            return f"Rule not found: {name}"
        return f"# {rule.name}\n\n{rule.content}"

    return mcp


def run_mcp_server(
    rules_dir: Path | str | None = None,
    transport: str = "stdio",
    host: str = "127.0.0.1",
    port: int = 11111,
) -> None:
    """
    Run the MCP server.

    Args:
        rules_dir: Directory containing rules
        transport: Transport type ("stdio" or "sse")
        host: Host to bind to (for SSE transport)
        port: Port to listen on (for SSE transport)
    """
    mcp = create_mcp_server(rules_dir, host=host, port=port)

    logger.info(f"Starting MCP server (transport={transport})")

    if transport == "stdio":
        mcp.run(transport="stdio")
    else:
        logger.info(f"MCP SSE server listening on http://{host}:{port}")
        mcp.run(transport="sse")
