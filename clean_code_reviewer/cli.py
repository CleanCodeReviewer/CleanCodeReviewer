"""CLI application for Clean Code Reviewer."""

from __future__ import annotations

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




def _get_agent_instructions() -> str:
    """Get the CCR instructions for agent files."""
    return """## Clean Code Reviewer

**Before generating or modifying code**, you MUST:
1. Check if `.cleancoderules/` exists.
2. If it exists, read and apply those rules.
3. If it does not exist, proceed with Level 2/1 rules only.

**After generating or modifying code**, you MUST:
1. Use the `review_code` MCP tool if it is configured in this environment.
2. Otherwise run `ccr review <file>` for each modified file.
3. Fix any violations before presenting the code.

### Rule Priority
- Level 3: Team rules in `.cleancoderules/` (highest)
- Level 2: Language-specific rules
- Level 1: General principles

If rules conflict, always follow the higher-level rule.
"""


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
    selected_agents: list[str] = []

    if not non_interactive:
        tui_result = run_init_tui(path)
        if tui_result.cancelled:
            console.print("[yellow]Initialization cancelled.[/yellow]")
            raise typer.Exit(0)
        selected_agents = tui_result.agent_files

    console.print("[bold blue]Initializing Clean Code Reviewer...[/bold blue]\n")

    # Create directory structure: community/, team/
    ensure_directory(rules_dir)
    ensure_directory(rules_dir / "community")
    ensure_directory(rules_dir / "team")
    console.print(f"  [green]✓[/green] Created {rules_dir}/ (community/, team/)")

    # Create default config
    default_config = """# Clean Code Reviewer Configuration
model: gpt-4
temperature: 0.3
max_tokens: 2000

# Priority order for rule categories
rules_priority:
  - security
  - style
  - performance
"""
    write_file_safe(rules_dir / "config.yaml", default_config)
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

    # Handle agent files based on TUI selection
    if selected_agents:
        instructions = _get_agent_instructions()

        if "claude" in selected_agents:
            claude_path = path / "CLAUDE.md"
            if claude_path.exists():
                existing = read_file_safe(claude_path) or ""
                if "Clean Code Reviewer" not in existing:
                    write_file_safe(claude_path, existing + "\n\n" + instructions)
                    console.print(f"  [green]✓[/green] Updated CLAUDE.md with CCR instructions")
            else:
                write_file_safe(claude_path, f"# Project Guidelines\n\n{instructions}")
                console.print(f"  [green]✓[/green] Created CLAUDE.md")

        if "cursor" in selected_agents:
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

    # Summary
    console.print("\n[bold green]Initialization complete![/bold green]")
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


if __name__ == "__main__":
    app()
