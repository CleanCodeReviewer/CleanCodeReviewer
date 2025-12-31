"""Textual TUI for project initialization."""

from __future__ import annotations

import shutil
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


PROMPT_OPTIONS = [
    ("claude", "CLAUDE.md (Claude Code)"),
    ("cursor", ".cursorrules (Cursor IDE)"),
]


def _is_claude_code_installed() -> bool:
    """Check if Claude Code CLI is installed."""
    # Check if 'claude' command exists in PATH
    if shutil.which("claude"):
        return True

    # Check if ~/.claude directory exists (Claude Code config dir)
    claude_dir = Path.home() / ".claude"
    if claude_dir.exists():
        return True

    return False


@dataclass
class InitResult:
    """Result from the init TUI."""

    prompt_files: list[str]
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
        width: 60;
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

    .section-title {
        text-style: bold;
        margin-top: 1;
        margin-bottom: 0;
    }

    .hook-info {
        color: $text-muted;
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
                yield Static("CCR Initialization", classes="title")

                # Hook info section (only if Claude Code is installed)
                if _is_claude_code_installed():
                    yield Static("Claude Code Hook", classes="section-title")
                    yield Static(
                        "✓ Will install hook in .claude/settings.json\n"
                        "  CCR runs automatically after Edit/Write",
                        classes="hook-info",
                    )

                # Prompt files section
                yield Static("Prompt Files (optional)", classes="section-title")
                yield SelectionList[str](
                    *[Selection(label, value, False) for value, label in PROMPT_OPTIONS],
                    id="prompt-list",
                )
                with Container(id="buttons"):
                    yield Button("Continue", variant="primary", id="btn-continue")
                    yield Button("Cancel", variant="default", id="btn-cancel")
        yield Footer()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "btn-continue":
            self.action_continue()
        elif event.button.id == "btn-cancel":
            self.action_cancel()

    def action_continue(self) -> None:
        """Continue with selected options."""
        selection_list = self.query_one("#prompt-list", SelectionList)
        selected = list(selection_list.selected)
        self.exit(InitResult(prompt_files=selected, cancelled=False))

    def action_cancel(self) -> None:
        """Cancel initialization."""
        self.exit(InitResult(prompt_files=[], cancelled=True))


def run_init_tui(project_path: Path) -> InitResult:
    """Run the init TUI application."""
    app = InitApp(project_path)
    result = app.run()
    if result is None:
        return InitResult(prompt_files=[], cancelled=True)
    return result
