"""Textual TUI for interactive configuration."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Center, Vertical
from textual.widgets import Button, Footer, Header, Label, ListItem, ListView, Static

from clean_code_reviewer.core.reviewers import get_all_reviewer_types, get_available_reviewers
from clean_code_reviewer.utils.logger import get_logger

logger = get_logger(__name__)


class ReviewerItem(ListItem):
    """A list item representing a reviewer option."""

    def __init__(self, name: str, available: bool) -> None:
        super().__init__()
        self.reviewer_name = name
        self.available = available

    def compose(self) -> ComposeResult:
        status = "[green]ready[/green]" if self.available else "[yellow]not installed[/yellow]"
        yield Label(f"  {self.reviewer_name.ljust(12)} {status}")


class FileModeItem(ListItem):
    """A list item representing a file selection mode."""

    def __init__(self, mode: str, label: str, description: str) -> None:
        super().__init__()
        self.mode = mode
        self.label = label
        self.description = description

    def compose(self) -> ComposeResult:
        yield Label(f"  {self.label}")
        yield Label(f"    [dim]{self.description}[/dim]")


class ReviewerSelectApp(App[str | None]):
    """Textual app for selecting a reviewer."""

    CSS = """
    Screen {
        align: center middle;
    }

    #container {
        width: 60;
        height: auto;
        border: solid $accent;
        padding: 1 2;
    }

    #title {
        text-align: center;
        text-style: bold;
        padding: 1;
        background: $surface-lighten-1;
        margin-bottom: 1;
    }

    ListView {
        height: auto;
        max-height: 20;
        margin: 1 0;
    }

    ListItem {
        padding: 0 1;
        height: 2;
    }

    ListItem:hover {
        background: $surface-lighten-1;
    }

    ListView:focus > ListItem.--highlight {
        background: $accent;
    }

    #hint {
        text-align: center;
        color: $text-muted;
        padding: 1;
    }
    """

    BINDINGS = [
        Binding("enter", "select", "Select"),
        Binding("escape", "cancel", "Cancel"),
        Binding("q", "cancel", "Cancel", show=False),
    ]

    def __init__(self) -> None:
        super().__init__()
        self.selected_reviewer: str | None = None
        self.available = get_available_reviewers()
        self.all_types = get_all_reviewer_types()

    def compose(self) -> ComposeResult:
        yield Header()
        with Center():
            with Vertical(id="container"):
                yield Static("Select Default Reviewer", id="title")
                yield ListView(
                    *[
                        ReviewerItem(name, name in self.available)
                        for name in self.all_types
                    ],
                    id="reviewer-list",
                )
                yield Static("[dim]↑/↓ Navigate  •  Enter Select  •  Esc Cancel[/dim]", id="hint")
        yield Footer()

    def on_mount(self) -> None:
        """Focus the list on mount."""
        self.query_one("#reviewer-list", ListView).focus()

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        """Handle selection."""
        if isinstance(event.item, ReviewerItem):
            self.selected_reviewer = event.item.reviewer_name
            self.exit(self.selected_reviewer)

    def action_select(self) -> None:
        """Select the highlighted item."""
        list_view = self.query_one("#reviewer-list", ListView)
        if list_view.highlighted_child and isinstance(list_view.highlighted_child, ReviewerItem):
            self.selected_reviewer = list_view.highlighted_child.reviewer_name
            self.exit(self.selected_reviewer)

    def action_cancel(self) -> None:
        """Cancel selection."""
        self.exit(None)


class FileModeSelectApp(App[str | None]):
    """Textual app for selecting file selection mode."""

    CSS = """
    Screen {
        align: center middle;
    }

    #container {
        width: 70;
        height: auto;
        border: solid $accent;
        padding: 1 2;
    }

    #title {
        text-align: center;
        text-style: bold;
        padding: 1;
        background: $surface-lighten-1;
        margin-bottom: 1;
    }

    ListView {
        height: auto;
        max-height: 20;
        margin: 1 0;
    }

    ListItem {
        padding: 0 1;
        height: 3;
    }

    ListItem:hover {
        background: $surface-lighten-1;
    }

    ListView:focus > ListItem.--highlight {
        background: $accent;
    }

    #hint {
        text-align: center;
        color: $text-muted;
        padding: 1;
    }
    """

    BINDINGS = [
        Binding("enter", "select", "Select"),
        Binding("escape", "cancel", "Cancel"),
        Binding("q", "cancel", "Cancel", show=False),
    ]

    FILE_MODES = [
        ("changed", "Git Changed Files", "Review files modified since last commit"),
        ("staged", "Git Staged Files", "Review only staged files"),
        ("all", "All Code Files", "Review all code files in current directory"),
        ("pattern", "Custom Pattern", "Specify a glob pattern (e.g., **/*.py)"),
    ]

    def __init__(self) -> None:
        super().__init__()
        self.selected_mode: str | None = None

    def compose(self) -> ComposeResult:
        yield Header()
        with Center():
            with Vertical(id="container"):
                yield Static("Select Files to Review", id="title")
                yield ListView(
                    *[
                        FileModeItem(mode, label, desc)
                        for mode, label, desc in self.FILE_MODES
                    ],
                    id="mode-list",
                )
                yield Static("[dim]↑/↓ Navigate  •  Enter Select  •  Esc Cancel[/dim]", id="hint")
        yield Footer()

    def on_mount(self) -> None:
        """Focus the list on mount."""
        self.query_one("#mode-list", ListView).focus()

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        """Handle selection."""
        if isinstance(event.item, FileModeItem):
            self.selected_mode = event.item.mode
            self.exit(self.selected_mode)

    def action_select(self) -> None:
        """Select the highlighted item."""
        list_view = self.query_one("#mode-list", ListView)
        if list_view.highlighted_child and isinstance(list_view.highlighted_child, FileModeItem):
            self.selected_mode = list_view.highlighted_child.mode
            self.exit(self.selected_mode)

    def action_cancel(self) -> None:
        """Cancel selection."""
        self.exit(None)


def run_reviewer_select_tui() -> str | None:
    """Run the reviewer selection TUI and return the selected reviewer."""
    app = ReviewerSelectApp()
    return app.run()


def run_file_mode_select_tui() -> str | None:
    """Run the file mode selection TUI and return the selected mode."""
    app = FileModeSelectApp()
    return app.run()


def save_reviewer_to_config(reviewer: str, config_path: Path) -> bool:
    """
    Save reviewer choice to config.yaml.

    Args:
        reviewer: Reviewer name to save
        config_path: Path to config.yaml file

    Returns:
        True if saved successfully
    """
    try:
        config: dict[str, Any] = {}

        # Load existing config if it exists
        if config_path.exists():
            with open(config_path, encoding="utf-8") as f:
                config = yaml.safe_load(f) or {}

        # Update reviewer
        config["default_reviewer"] = reviewer

        # Ensure parent directory exists
        config_path.parent.mkdir(parents=True, exist_ok=True)

        # Save config
        with open(config_path, "w", encoding="utf-8") as f:
            yaml.dump(config, f, default_flow_style=False, sort_keys=False)

        logger.info(f"Saved default_reviewer={reviewer} to {config_path}")
        return True

    except Exception as e:
        logger.error(f"Failed to save config: {e}")
        return False
