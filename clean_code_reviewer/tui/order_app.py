"""Textual TUI for rule ordering."""

from __future__ import annotations

from pathlib import Path

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import Footer, Header, Label, ListItem, ListView, Static

from clean_code_reviewer.core.order_manager import OrderManager


class RuleItem(ListItem):
    """A list item representing a rule."""

    def __init__(self, rule_name: str, index: int) -> None:
        super().__init__()
        self.rule_name = rule_name
        self.index = index

    def compose(self) -> ComposeResult:
        yield Label(f"{self.index + 1}. {self.rule_name}")


class DirectoryPanel(Vertical):
    """Panel showing rules for a single directory."""

    def __init__(
        self,
        directory: str,
        level_name: str,
        rules: list[str],
        is_active: bool = False,
    ) -> None:
        super().__init__(classes="directory-panel")
        self.directory = directory
        self.level_name = level_name
        self.rules = rules
        self.is_active = is_active
        if is_active:
            self.add_class("active")

    def compose(self) -> ComposeResult:
        yield Static(
            f"[bold]{self.directory}/[/bold] ({self.level_name})",
            classes="panel-header",
        )
        if self.rules:
            list_view = ListView(
                *[RuleItem(rule, i) for i, rule in enumerate(self.rules)],
                id=f"list-{self.directory}",
            )
            yield list_view
        else:
            yield Static("[dim](no rules)[/dim]", classes="empty-message")


class OrderApp(App[None]):
    """Textual app for reordering rules."""

    CSS = """
    Screen {
        layout: horizontal;
    }

    .directory-panel {
        width: 1fr;
        height: 100%;
        border: solid $surface-lighten-2;
        padding: 1;
        margin: 0 1;
    }

    .directory-panel.active {
        border: solid $accent;
    }

    .panel-header {
        text-align: center;
        background: $surface-lighten-1;
        padding: 1;
        margin-bottom: 1;
    }

    .empty-message {
        text-align: center;
        padding: 2;
    }

    ListView {
        height: auto;
        max-height: 100%;
    }

    ListItem {
        padding: 0 1;
    }

    ListItem:hover {
        background: $surface-lighten-1;
    }

    ListView:focus > ListItem.--highlight {
        background: $accent;
    }

    #help-bar {
        dock: bottom;
        height: 3;
        background: $surface-lighten-1;
        padding: 1;
    }

    #status {
        dock: bottom;
        height: 1;
        background: $success;
        color: $text;
        padding: 0 1;
    }

    .hidden {
        display: none;
    }
    """

    BINDINGS = [
        Binding("q", "quit", "Quit & Save"),
        Binding("escape", "quit", "Quit & Save", show=False),
        Binding("1", "select_community", "Community"),
        Binding("2", "select_team", "Team"),
        Binding("k", "move_up", "Move Up ↑"),
        Binding("up", "move_up", "Move Up", show=False),
        Binding("j", "move_down", "Move Down ↓"),
        Binding("down", "move_down", "Move Down", show=False),
    ]

    def __init__(self, rules_dir: Path) -> None:
        super().__init__()
        self.rules_dir = rules_dir
        self.order_manager = OrderManager(rules_dir)
        self.current_directory = "community"
        self.directories = ["community", "team"]
        self.level_names = {
            "community": "Level 2",
            "team": "Level 3",
        }
        self.status_message = ""

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal():
            for directory in self.directories:
                rules = self.order_manager.order.get(directory, [])
                is_active = directory == self.current_directory
                yield DirectoryPanel(
                    directory,
                    self.level_names[directory],
                    rules,
                    is_active,
                )
        yield Static("", id="status", classes="hidden")
        yield Footer()

    def on_mount(self) -> None:
        """Focus the first active list."""
        self._focus_current_list()

    def _focus_current_list(self) -> None:
        """Focus the list for the current directory."""
        list_view = self.query_one(f"#list-{self.current_directory}", ListView)
        list_view.focus()

    def _update_panel_styles(self) -> None:
        """Update which panel is highlighted as active."""
        for directory in self.directories:
            panel = self.query_one(f"DirectoryPanel", DirectoryPanel)
            # Find the right panel
            for p in self.query(DirectoryPanel):
                if p.directory == directory:
                    if directory == self.current_directory:
                        p.add_class("active")
                    else:
                        p.remove_class("active")

    def _refresh_lists(self) -> None:
        """Refresh all list views with current order."""
        for directory in self.directories:
            try:
                list_view = self.query_one(f"#list-{directory}", ListView)
                rules = self.order_manager.order.get(directory, [])
                list_view.clear()
                for i, rule in enumerate(rules):
                    list_view.append(RuleItem(rule, i))
            except Exception:
                pass  # List might not exist if empty

    def _show_status(self, message: str) -> None:
        """Show a status message briefly."""
        status = self.query_one("#status", Static)
        status.update(message)
        status.remove_class("hidden")
        self.set_timer(1.5, self._hide_status)

    def _hide_status(self) -> None:
        """Hide the status message."""
        status = self.query_one("#status", Static)
        status.add_class("hidden")

    def action_quit(self) -> None:
        """Save and quit."""
        self.order_manager.save()
        self.exit()

    def action_select_community(self) -> None:
        """Select the community directory."""
        self._select_directory("community")

    def action_select_team(self) -> None:
        """Select the team directory."""
        self._select_directory("team")

    def _select_directory(self, directory: str) -> None:
        """Select a directory and focus its list."""
        self.current_directory = directory
        self._update_panel_styles()
        try:
            self._focus_current_list()
        except Exception:
            pass  # List might not exist if empty

    def action_move_up(self) -> None:
        """Move the selected rule up (lower priority)."""
        self._move_rule("up")

    def action_move_down(self) -> None:
        """Move the selected rule down (higher priority)."""
        self._move_rule("down")

    def _move_rule(self, direction: str) -> None:
        """Move the currently selected rule."""
        try:
            list_view = self.query_one(f"#list-{self.current_directory}", ListView)
            if list_view.highlighted_child is None:
                return

            item = list_view.highlighted_child
            if not isinstance(item, RuleItem):
                return

            rule_name = item.rule_name
            current_index = list_view.index

            if direction == "up":
                success = self.order_manager.move_up(self.current_directory, rule_name)
                new_index = current_index - 1 if success else current_index
                msg = f"↑ Moved '{rule_name}' up (lower priority)"
            else:
                success = self.order_manager.move_down(self.current_directory, rule_name)
                new_index = current_index + 1 if success else current_index
                msg = f"↓ Moved '{rule_name}' down (higher priority)"

            if success:
                self._refresh_lists()
                list_view.index = new_index
                self._show_status(msg)

        except Exception:
            pass


def run_order_tui(rules_dir: Path) -> None:
    """Run the order TUI application."""
    app = OrderApp(rules_dir)
    app.run()
