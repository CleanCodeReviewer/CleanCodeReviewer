"""Textual TUI for project initialization."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Vertical
from textual.widgets import (
    Button,
    Checkbox,
    Footer,
    Header,
    Static,
)


AGENT_OPTIONS = [
    ("claude", "CLAUDE.md", "For Claude Code"),
    ("cursor", ".cursorrules", "For Cursor IDE"),
]


@dataclass
class InitResult:
    """Result from the init TUI."""

    agent_files: list[str]  # "claude", "cursor", or both
    cancelled: bool = False


class InitApp(App[InitResult]):
    """Textual app for project initialization."""

    CSS = """
    Screen {
        align: center middle;
    }

    #main-container {
        width: 50;
        height: auto;
        border: solid $accent;
        padding: 1 2;
    }

    .section-title {
        text-style: bold;
        margin-bottom: 1;
    }

    .section-subtitle {
        color: $text-muted;
        margin-bottom: 1;
    }

    #agents-container {
        height: auto;
        margin-bottom: 1;
    }

    Checkbox {
        height: 3;
        padding: 1;
    }

    Checkbox:focus {
        background: $accent 20%;
    }

    #buttons {
        height: 3;
        align: center middle;
        margin-top: 1;
    }

    Button {
        margin: 0 1;
    }

    #status {
        height: 1;
        text-align: center;
        color: $text-muted;
        margin-top: 1;
    }
    """

    BINDINGS = [
        Binding("enter", "continue", "Continue"),
        Binding("escape", "cancel", "Cancel"),
        Binding("q", "cancel", "Cancel", show=False),
        Binding("j", "focus_next", "Next", show=False),
        Binding("k", "focus_previous", "Previous", show=False),
        Binding("down", "focus_next", "Next"),
        Binding("up", "focus_previous", "Previous"),
        Binding("space", "toggle_checkbox", "Toggle", show=False),
    ]

    def __init__(self, project_path: Path) -> None:
        super().__init__()
        self.project_path = project_path
        self.selected_agents: set[str] = set()

    def compose(self) -> ComposeResult:
        yield Header()
        with Container(id="main-container"):
            yield Static("Agent Integration", classes="section-title")
            yield Static("Create config files for AI assistants:", classes="section-subtitle")
            with Vertical(id="agents-container"):
                for agent_id, filename, description in AGENT_OPTIONS:
                    label = f"{filename} ({description})"
                    yield Checkbox(label, value=False, id=f"agent-{agent_id}")

            with Container(id="buttons"):
                yield Button("Continue", variant="primary", id="btn-continue")
                yield Button("Skip", variant="default", id="btn-skip")

            yield Static("↑/↓ navigate, Space toggle, Enter continue", id="status")
        yield Footer()

    def on_checkbox_changed(self, event: Checkbox.Changed) -> None:
        """Handle checkbox state changes."""
        checkbox_id = event.checkbox.id or ""

        if checkbox_id.startswith("agent-"):
            agent = checkbox_id.replace("agent-", "")
            if event.value:
                self.selected_agents.add(agent)
            else:
                self.selected_agents.discard(agent)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "btn-continue":
            self.action_continue()
        elif event.button.id == "btn-skip":
            self.exit(InitResult(agent_files=[], cancelled=False))

    def action_continue(self) -> None:
        """Continue with selected options."""
        self.exit(InitResult(agent_files=list(self.selected_agents), cancelled=False))

    def action_cancel(self) -> None:
        """Cancel initialization."""
        self.exit(InitResult(agent_files=[], cancelled=True))

    def action_toggle_checkbox(self) -> None:
        """Toggle the currently focused checkbox."""
        focused = self.focused
        if isinstance(focused, Checkbox):
            focused.toggle()


def run_init_tui(project_path: Path) -> InitResult:
    """Run the init TUI application."""
    app = InitApp(project_path)
    result = app.run()
    if result is None:
        return InitResult(agent_files=[], cancelled=True)
    return result
