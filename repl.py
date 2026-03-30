"""
repl.py — Full interactive REPL experience matching Claude CLI.

Features:
- prompt_toolkit for rich input (history, multiline, shortcuts)
- Streaming token-by-token output with markdown rendering
- Slash commands: /clear /history /save /model /help /exit
- Persistent input history (arrow keys work across sessions)
- Clean visual separation between turns
"""

import sys
from pathlib import Path
from typing import Optional

from prompt_toolkit import PromptSession
from prompt_toolkit.history import FileHistory
from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
from prompt_toolkit.formatted_text import HTML
from prompt_toolkit.styles import Style
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.filters import is_done

from rich.console import Console
from rich.markdown import Markdown
from rich.rule import Rule
from rich.text import Text
from rich import box
from rich.panel import Panel

# ── Constants ────────────────────────────────────────────────────────────────

PROMPT_HISTORY_FILE = Path.home() / ".openai" / "input_history"
PROMPT_HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)

SLASH_COMMANDS = {
    "/help":    "Show available commands",
    "/clear":   "Clear conversation history",
    "/history": "Print conversation history",
    "/save":    "Save history to disk",
    "/model":   "Show or switch model  e.g. /model gpt-4-turbo",
    "/exit":    "Exit the session",
}

PROMPT_STYLE = Style.from_dict({
    "prompt":       "#a8ff78 bold",
    "prompt.arrow": "#a8ff78",
})

# ── Key bindings ──────────────────────────────────────────────────────────────

def make_bindings() -> KeyBindings:
    kb = KeyBindings()

    # Enter submits; Alt+Enter / Meta+Enter inserts newline
    @kb.add("enter")
    def _submit(event):
        buf = event.app.current_buffer
        if buf.text.strip():
            buf.validate_and_handle()
        else:
            buf.insert_text("\n")

    @kb.add("escape", "enter")  # Alt+Enter
    def _newline(event):
        event.app.current_buffer.insert_text("\n")

    return kb


# ── REPL class ────────────────────────────────────────────────────────────────

class InteractiveREPL:
    """
    Claude CLI-style interactive session.
    """

    def __init__(self, client, memory, console: Console, initial_model: str):
        self.client = client
        self.memory = memory
        self.console = console
        self.model = initial_model
        self.history: list[dict] = []

        self._session = PromptSession(
            history=FileHistory(str(PROMPT_HISTORY_FILE)),
            auto_suggest=AutoSuggestFromHistory(),
            key_bindings=make_bindings(),
            style=PROMPT_STYLE,
            multiline=False,
            wrap_lines=True,
            enable_history_search=True,
        )

    # ── Public entry point ────────────────────────────────────────────────────

    def run(self, load_history: bool = False, stdin_prefix: Optional[str] = None):
        self._print_banner()

        if load_history:
            self.history = self.memory.load()
            if self.history:
                turns = sum(1 for m in self.history if m["role"] == "user")
                self._info(f"Resuming session — {turns} previous turn(s). Type [bold]/history[/bold] to review.")

        first = True
        while True:
            try:
                raw = self._get_input()
            except (KeyboardInterrupt, EOFError):
                self._goodbye()
                break

            if raw is None:
                continue

            text = raw.strip()
            if not text:
                continue

            # Slash commands
            if text.startswith("/"):
                if self._handle_command(text):
                    break  # /exit
                continue

            # Prepend piped stdin on first turn
            if first and stdin_prefix:
                text = f"{stdin_prefix}\n\n{text}"
            first = False

            self._send(text)

    # ── Input ─────────────────────────────────────────────────────────────────

    def _get_input(self) -> Optional[str]:
        try:
            return self._session.prompt(
                HTML("<prompt>❯ </prompt>"),
                style=PROMPT_STYLE,
            )
        except KeyboardInterrupt:
            # Ctrl+C clears the line, doesn't exit
            self.console.print()
            return None

    # ── Sending a message ─────────────────────────────────────────────────────

    def _send(self, text: str):
        from utils import detect_content_type

        self.history.append({"role": "user", "content": text})
        content_type = detect_content_type(text)

        self.console.print()  # breathing room before response

        response = self.client.chat(
            messages=self.history,
            stream=True,
            content_hint=content_type,
        )

        if response:
            self.history.append({"role": "assistant", "content": response})
            self.memory.save(self.history)

        self.console.print()  # breathing room after response

    # ── Slash commands ────────────────────────────────────────────────────────

    def _handle_command(self, text: str) -> bool:
        """Returns True if the REPL should exit."""
        parts = text.split(maxsplit=1)
        cmd = parts[0].lower()
        arg = parts[1].strip() if len(parts) > 1 else ""

        if cmd in ("/exit", "/quit", "/q"):
            self._goodbye()
            return True

        elif cmd == "/clear":
            self.history.clear()
            self._info("Conversation cleared.")

        elif cmd == "/history":
            self.memory.print_history(self.console, self.history)

        elif cmd == "/save":
            self.memory.save(self.history)
            self._info(f"Saved to [bold]{self.memory.history_path}[/bold]")

        elif cmd == "/model":
            if arg:
                self.client.model = arg
                self.model = arg
                self._info(f"Model switched to [bold]{arg}[/bold]")
            else:
                self._info(f"Current model: [bold]{self.client.model}[/bold]")

        elif cmd == "/help":
            self._print_help()

        else:
            self._warn(f"Unknown command [bold]{cmd}[/bold]. Type [bold]/help[/bold].")

        return False

    # ── UI helpers ────────────────────────────────────────────────────────────

    def _print_banner(self):
        self.console.print()
        self.console.print(
            Panel(
                f"[bold green]OpenAI CLI[/bold green]  [dim]·  model: {self.model}[/dim]\n"
                "[dim]Type a message to start. [bold]/help[/bold] for commands.  "
                "[bold]Ctrl+C[/bold] or [bold]/exit[/bold] to quit.[/dim]",
                border_style="green",
                box=box.ROUNDED,
                padding=(0, 2),
            )
        )
        self.console.print()

    def _print_help(self):
        rows = "\n".join(
            f"  [bold green]{cmd:<12}[/bold green] [dim]{desc}[/dim]"
            for cmd, desc in SLASH_COMMANDS.items()
        )
        self.console.print(
            Panel(
                rows,
                title="[bold]Commands[/bold]",
                border_style="blue",
                box=box.ROUNDED,
                padding=(0, 1),
            )
        )

    def _info(self, msg: str):
        self.console.print(f"  [dim]✓  {msg}[/dim]\n")

    def _warn(self, msg: str):
        self.console.print(f"  [yellow]⚠  {msg}[/yellow]\n")

    def _goodbye(self):
        self.console.print()
        self.console.print(Rule("[dim]Bye![/dim]", style="dim"))
        self.console.print()
