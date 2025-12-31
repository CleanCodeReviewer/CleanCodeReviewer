"""CLI application for Clean Code Reviewer."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Annotated, Optional

import typer
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.table import Table

from clean_code_reviewer import __version__
from clean_code_reviewer.adapters.ci_runner import CIRunner
from clean_code_reviewer.adapters.mcp_server import run_mcp_server
from clean_code_reviewer.core.prompt_builder import CodeContext, PromptBuilder
from clean_code_reviewer.core.order_manager import OrderManager
from clean_code_reviewer.core.rules_manager import RulesManager
from clean_code_reviewer.core.rules_engine import RulesEngine
from clean_code_reviewer.utils.config import get_effective_settings
from clean_code_reviewer.utils.detection import (
    get_project_targets,
    is_claude_code_installed,
    is_cursor_installed,
    is_gemini_cli_installed,
)
from clean_code_reviewer.utils.file_ops import ensure_directory, read_file_safe, write_file_safe
from clean_code_reviewer.utils.logger import setup_logging

app = typer.Typer(
    name="ccr",
    help="Clean Code Reviewer - LLM-powered code review against customizable rules",
    add_completion=False,
)

console = Console()


def version_callback(value: bool) -> None:
    """Print version and exit."""
    if value:
        console.print(f"Clean Code Reviewer v{__version__}")
        raise typer.Exit()


@app.callback()
def main(
    _: Annotated[  # noqa: PYL-W0613
        Optional[bool],
        typer.Option(
            "--version",
            "-v",
            help="Show version and exit",
            callback=version_callback,
            is_eager=True,
        ),
    ] = None,
    verbose: Annotated[
        bool,
        typer.Option("--verbose", "-V", help="Enable verbose output"),
    ] = False,
    quiet: Annotated[
        bool,
        typer.Option("--quiet", "-q", help="Suppress non-error output"),
    ] = False,
) -> None:
    """Clean Code Reviewer - LLM-powered code review."""
    log_level = "DEBUG" if verbose else ("ERROR" if quiet else "INFO")
    setup_logging(level=log_level)


def _get_prompt_instructions() -> str:
    """Get the CCR instructions for prompt files."""
    return """## Clean Code Reviewer

This project uses Clean Code Reviewer (CCR) for code quality enforcement.

### Rules
- `.cleancoderules/team/` - Team rules (highest priority)
- `.cleancoderules/community/` - Community rules
- `.cleancoderules/base.yml` - Base principles

### Manual Review
```bash
ccr review <file>              # Review specific file
ccr review src/                # Review directory
ccr review -p "**/*.py"        # Review by pattern
ccr review --changed           # Review git changes
ccr review --staged            # Review staged only
```
"""


def _install_hooks_for_init(path: Path, target: str) -> None:
    """Install hooks for a specific target during init."""
    import json

    # Get settings path based on target
    if target == "gemini":
        settings_path = path / ".gemini" / "settings.json"
    else:  # claude
        settings_path = path / ".claude" / "settings.json"

    # Load existing settings
    settings: dict = {}
    if settings_path.exists():
        content = read_file_safe(settings_path)
        if content:
            try:
                settings = json.loads(content)
            except json.JSONDecodeError:
                pass

    # Get hook configs for this target
    hook_configs = _get_ccr_hook_configs(target)

    # Check if already installed
    already_installed = False
    hooks = settings.get("hooks", {})
    for event_name in hook_configs:
        event_hooks = hooks.get(event_name, [])
        for hook in event_hooks:
            for h in hook.get("hooks", []):
                if h.get("type") == "command" and "ccr hooks handle" in h.get("command", ""):
                    already_installed = True
                    break

    if already_installed:
        console.print(f"  [dim]-[/dim] {target}: hooks already installed")
        return

    # Add hooks
    if "hooks" not in settings:
        settings["hooks"] = {}

    for event_name, hook_config in hook_configs.items():
        if event_name not in settings["hooks"]:
            settings["hooks"][event_name] = []
        settings["hooks"][event_name].append(hook_config)

    # Save
    ensure_directory(settings_path.parent)
    write_file_safe(settings_path, json.dumps(settings, indent=2) + "\n")
    console.print(f"  [green]✓[/green] {target}: installed hooks in {settings_path.relative_to(path) if path != Path('.') else settings_path}")


def _install_mcp_for_init(path: Path, target: str) -> None:
    """Install MCP server configuration for a specific target during init.

    MCP (Model Context Protocol) allows on-demand code review requests.
    - claude: .mcp.json in project root
    - trae: .mcp.json in project root
    - cursor: .cursor/mcp.json
    - gemini: not supported (no MCP)
    """
    import json

    # Gemini doesn't support MCP
    if target == "gemini":
        return

    # Get MCP config path based on target
    if target == "cursor":
        mcp_path = path / ".cursor" / "mcp.json"
    else:  # claude, trae
        mcp_path = path / ".mcp.json"

    # Load existing MCP config
    mcp_config: dict = {}
    if mcp_path.exists():
        content = read_file_safe(mcp_path)
        if content:
            try:
                mcp_config = json.loads(content)
            except json.JSONDecodeError:
                pass

    # Check if already configured
    servers = mcp_config.get("mcpServers", {})
    if "clean-code-reviewer" in servers:
        console.print(f"  [dim]-[/dim] {target}: MCP already configured")
        return

    # Add CCR MCP server
    if "mcpServers" not in mcp_config:
        mcp_config["mcpServers"] = {}

    mcp_config["mcpServers"]["clean-code-reviewer"] = {
        "command": "ccr",
        "args": ["mcp"]
    }

    # Save
    ensure_directory(mcp_path.parent)
    write_file_safe(mcp_path, json.dumps(mcp_config, indent=2) + "\n")

    relative_path = mcp_path.relative_to(path) if path != Path(".") else mcp_path
    console.print(f"  [green]✓[/green] {target}: configured MCP in {relative_path}")


@app.command()
def init(
    path: Annotated[
        Path,
        typer.Argument(help="Project path to initialize"),
    ] = Path("."),
    force: Annotated[
        bool,
        typer.Option("--force", "-f", help="Overwrite existing configuration"),
    ] = False,
    skip_download: Annotated[
        bool,
        typer.Option("--skip-download", help="Skip downloading rules from remote"),
    ] = False,
    non_interactive: Annotated[
        bool,
        typer.Option("--non-interactive", "-y", help="Use defaults, no prompts"),
    ] = False,
) -> None:
    """Initialize clean code rules in a project."""
    from clean_code_reviewer.tui.init_app import run_init_tui

    rules_dir = path / ".cleancoderules"

    if rules_dir.exists() and not force:
        console.print(f"[yellow]Rules directory already exists: {rules_dir}[/yellow]")
        console.print("Use --force to overwrite")
        raise typer.Exit(1)

    # Run TUI for interactive mode
    selected_prompts: list[str] = []

    if not non_interactive:
        tui_result = run_init_tui(path)
        if tui_result.cancelled:
            console.print("[yellow]Initialization cancelled.[/yellow]")
            raise typer.Exit(0)
        selected_prompts = tui_result.prompt_files

    console.print("[bold blue]Initializing Clean Code Reviewer...[/bold blue]\n")

    # Create directory structure: community/, team/
    ensure_directory(rules_dir)
    ensure_directory(rules_dir / "community")
    ensure_directory(rules_dir / "team")
    console.print(f"  [green]✓[/green] Created {rules_dir}/ (community/, team/)")

    # Create empty config file
    write_file_safe(rules_dir / "config.yaml", "")
    console.print(f"  [green]✓[/green] Created config.yaml")

    # Download base.yml (Level 1)
    if not skip_download:
        console.print("\n[bold]Downloading base rules...[/bold]")
        with RulesManager() as manager:
            result = manager.download_rule("base", rules_dir)
            if result:
                console.print(f"  [green]✓[/green] Downloaded base.yml")
            else:
                console.print(f"  [yellow]![/yellow] Could not download base.yml (will use sample)")
                _write_sample_base_rule(rules_dir)
    else:
        _write_sample_base_rule(rules_dir)
        console.print(f"  [green]✓[/green] Created base.yml (sample)")

    # Create sample team rule
    _write_sample_team_rule(rules_dir / "team")
    console.print(f"  [green]✓[/green] Created team/example.yml")

    # Create order.yml
    order_manager = OrderManager(rules_dir)
    order_manager.add_rule("team", "example")
    console.print(f"  [green]✓[/green] Created order.yml")

    # Handle prompt files based on TUI selection
    if selected_prompts:
        instructions = _get_prompt_instructions()

        if "claude" in selected_prompts:
            claude_path = path / "CLAUDE.md"
            if claude_path.exists():
                existing = read_file_safe(claude_path) or ""
                if "Clean Code Reviewer" not in existing:
                    write_file_safe(claude_path, existing + "\n\n" + instructions)
                    console.print(f"  [green]✓[/green] Updated CLAUDE.md with CCR instructions")
            else:
                write_file_safe(claude_path, f"# Project Guidelines\n\n{instructions}")
                console.print(f"  [green]✓[/green] Created CLAUDE.md")

        if "cursor" in selected_prompts:
            cursor_path = path / ".cursorrules"
            if cursor_path.exists():
                existing = read_file_safe(cursor_path) or ""
                if "Clean Code Reviewer" not in existing:
                    write_file_safe(cursor_path, existing + "\n\n" + instructions)
                    console.print(f"  [green]✓[/green] Updated .cursorrules with CCR instructions")
            else:
                write_file_safe(cursor_path, instructions)
                console.print(f"  [green]✓[/green] Created .cursorrules")

    # Add .cleancoderules to .gitignore if it exists
    gitignore_path = path / ".gitignore"
    if gitignore_path.exists():
        gitignore_content = read_file_safe(gitignore_path) or ""
        if ".cleancoderules" not in gitignore_content:
            # Append with newline if file doesn't end with one
            separator = "" if gitignore_content.endswith("\n") else "\n"
            write_file_safe(gitignore_path, gitignore_content + separator + ".cleancoderules\n")
            console.print(f"  [green]✓[/green] Added .cleancoderules to .gitignore")

    # Install hooks and MCP for AI coding assistants used in this project
    detected_targets = get_project_targets(path)

    # Targets that support hooks (Trae does not support hooks yet)
    hook_targets = [t for t in detected_targets if t != "trae"]
    # Targets that support MCP (all except gemini)
    mcp_targets = [t for t in detected_targets if t in ("claude", "cursor", "trae")]

    if detected_targets:
        if hook_targets:
            console.print("\n[bold]Installing hooks...[/bold]")
            for target in hook_targets:
                _install_hooks_for_init(path, target)

        if mcp_targets:
            console.print("\n[bold]Configuring MCP servers...[/bold]")
            for target in mcp_targets:
                _install_mcp_for_init(path, target)

        # Note about Trae not supporting hooks
        if "trae" in detected_targets:
            console.print("\n[yellow]Note:[/yellow] Trae does not support hooks yet, MCP only.")
    else:
        console.print("\n[dim]Skipping hooks/MCP (no AI coding assistants detected)[/dim]")

    # Summary
    console.print("\n[bold green]Initialization complete![/bold green]")
    if detected_targets:
        if hook_targets:
            console.print(f"\nCCR will automatically review code when {', '.join(hook_targets)} edits files.")
        if mcp_targets:
            console.print(f"You can also ask for explicit reviews via MCP ({', '.join(mcp_targets)}).")
    console.print("\nNext steps:")
    console.print("  1. Review rules in .cleancoderules/")
    console.print("  2. Add more rules: [cyan]ccr add <namespace/rule>[/cyan]")
    console.print("  3. Review code: [cyan]ccr review src/[/cyan]")


def _write_sample_base_rule(rules_dir: Path) -> None:
    """Write a sample base.yml rule file."""
    sample_rule = """# Base Principles
# Foundational clean code principles that apply to all languages.

_meta:
  name: base
  tags: [general, style]

naming:
  descriptive_names:
    enforcement: MUST
    value: "Use meaningful, descriptive names for variables, functions, and classes"
    good: |
      user_count = len(users)
      def calculate_total_price(items):
          pass
    bad: |
      x = len(u)
      def calc(i):
          pass

functions:
  single_responsibility:
    enforcement: SHOULD
    value: "Each function should do one thing well"
  max_lines:
    enforcement: SHOULD
    value: 20

error_handling:
  meaningful_messages:
    enforcement: SHOULD
    value: "Provide meaningful error messages"
  silent_exceptions:
    enforcement: MUST_NOT
    value: "Never swallow exceptions silently"
    bad: |
      try:
          risky_operation()
      except:
          pass
"""
    write_file_safe(rules_dir / "base.yml", sample_rule)


def _write_sample_team_rule(team_dir: Path) -> None:
    """Write a sample team rule to team/ folder."""
    sample_rule = """# Team Rules (Example)
# These rules have the HIGHEST priority (Level 3) and override all other rules.
#
# Hierarchy:
#   1. base.yml - Level 1 (base principles)
#   2. community/ - Level 2 (external rules: google, airbnb, etc.)
#   3. team/ - Level 3 (your team's rules - HIGHEST)

_meta:
  name: team-example
  tags: [team]

# Example: Override function length limits
functions:
  max_lines:
    enforcement: SHOULD
    value: 80
"""
    write_file_safe(team_dir / "example.yml", sample_rule)


@app.command()
def add(
    rule: Annotated[
        Optional[str],
        typer.Argument(help="Rule to download (e.g., 'google/python')"),
    ] = None,
    directory: Annotated[
        str,
        typer.Option("--directory", "-d", help="Target subdirectory (community, team)"),
    ] = "community",
    file: Annotated[
        Optional[Path],
        typer.Option("--file", "-f", help="Local file to add"),
    ] = None,
    rules_dir: Annotated[
        Path,
        typer.Option("--rules-dir", help="Base rules directory"),
    ] = Path(".cleancoderules"),
) -> None:
    """Add a rule from remote repository or local file.

    Examples:
        ccr add google/python                  # Download to community/google/
        ccr add airbnb/javascript              # Download to community/airbnb/
        ccr add -d team myteam/standards       # Download to team/myteam/
        ccr add -d team -f my-rule.md          # Copy local file to team/
    """
    # Validate directory
    valid_dirs = ["community", "team"]
    if directory not in valid_dirs:
        console.print(f"[red]Invalid directory: {directory}[/red]")
        console.print(f"Valid options: {', '.join(valid_dirs)}")
        raise typer.Exit(1)

    # Must provide either rule or file
    if not rule and not file:
        console.print("[red]Error: Must provide either a rule name or --file[/red]")
        console.print("Examples:")
        console.print("  ccr add google/python")
        console.print("  ccr add -d community -f my-rule.md")
        raise typer.Exit(1)

    # Determine target directory
    target_dir = rules_dir / directory
    ensure_directory(target_dir)

    # Initialize order manager
    order_manager = OrderManager(rules_dir)

    if file:
        # Copy local file (only the file, not directory structure)
        if not file.exists():
            console.print(f"[red]File not found: {file}[/red]")
            raise typer.Exit(1)

        content = read_file_safe(file)
        if content is None:
            console.print(f"[red]Could not read file: {file}[/red]")
            raise typer.Exit(1)

        # Use only the filename, not the full path
        dest_path = target_dir / file.name
        write_file_safe(dest_path, content)

        # Add to order.yml (use filename without .md extension)
        rule_name = file.stem
        order_manager.add_rule(directory, rule_name)

        console.print(f"[green]Added: {file.name} -> {dest_path}[/green]")
    else:
        # Download from remote
        assert rule is not None  # Already checked above
        if "/" not in rule:
            console.print(f"[red]Invalid rule format: {rule}[/red]")
            console.print("Use format: <namespace>/<rule-name> (e.g., 'google/python')")
            raise typer.Exit(1)

        console.print(f"[blue]Downloading rule: {rule}[/blue]")
        with RulesManager() as manager:
            result = manager.download_rule(rule, target_dir)
            if result:
                # Add to order.yml
                order_manager.add_rule(directory, rule)
                console.print(f"[green]Added: {rule} -> {result}[/green]")
            else:
                console.print(f"[red]Failed to download rule: {rule}[/red]")
                console.print("Make sure the rule exists:")
                console.print("  https://github.com/CleanCodeReviewer/Rules")
                raise typer.Exit(1)


@app.command()
def remove(
    rule: Annotated[
        str,
        typer.Argument(help="Rule name to remove"),
    ],
    rules_dir: Annotated[
        Path,
        typer.Option("--rules-dir", "-d", help="Rules directory"),
    ] = Path(".cleancoderules"),
) -> None:
    """Remove an installed rule."""
    engine = RulesEngine(rules_dir)
    rule_obj = engine.get_rule_by_name(rule)

    if rule_obj is None:
        console.print(f"[yellow]Rule not found: {rule}[/yellow]")
        raise typer.Exit(1)

    if rule_obj.source_file and rule_obj.source_file.exists():
        rule_obj.source_file.unlink()
        console.print(f"[green]Removed rule: {rule}[/green]")
    else:
        console.print(f"[red]Could not find rule file to remove[/red]")
        raise typer.Exit(1)


# Create update subcommand group
update_app = typer.Typer(help="Update rules or agent files", invoke_without_command=True)
app.add_typer(update_app, name="update")


@update_app.callback()
def update_callback(
    ctx: typer.Context,
    path: Annotated[
        Path,
        typer.Argument(help="Project path"),
    ] = Path("."),
    rules_dir: Annotated[
        Path,
        typer.Option("--rules-dir", "-d", help="Rules directory"),
    ] = Path(".cleancoderules"),
) -> None:
    """Update rules and agent files.

    Examples:
        ccr update              # Update both rules and agent files
        ccr update rules        # Only update rules from remote
        ccr update agent        # Only update agent files
    """
    # Store path and rules_dir in context for subcommands
    ctx.ensure_object(dict)
    ctx.obj["path"] = path
    ctx.obj["rules_dir"] = rules_dir

    # If no subcommand, run both updates
    if ctx.invoked_subcommand is None:
        rules_path = path / rules_dir

        if not rules_path.exists():
            console.print(f"[red]Rules directory not found: {rules_path}[/red]")
            console.print("Run 'ccr init' first to initialize the project.")
            raise typer.Exit(1)

        # Update rules
        console.print("[bold]Updating rules from remote...[/bold]")
        community_dir = rules_path / "community"

        with RulesManager() as manager:
            result = manager.download_rule("base", rules_path)
            if result:
                console.print(f"  [green]✓[/green] Updated base.yml")
            else:
                console.print(f"  [yellow]![/yellow] Could not update base.yml")

            if community_dir.exists():
                for namespace_dir in community_dir.iterdir():
                    if namespace_dir.is_dir():
                        namespace = namespace_dir.name
                        for rule_file in namespace_dir.glob("*.yml"):
                            rule_name = rule_file.stem
                            rule_path_str = f"{namespace}/{rule_name}"
                            result = manager.download_rule(rule_path_str, community_dir)
                            if result:
                                console.print(f"  [green]✓[/green] Updated {rule_path_str}")
                            else:
                                console.print(f"  [yellow]![/yellow] Could not update {rule_path_str}")

        # Update agent files
        console.print("\n[bold]Updating agent files...[/bold]")
        instructions = _get_prompt_instructions()
        pattern = r"##[^\n]*Clean Code Reviewer[^\n]*\n.*?(?=\n## |\n# |\Z)"

        def update_file(file_path: Path, name: str) -> None:
            if not file_path.exists():
                return
            content = read_file_safe(file_path) or ""
            if "Clean Code Reviewer" not in content:
                console.print(f"  [dim]-[/dim] {name} exists but has no CCR section")
                return
            new_content = re.sub(pattern, instructions.strip(), content, flags=re.DOTALL)
            write_file_safe(file_path, new_content)
            console.print(f"  [green]✓[/green] Updated {name}")

        claude_path = path / "CLAUDE.md"
        cursor_path = path / ".cursorrules"

        update_file(claude_path, "CLAUDE.md")
        update_file(cursor_path, ".cursorrules")

        if not claude_path.exists() and not cursor_path.exists():
            console.print("  [yellow]No agent files found (CLAUDE.md or .cursorrules)[/yellow]")

        # Update hooks
        detected_targets = get_project_targets(path)

        if detected_targets:
            console.print("\n[bold]Updating hooks...[/bold]")
            for t in detected_targets:
                settings_path = _get_settings_path(t, "project")
                settings = _load_settings(settings_path)
                if _has_ccr_hook(settings, t):
                    settings = _remove_ccr_hook(settings, t)
                settings = _add_ccr_hook(settings, t)
                _save_settings(settings_path, settings)
                console.print(f"  [green]✓[/green] {t}: updated hooks")

        console.print("\n[bold green]Update complete![/bold green]")


@update_app.command(name="rules")
def update_rules(
    path: Annotated[
        Path,
        typer.Argument(help="Project path"),
    ] = Path("."),
    rules_dir: Annotated[
        Path,
        typer.Option("--rules-dir", "-d", help="Rules directory"),
    ] = Path(".cleancoderules"),
) -> None:
    """Update rules from remote.

    Examples:
        ccr update rules           # Update all rules from remote
        ccr update rules ./myproj  # Update rules for a specific project
    """
    rules_path = path / rules_dir

    if not rules_path.exists():
        console.print(f"[red]Rules directory not found: {rules_path}[/red]")
        console.print("Run 'ccr init' first to initialize the project.")
        raise typer.Exit(1)

    console.print("[bold]Updating rules from remote...[/bold]")
    community_dir = rules_path / "community"

    # Re-download base.yml
    with RulesManager() as manager:
        result = manager.download_rule("base", rules_path)
        if result:
            console.print(f"  [green]✓[/green] Updated base.yml")
        else:
            console.print(f"  [yellow]![/yellow] Could not update base.yml")

        # Find and update community rules
        if community_dir.exists():
            for namespace_dir in community_dir.iterdir():
                if namespace_dir.is_dir():
                    namespace = namespace_dir.name
                    for rule_file in namespace_dir.glob("*.yml"):
                        rule_name = rule_file.stem
                        rule_path = f"{namespace}/{rule_name}"
                        result = manager.download_rule(rule_path, community_dir)
                        if result:
                            console.print(f"  [green]✓[/green] Updated {rule_path}")
                        else:
                            console.print(f"  [yellow]![/yellow] Could not update {rule_path}")

    console.print("\n[bold green]Update complete![/bold green]")


@update_app.command(name="agent")
def update_agent(
    path: Annotated[
        Path,
        typer.Argument(help="Project path"),
    ] = Path("."),
    rules_dir: Annotated[
        Path,
        typer.Option("--rules-dir", "-d", help="Rules directory"),
    ] = Path(".cleancoderules"),
) -> None:
    """Update agent files (CLAUDE.md, .cursorrules).

    Examples:
        ccr update agent           # Update agent files in current directory
        ccr update agent ./myproj  # Update agent files for a specific project
    """
    rules_path = path / rules_dir

    if not rules_path.exists():
        console.print(f"[red]Rules directory not found: {rules_path}[/red]")
        console.print("Run 'ccr init' first to initialize the project.")
        raise typer.Exit(1)

    console.print("[bold]Updating agent files...[/bold]")
    instructions = _get_prompt_instructions()
    # Match any heading containing "Clean Code Reviewer" and everything until next heading
    pattern = r"##[^\n]*Clean Code Reviewer[^\n]*\n.*?(?=\n## |\n# |\Z)"

    def update_agent_file(file_path: Path, name: str) -> None:
        if not file_path.exists():
            return
        content = read_file_safe(file_path) or ""
        if "Clean Code Reviewer" not in content:
            console.print(f"  [dim]-[/dim] {name} exists but has no CCR section")
            return
        new_content = re.sub(pattern, instructions.strip(), content, flags=re.DOTALL)
        write_file_safe(file_path, new_content)
        console.print(f"  [green]✓[/green] Updated {name}")

    claude_path = path / "CLAUDE.md"
    cursor_path = path / ".cursorrules"

    update_agent_file(claude_path, "CLAUDE.md")
    update_agent_file(cursor_path, ".cursorrules")

    if not claude_path.exists() and not cursor_path.exists():
        console.print("  [yellow]No agent files found (CLAUDE.md or .cursorrules)[/yellow]")

    console.print("\n[bold green]Update complete![/bold green]")


@update_app.command(name="hooks")
def update_hooks(
    path: Annotated[
        Path,
        typer.Argument(help="Project path"),
    ] = Path("."),
    target: Annotated[
        str,
        typer.Option("--target", "-t", help="Target: 'claude', 'gemini', 'cursor', or 'all'"),
    ] = "all",
) -> None:
    """Update/reinstall hooks for AI coding assistants.

    This will remove existing CCR hooks and reinstall them with the latest
    configuration. Useful after CCR updates.

    Examples:
        ccr update hooks                 # Update hooks for detected CLIs
        ccr update hooks -t claude       # Update Claude Code hooks only
        ccr update hooks -t cursor       # Update Cursor IDE hooks only
    """
    # Determine targets
    if target == "all":
        targets = get_project_targets(path)
        if not targets:
            console.print("[yellow]No AI coding assistants detected for this project[/yellow]")
            raise typer.Exit(1)
    elif target in HOOK_TARGETS:
        targets = [target]
    else:
        console.print(f"[red]Invalid target: {target}[/red]")
        raise typer.Exit(1)

    console.print("[bold]Updating hooks...[/bold]")

    for t in targets:
        settings_path = _get_settings_path(t, "project")
        settings = _load_settings(settings_path)

        # Remove existing CCR hooks
        if _has_ccr_hook(settings, t):
            settings = _remove_ccr_hook(settings, t)

        # Add fresh hooks
        settings = _add_ccr_hook(settings, t)
        _save_settings(settings_path, settings)
        console.print(f"  [green]✓[/green] {t}: updated hooks in {settings_path}")

    console.print("\n[bold green]Hooks updated![/bold green]")


@app.command(name="list")
def list_rules(
    query: Annotated[
        Optional[str],
        typer.Argument(help="Search term (matches name, namespace, or tags)"),
    ] = None,
    rules_dir: Annotated[
        Path,
        typer.Option("--rules-dir", "-d", help="Rules directory"),
    ] = Path(".cleancoderules"),
    remote: Annotated[
        bool,
        typer.Option("--remote", "-r", help="List remote rules only"),
    ] = False,
    all_rules: Annotated[
        bool,
        typer.Option("--all", "-a", help="List both local and remote rules"),
    ] = False,
) -> None:
    """List installed or available rules.

    Examples:
        ccr list              # List all local rules
        ccr list python       # List local rules matching 'python'
        ccr list -r           # List all remote rules
        ccr list python -r    # List remote rules matching 'python'
        ccr list python -a    # List both local and remote matching 'python'
    """

    def matches_query(name: str, namespace: str = "", tags: list[str] | None = None) -> bool:
        """Check if rule matches the search query."""
        if not query:
            return True
        q = query.lower()
        if q in name.lower():
            return True
        if namespace and q in namespace.lower():
            return True
        if tags and any(q in tag.lower() for tag in tags):
            return True
        return False

    show_local = not remote or all_rules
    show_remote = remote or all_rules

    # List local rules
    if show_local:
        engine = RulesEngine(rules_dir)
        local_rules = [r for r in engine.rules if matches_query(r.name, "", r.tags)]

        if local_rules:
            table = Table(title="Local Rules")
            table.add_column("Level", style="magenta")
            table.add_column("Name", style="cyan")
            table.add_column("Tags", style="yellow")

            for rule in local_rules:
                table.add_row(
                    rule.level_name,
                    rule.name,
                    ", ".join(rule.tags) if rule.tags else "-",
                )
            console.print(table)
        elif not show_remote:
            console.print("[yellow]No local rules found[/yellow]")
            console.print("Run 'ccr init' to create default rules or 'ccr add' to download rules")

    # List remote rules
    if show_remote:
        if show_local:
            console.print()  # Add spacing between tables
        console.print("[blue]Fetching remote rules...[/blue]")

        with RulesManager() as manager:
            all_remote = manager.list_available_rules()

        remote_rules = [r for r in all_remote if matches_query(r.name, r.namespace)]

        if remote_rules:
            table = Table(title="Remote Rules")
            table.add_column("Namespace", style="cyan")
            table.add_column("Rule", style="green")

            for rule in remote_rules:
                table.add_row(rule.namespace or "(base)", rule.name)
            console.print(table)
        elif not show_local:
            console.print("[yellow]No remote rules found[/yellow]")
            console.print("Browse available rules at: https://github.com/CleanCodeReviewer/Rules")


@app.command()
def review(
    files: Annotated[
        Optional[list[Path]],
        typer.Argument(help="Files or directories to review"),
    ] = None,
    pattern: Annotated[
        Optional[list[str]],
        typer.Option("--pattern", "-p", help="Glob patterns to match files (e.g., '**/*.py')"),
    ] = None,
    changed: Annotated[
        bool,
        typer.Option("--changed", "-c", help="Review only git changed files"),
    ] = False,
    staged: Annotated[
        bool,
        typer.Option("--staged", help="Review only git staged files"),
    ] = False,
    base_ref: Annotated[
        str,
        typer.Option("--base", "-b", help="Git base ref for comparison"),
    ] = "HEAD",
    compare_ref: Annotated[
        Optional[str],
        typer.Option("--compare", help="Git compare ref"),
    ] = None,
    reviewer: Annotated[
        Optional[str],
        typer.Option("--reviewer", "-r", help="Reviewer backend (litellm, claudecode, gemini, codex)"),
    ] = None,
    rules_dir: Annotated[
        Path,
        typer.Option("--rules-dir", "-d", help="Rules directory"),
    ] = Path(".cleancoderules"),
    model: Annotated[
        Optional[str],
        typer.Option("--model", "-m", help="LLM model to use (for litellm)"),
    ] = None,
    tags: Annotated[
        Optional[str],
        typer.Option("--tags", "-t", help="Rule tags to apply (comma-separated)"),
    ] = None,
    output: Annotated[
        Optional[Path],
        typer.Option("--output", "-o", help="Output file for review results"),
    ] = None,
    stream: Annotated[
        bool,
        typer.Option("--stream", "-s", help="Stream output as it's generated"),
    ] = False,
) -> None:
    """Review code files against rules.

    Examples:
        ccr review src/                          # Review all files in src/
        ccr review -p "**/*.py"                  # Review all Python files
        ccr review --changed                     # Review git changed files
        ccr review --staged                      # Review staged files only
        ccr review -r claudecode src/main.py    # Use Claude Code CLI
        ccr review -r gemini --pattern "*.ts"   # Use Gemini for TypeScript
    """
    from clean_code_reviewer.core.reviewers import (
        ReviewRequest,
        get_available_reviewers,
        get_reviewer,
    )
    from clean_code_reviewer.tui import (
        run_file_mode_select_tui,
        run_reviewer_select_tui,
        save_reviewer_to_config,
    )
    from clean_code_reviewer.utils.file_selector import FileSelector

    settings = get_effective_settings()

    # Determine reviewer
    selected_reviewer = reviewer or settings.default_reviewer

    # Interactive config if no reviewer configured and no specific inputs
    no_file_input = not files and not pattern and not changed and not staged
    if not selected_reviewer and no_file_input:
        console.print("[yellow]No reviewer configured. Launching setup...[/yellow]\n")
        selected_reviewer = run_reviewer_select_tui()
        if selected_reviewer is None:
            console.print("[red]Setup cancelled.[/red]")
            raise typer.Exit(1)
        save_reviewer_to_config(selected_reviewer, rules_dir / "config.yaml")
        console.print(f"[green]Saved {selected_reviewer} as default reviewer.[/green]\n")

    # If still no reviewer, default to litellm
    if not selected_reviewer:
        selected_reviewer = "litellm"

    # Interactive file selection if no files specified
    if no_file_input:
        mode = run_file_mode_select_tui()
        if mode is None:
            console.print("[red]Cancelled.[/red]")
            raise typer.Exit(1)
        if mode == "all":
            pattern = ["**/*.py", "**/*.js", "**/*.ts", "**/*.tsx", "**/*.jsx"]
        elif mode == "changed":
            changed = True
        elif mode == "staged":
            staged = True
        elif mode == "pattern":
            from rich.prompt import Prompt
            custom_pattern = Prompt.ask("Enter glob pattern", default="**/*.py")
            pattern = [custom_pattern]

    # Select files using FileSelector
    selector = FileSelector()
    files_to_review = selector.select(
        files=files,
        patterns=pattern,
        changed=changed,
        staged=staged,
        base_ref=base_ref,
        compare_ref=compare_ref,
    )

    if not files_to_review:
        console.print("[red]No files to review[/red]")
        console.print("Specify files, patterns, or use --changed/--staged flags")
        raise typer.Exit(1)

    console.print(f"[blue]Reviewing {len(files_to_review)} file(s) with {selected_reviewer}...[/blue]\n")

    # Initialize components
    engine = RulesEngine(rules_dir)
    builder = PromptBuilder(engine)
    tag_list = [t.strip() for t in tags.split(",")] if tags else None

    # Get reviewer instance
    reviewer_kwargs = {}
    if selected_reviewer == "litellm":
        reviewer_kwargs["model"] = model or settings.model
        reviewer_kwargs["settings"] = settings

    try:
        rev = get_reviewer(selected_reviewer, **reviewer_kwargs)
    except ValueError as e:
        console.print(f"[red]{e}[/red]")
        raise typer.Exit(1)

    if not rev.is_available():
        available = get_available_reviewers()
        console.print(f"[red]Reviewer '{selected_reviewer}' is not available.[/red]")
        if available:
            console.print(f"Available reviewers: {', '.join(available)}")
        else:
            console.print("No reviewers are currently available. Check your configuration.")
        raise typer.Exit(1)

    all_results: list[str] = []

    for file_path in files_to_review:
        context = CodeContext.from_file(file_path)
        if context is None:
            console.print(f"[yellow]Could not read: {file_path}[/yellow]")
            continue

        console.print(f"[cyan]Reviewing: {file_path}[/cyan]")

        system_prompt, user_prompt = builder.build_review_prompt(
            code=context,
            tags=tag_list,
        )

        request = ReviewRequest(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            file_path=str(file_path),
            language=context.language,
        )

        try:
            if stream:
                console.print()
                for chunk in rev.review_stream(request):
                    console.print(chunk, end="")
                console.print("\n")
            else:
                response = rev.review(request)
                if response.error:
                    console.print(f"[red]Error: {response.error}[/red]")
                else:
                    all_results.append(f"## {file_path}\n\n{response.content}")

                    # Display with rich markdown
                    console.print()
                    console.print(Panel(Markdown(response.content), title=str(file_path)))
                    console.print()

        except Exception as e:
            console.print(f"[red]Error reviewing {file_path}: {e}[/red]")

    # Save output if requested
    if output and all_results:
        output_content = "\n\n---\n\n".join(all_results)
        write_file_safe(output, output_content)
        console.print(f"[green]Results saved to: {output}[/green]")


@app.command()
def mcp(
    rules_dir: Annotated[
        Path,
        typer.Option("--rules-dir", "-d", help="Rules directory"),
    ] = Path(".cleancoderules"),
    transport: Annotated[
        str,
        typer.Option("--transport", "-t", help="Transport type (stdio or sse)"),
    ] = "stdio",
    host: Annotated[
        str,
        typer.Option("--host", "-h", help="Host to bind to (for SSE)"),
    ] = "127.0.0.1",
    port: Annotated[
        int,
        typer.Option("--port", "-p", help="Port to listen on (for SSE)"),
    ] = 11111,
) -> None:
    """Start the MCP server for Claude Code integration."""
    if transport == "sse":
        console.print(f"[blue]Starting MCP SSE server on http://{host}:{port}...[/blue]")
    else:
        console.print(f"[blue]Starting MCP server (transport={transport})...[/blue]")
    run_mcp_server(rules_dir, transport, host, port)


@app.command()
def config(
    rules_dir: Annotated[
        Path,
        typer.Option("--rules-dir", "-d", help="Rules directory"),
    ] = Path(".cleancoderules"),
    show: Annotated[
        bool,
        typer.Option("--show", "-s", help="Show current configuration"),
    ] = True,
) -> None:
    """Show or edit configuration."""
    config_path = rules_dir / "config.yaml"

    if not config_path.exists():
        console.print(f"[yellow]No configuration found at {config_path}[/yellow]")
        console.print("Run 'ccr init' to create default configuration")
        raise typer.Exit(1)

    if show:
        content = read_file_safe(config_path)
        if content:
            console.print(Panel(content, title="Configuration"))

        # Also show effective settings
        settings = get_effective_settings()
        console.print("\n[bold]Effective Settings:[/bold]")
        console.print(f"  Model: {settings.model}")
        console.print(f"  Temperature: {settings.temperature}")
        console.print(f"  Max Tokens: {settings.max_tokens}")
        console.print(f"  Rules Priority: {', '.join(settings.rules_priority)}")


@app.command()
def ci(
    files: Annotated[
        Optional[list[Path]],
        typer.Argument(help="Files to review (defaults to current directory)"),
    ] = None,
    rules_dir: Annotated[
        Path,
        typer.Option("--rules-dir", "-d", help="Rules directory"),
    ] = Path(".cleancoderules"),
    model: Annotated[
        Optional[str],
        typer.Option("--model", "-m", help="LLM model to use"),
    ] = None,
    output_format: Annotated[
        str,
        typer.Option("--format", "-f", help="Output format (text, json, github)"),
    ] = "text",
    output: Annotated[
        Optional[Path],
        typer.Option("--output", "-o", help="Output file"),
    ] = None,
    fail_on_warning: Annotated[
        bool,
        typer.Option("--fail-on-warning", help="Fail if warnings are found"),
    ] = False,
) -> None:
    """Run code review for CI/CD pipelines."""
    runner = CIRunner(
        rules_dir=rules_dir,
        model=model,
        fail_on_error=True,
        fail_on_warning=fail_on_warning,
    )

    if files:
        result = runner.review_files(files)
    else:
        result = runner.review_directory(Path.cwd())

    runner.print_results(result, output_format=output_format, output_file=output)

    if not result.success:
        raise typer.Exit(1)


@app.command()
def order(
    rules_dir: Annotated[
        Path,
        typer.Option("--rules-dir", "-d", help="Rules directory"),
    ] = Path(".cleancoderules"),
) -> None:
    """Interactively reorder rules within levels.

    Opens a TUI to move rules up/down within their level (community, team).
    Rules can only be reordered within the same level - they cannot be moved between levels.

    Controls:
      1/2    - Switch between community/team panels
      k/↑    - Move selected rule up (lower priority)
      j/↓    - Move selected rule down (higher priority)
      q/ESC  - Save and quit
    """
    if not rules_dir.exists():
        console.print(f"[red]Rules directory not found: {rules_dir}[/red]")
        console.print("Run 'ccr init' first")
        raise typer.Exit(1)

    from clean_code_reviewer.tui import run_order_tui

    run_order_tui(rules_dir)
    console.print("[green]Order saved![/green]")


# Create hooks subcommand group
hooks_app = typer.Typer(help="Manage AI coding assistant hooks for automatic code review")
app.add_typer(hooks_app, name="hooks")

# Supported targets
HOOK_TARGETS = ["claude", "gemini", "cursor"]


def _get_ccr_hook_configs(target: str) -> dict:
    """Get the CCR hook configurations for the target CLI.

    Returns a dict with hook event names as keys and hook configs as values.
    Only installs post-tool hooks to review code after edits.
    """
    if target == "gemini":
        # Gemini CLI: AfterTool only
        matcher = "edit_file|write_file"
        return {
            "AfterTool": {
                "matcher": matcher,
                "hooks": [{"type": "command", "command": "ccr hooks handle"}],
            },
        }
    elif target == "cursor":
        # Cursor IDE: afterFileEdit only (simpler structure, no matcher)
        return {
            "afterFileEdit": {"command": "ccr hooks handle"},
        }
    else:  # claude
        # Claude Code: PostToolUse only
        matcher = "Edit|Write|NotebookEdit"
        return {
            "PostToolUse": {
                "matcher": matcher,
                "hooks": [{"type": "command", "command": "ccr hooks handle"}],
            },
        }


def _get_settings_path(target: str, scope: str) -> Path:
    """Get the settings file path for the given target and scope."""
    if target == "gemini":
        if scope == "user":
            return Path.home() / ".gemini" / "settings.json"
        else:  # project
            return Path(".gemini") / "settings.json"
    elif target == "cursor":
        # Cursor uses hooks.json instead of settings.json
        if scope == "user":
            return Path.home() / ".cursor" / "hooks.json"
        else:  # project
            return Path(".cursor") / "hooks.json"
    else:  # claude
        if scope == "user":
            return Path.home() / ".claude" / "settings.json"
        else:  # project
            return Path(".claude") / "settings.json"


def _load_settings(path: Path) -> dict:
    """Load settings from a JSON file."""
    import json

    if not path.exists():
        return {}
    content = read_file_safe(path)
    if not content:
        return {}
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        return {}


def _save_settings(path: Path, settings: dict) -> None:
    """Save settings to a JSON file."""
    import json

    ensure_directory(path.parent)
    write_file_safe(path, json.dumps(settings, indent=2) + "\n")


def _is_ccr_hook_entry(hook: dict) -> bool:
    """Check if a hook entry is a CCR hook.

    Handles both Claude/Gemini format (with hooks array) and Cursor format (direct command).
    """
    # Claude/Gemini format: {"matcher": "...", "hooks": [{"type": "command", "command": "..."}]}
    for h in hook.get("hooks", []):
        if h.get("type") == "command":
            cmd = h.get("command", "")
            if "ccr hooks handle" in cmd or "ccr review" in cmd:
                return True

    # Cursor format: {"command": "..."}
    cmd = hook.get("command", "")
    if "ccr hooks handle" in cmd or "ccr review" in cmd:
        return True

    return False


def _has_ccr_hook(settings: dict, target: str) -> bool:
    """Check if CCR hook is already installed for target."""
    hooks = settings.get("hooks", {})
    hook_configs = _get_ccr_hook_configs(target)

    for event_name in hook_configs:
        event_hooks = hooks.get(event_name, [])
        for hook in event_hooks:
            if _is_ccr_hook_entry(hook):
                return True
    return False


def _add_ccr_hook(settings: dict, target: str) -> dict:
    """Add CCR hooks to settings for target."""
    # Cursor hooks.json requires a version field
    if target == "cursor" and "version" not in settings:
        settings["version"] = 1

    if "hooks" not in settings:
        settings["hooks"] = {}

    hook_configs = _get_ccr_hook_configs(target)

    for event_name, hook_config in hook_configs.items():
        if event_name not in settings["hooks"]:
            settings["hooks"][event_name] = []
        # Check if already exists
        already_exists = any(
            _is_ccr_hook_entry(h) for h in settings["hooks"][event_name]
        )
        if not already_exists:
            settings["hooks"][event_name].append(hook_config)

    return settings


def _remove_ccr_hook(settings: dict, target: str) -> dict:
    """Remove CCR hooks from settings for target."""
    if "hooks" not in settings:
        return settings

    hook_configs = _get_ccr_hook_configs(target)

    for event_name in hook_configs:
        if event_name not in settings["hooks"]:
            continue

        # Filter out CCR hooks
        settings["hooks"][event_name] = [
            hook
            for hook in settings["hooks"][event_name]
            if not _is_ccr_hook_entry(hook)
        ]

        # Clean up empty event
        if not settings["hooks"][event_name]:
            del settings["hooks"][event_name]

    # Clean up empty hooks
    if not settings["hooks"]:
        del settings["hooks"]

    return settings


@hooks_app.command(name="install")
def hooks_install(
    target: Annotated[
        str,
        typer.Option("--target", "-t", help="Target: 'claude', 'gemini', 'cursor', or 'all'"),
    ] = "all",
) -> None:
    """Install hooks for automatic code review.

    Installs project-level hooks for Claude Code, Gemini CLI, and/or Cursor IDE.

    Examples:
        ccr hooks install                    # Install for detected CLIs
        ccr hooks install -t claude          # Install for Claude Code only
        ccr hooks install -t gemini          # Install for Gemini CLI only
        ccr hooks install -t cursor          # Install for Cursor IDE only
    """
    # Determine targets
    if target == "all":
        targets = get_project_targets(Path("."))
        if not targets:
            console.print("[yellow]No AI coding assistants detected for this project[/yellow]")
            console.print("Make sure .claude, .gemini, .cursor directory or CLAUDE.md, .cursorrules exists")
            raise typer.Exit(1)
    elif target in HOOK_TARGETS:
        targets = [target]
    else:
        console.print(f"[red]Invalid target: {target}[/red]")
        console.print(f"Use: {', '.join(HOOK_TARGETS)} or 'all'")
        raise typer.Exit(1)

    for t in targets:
        settings_path = _get_settings_path(t, "project")
        settings = _load_settings(settings_path)

        if _has_ccr_hook(settings, t):
            console.print(f"[dim]-[/dim] {t}: already installed")
            continue

        settings = _add_ccr_hook(settings, t)
        _save_settings(settings_path, settings)
        console.print(f"[green]✓[/green] {t}: installed hooks in {settings_path}")

    console.print("\n[bold]CCR will now review code after file edits.[/bold]")


@hooks_app.command(name="uninstall")
def hooks_uninstall(
    target: Annotated[
        str,
        typer.Option("--target", "-t", help="Target: 'claude', 'gemini', 'cursor', or 'all'"),
    ] = "all",
) -> None:
    """Uninstall hooks.

    Examples:
        ccr hooks uninstall                  # Uninstall from all targets
        ccr hooks uninstall -t claude        # Uninstall from Claude Code only
        ccr hooks uninstall -t cursor        # Uninstall from Cursor IDE only
    """
    # Determine targets
    if target == "all":
        targets = HOOK_TARGETS
    elif target in HOOK_TARGETS:
        targets = [target]
    else:
        console.print(f"[red]Invalid target: {target}[/red]")
        raise typer.Exit(1)

    for t in targets:
        settings_path = _get_settings_path(t, "project")
        settings = _load_settings(settings_path)

        if not _has_ccr_hook(settings, t):
            continue

        settings = _remove_ccr_hook(settings, t)
        _save_settings(settings_path, settings)
        console.print(f"[green]✓[/green] {t}: removed hooks from {settings_path}")


@hooks_app.command(name="status")
def hooks_status() -> None:
    """Show current hook installation status."""
    from rich.table import Table

    table = Table(title="CCR Hook Status")
    table.add_column("Target", style="cyan")
    table.add_column("Path", style="dim")
    table.add_column("Status", style="bold")

    for t in HOOK_TARGETS:
        settings_path = _get_settings_path(t, "project")
        settings = _load_settings(settings_path)

        if not settings_path.exists():
            status = "[dim]No settings[/dim]"
        elif _has_ccr_hook(settings, t):
            status = "[green]Installed[/green]"
        else:
            status = "[yellow]Not installed[/yellow]"

        table.add_row(t, str(settings_path), status)

    console.print(table)

    # Show detection status
    console.print("\n[bold]Detection:[/bold]")
    console.print(f"  Claude Code: {'[green]found[/green]' if is_claude_code_installed() else '[dim]not found[/dim]'}")
    console.print(f"  Gemini CLI:  {'[green]found[/green]' if is_gemini_cli_installed() else '[dim]not found[/dim]'}")
    console.print(f"  Cursor IDE:  {'[green]found[/green]' if is_cursor_installed() else '[dim]not found[/dim]'}")


@hooks_app.command(name="handle", hidden=True)
def hooks_handle() -> None:
    """Handle hook events from AI coding assistants (internal command).

    Reviews the edited code and suggests refactoring.
    Works on Windows, macOS, and Linux.
    """
    import json
    import sys

    try:
        # Read JSON input from stdin
        input_data = sys.stdin.read()
        if not input_data.strip():
            sys.exit(0)

        hook_input = json.loads(input_data)

        # Extract file path from tool_input
        tool_input = hook_input.get("tool_input", {})
        file_path = tool_input.get("file_path") or tool_input.get("notebook_path")

        if not file_path:
            sys.exit(0)

        target_file = Path(file_path)
        if not target_file.exists():
            sys.exit(0)

        # Check if .cleancoderules directory exists
        rules_dir = Path(".cleancoderules")
        if not rules_dir.exists():
            sys.exit(0)

        from clean_code_reviewer.core.prompt_builder import CodeContext, PromptBuilder
        from clean_code_reviewer.core.reviewers import ReviewRequest, get_reviewer
        from clean_code_reviewer.core.rules_engine import RulesEngine

        engine = RulesEngine(rules_dir)
        builder = PromptBuilder(engine)

        context = CodeContext.from_file(target_file)
        if context is None:
            sys.exit(0)

        system_prompt, user_prompt = builder.build_review_prompt(code=context)

        request = ReviewRequest(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            file_path=str(target_file),
            language=context.language,
        )

        settings = get_effective_settings()
        reviewer = get_reviewer("litellm", model=settings.model, settings=settings)

        if not reviewer.is_available():
            sys.exit(0)

        response = reviewer.review(request)

        if response.error:
            sys.exit(0)

        output = {
            "hookSpecificOutput": {
                "hookEventName": "PostToolUse",
                "additionalContext": (
                    f"## CCR Review for {file_path}:\n\n"
                    f"{response.content}\n\n"
                    "Fix any violations before continuing."
                ),
            }
        }
        print(json.dumps(output))

    except Exception:
        # Always exit silently on any error
        pass

    sys.exit(0)


if __name__ == "__main__":
    app()
