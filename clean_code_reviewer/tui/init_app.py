"""Textual TUI for project initialization."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container
from textual.widgets import (
    Button,
    Footer,
    Header,
    SelectionList,
    Static,
)
from textual.widgets.selection_list import Selection


AGENT_OPTIONS = [
    ("claude", "CLAUDE.md (Claude Code)"),
    ("cursor", ".cursorrules (Cursor IDE)"),
]


@dataclass
class InitResult:
    """Result from the init TUI."""

    agent_files: list[str]
    cancelled: bool = False


class InitApp(App[InitResult]):
    """Textual app for project initialization."""

    CSS = """
    #main-container {
        align: center middle;
        width: 100%;
        height: 100%;
    }

    #dialog {
        width: 50;
        height: auto;
        border: solid $accent;
        padding: 1 2;
        background: $surface;
    }

    .title {
        text-style: bold;
        text-align: center;
        width: 100%;
        margin-bottom: 1;
    }

    SelectionList {
        height: 6;
        margin-bottom: 1;
    }

    /* Hide the X when not selected, show when selected */
    SelectionList > .selection-list--button {
        color: transparent;
    }

    SelectionList > .selection-list--button-selected {
        color: $success;
    }

    SelectionList > .selection-list--button-highlighted {
        color: transparent;
    }

    SelectionList > .selection-list--button-selected-highlighted {
        color: $success;
    }

    #buttons {
        height: 3;
        align: center middle;
    }

    Button {
        margin: 0 1;
    }
    """

    BINDINGS = [
        Binding("enter", "continue", "Continue"),
        Binding("escape", "cancel", "Cancel"),
        Binding("q", "cancel", "Cancel", show=False),
    ]

    def __init__(self, project_path: Path) -> None:
        super().__init__()
        self.project_path = project_path

    def compose(self) -> ComposeResult:
        yield Header()
        with Container(id="main-container"):
            with Container(id="dialog"):
                yield Static("Create AI Assistant Config Files?", classes="title")
                yield SelectionList[str](
                    *[Selection(label, value, False) for value, label in AGENT_OPTIONS],
                    id="agent-list",
                )
                with Container(id="buttons"):
                    yield Button("Continue", variant="primary", id="btn-continue")
                    yield Button("Skip", variant="default", id="btn-skip")
        yield Footer()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "btn-continue":
            self.action_continue()
        elif event.button.id == "btn-skip":
            self.exit(InitResult(agent_files=[], cancelled=False))

    def action_continue(self) -> None:
        """Continue with selected options."""
        selection_list = self.query_one("#agent-list", SelectionList)
        selected = list(selection_list.selected)
        self.exit(InitResult(agent_files=selected, cancelled=False))

    def action_cancel(self) -> None:
        """Cancel initialization."""
        self.exit(InitResult(agent_files=[], cancelled=True))


def run_init_tui(project_path: Path) -> InitResult:
    """Run the init TUI application."""
    app = InitApp(project_path)
    result = app.run()
    if result is None:
        return InitResult(agent_files=[], cancelled=True)
    return result
