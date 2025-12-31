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

from clean_code_reviewer.utils.detection import (
    is_claude_code_installed,
    is_cursor_installed,
    is_gemini_cli_installed,
    project_uses_claude,
    project_uses_cursor,
    project_uses_gemini,
)


PROMPT_OPTIONS = [
    ("claude", "CLAUDE.md (Claude Code)"),
    ("cursor", ".cursorrules (Cursor IDE)"),
]


def _get_detected_targets_display(project_path: Path) -> list[str]:
    """Get list of AI coding assistants for display in TUI.

    Returns human-readable names for detected assistants.
    """
    targets = []
    if is_claude_code_installed() and project_uses_claude(project_path):
        targets.append("Claude Code")
    if is_gemini_cli_installed() and project_uses_gemini(project_path):
        targets.append("Gemini CLI")
    if is_cursor_installed() and project_uses_cursor(project_path):
        targets.append("Cursor IDE")
    return targets


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

                # Hook info section (show detected AI assistants)
                detected = _get_detected_targets_display(self.project_path)
                if detected:
                    yield Static("Hooks", classes="section-title")
                    hook_info = "✓ Will install hooks for:\n"
                    for target in detected:
                        hook_info += f"  • {target}\n"
                    hook_info += "  CCR reviews code after file edits"
                    yield Static(hook_info, classes="hook-info")

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
