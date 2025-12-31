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
    Label,
    Static,
)


# Available languages and their rule mappings
AVAILABLE_LANGUAGES: dict[str, list[str]] = {
    "Python": ["google/python"],
    "JavaScript": ["airbnb/javascript"],
    "TypeScript": ["airbnb/javascript"],
    "React": ["airbnb/react"],
    "Go": ["google/go", "uber/go"],
    "Java": ["google/java"],
    "C++": ["google/cpp"],
    "C#": ["microsoft/csharp"],
    "Swift": ["google/swift"],
    "Shell": ["google/shell"],
}

AGENT_OPTIONS = [
    ("claude", "CLAUDE.md", "For Claude Code"),
    ("cursor", ".cursorrules", "For Cursor IDE"),
]


@dataclass
class InitResult:
    """Result from the init TUI."""

    languages: list[str]
    agent_files: list[str]  # "claude", "cursor", or both
    cancelled: bool = False


class InitApp(App[InitResult]):
    """Textual app for project initialization."""

    CSS = """
    Screen {
        align: center middle;
    }

    #main-container {
        width: 60;
        height: auto;
        max-height: 90%;
        border: solid $accent;
        padding: 1 2;
    }

    .section-title {
        text-style: bold;
        margin-bottom: 1;
        color: $text;
    }

    .section-subtitle {
        color: $text-muted;
        margin-bottom: 1;
    }

    #languages-container {
        height: auto;
        max-height: 12;
        margin-bottom: 1;
        padding: 0 1;
    }

    #agents-container {
        height: auto;
        margin-bottom: 1;
        padding: 0 1;
    }

    Checkbox {
        margin: 0;
        padding: 0;
        height: 1;
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
    ]

    def __init__(self, project_path: Path) -> None:
        super().__init__()
        self.project_path = project_path
        self.selected_languages: set[str] = set()
        self.selected_agents: set[str] = set()

    def compose(self) -> ComposeResult:
        yield Header()
        with Container(id="main-container"):
            yield Static("Select Languages", classes="section-title")
            yield Static("Choose languages used in this project:", classes="section-subtitle")
            with Vertical(id="languages-container"):
                for lang in AVAILABLE_LANGUAGES:
                    # Sanitize ID: replace invalid chars with underscores
                    safe_id = lang.lower().replace("+", "plus").replace("#", "sharp")
                    yield Checkbox(lang, id=f"lang-{safe_id}")

            yield Static("Agent Integration", classes="section-title")
            yield Static("Create config files for AI assistants:", classes="section-subtitle")
            with Vertical(id="agents-container"):
                for agent_id, filename, description in AGENT_OPTIONS:
                    label = f"{filename} ({description})"
                    yield Checkbox(label, id=f"agent-{agent_id}")

            with Container(id="buttons"):
                yield Button("Continue", variant="primary", id="btn-continue")
                yield Button("Skip", variant="default", id="btn-skip")

            yield Static("Press Enter to continue, Esc to cancel", id="status")
        yield Footer()

    def _sanitize_id(self, name: str) -> str:
        """Sanitize a name for use as widget ID."""
        return name.lower().replace("+", "plus").replace("#", "sharp")

    def on_checkbox_changed(self, event: Checkbox.Changed) -> None:
        """Handle checkbox state changes."""
        checkbox_id = event.checkbox.id or ""

        if checkbox_id.startswith("lang-"):
            lang_id = checkbox_id.replace("lang-", "")
            # Find the actual language name by matching sanitized ID
            for full_lang in AVAILABLE_LANGUAGES:
                if self._sanitize_id(full_lang) == lang_id:
                    if event.value:
                        self.selected_languages.add(full_lang)
                    else:
                        self.selected_languages.discard(full_lang)
                    break

        elif checkbox_id.startswith("agent-"):
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
            # Skip with empty selections
            self.exit(
                InitResult(
                    languages=[],
                    agent_files=[],
                    cancelled=False,
                )
            )

    def action_continue(self) -> None:
        """Continue with selected options."""
        self.exit(
            InitResult(
                languages=list(self.selected_languages),
                agent_files=list(self.selected_agents),
                cancelled=False,
            )
        )

    def action_cancel(self) -> None:
        """Cancel initialization."""
        self.exit(
            InitResult(
                languages=[],
                agent_files=[],
                cancelled=True,
            )
        )


def run_init_tui(project_path: Path) -> InitResult:
    """Run the init TUI application."""
    app = InitApp(project_path)
    result = app.run()
    if result is None:
        return InitResult(languages=[], agent_files=[], cancelled=True)
    return result
