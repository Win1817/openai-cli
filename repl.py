"""
repl.py — Full interactive REPL experience matching Claude CLI.

Features:
- prompt_toolkit for rich input (history, multiline, shortcuts)
- Streaming token-by-token output with markdown rendering
- Slash commands: /clear /history /save /model /models /help /exit
- /models fetches live model list from API and shows an interactive picker
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

from rich.console import Console
from rich.markdown import Markdown
from rich.rule import Rule
from rich.table import Table
from rich import box
from rich.panel import Panel

# ── Constants ─────────────────────────────────────────────────────────────────

PROMPT_HISTORY_FILE = Path.home() / ".openai" / "input_history"
PROMPT_HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)

SLASH_COMMANDS = {
    "/help":    "Show available commands",
    "/clear":   "Clear conversation history",
    "/history": "Print conversation history",
    "/save":    "Save history to disk",
    "/models":  "Browse and select from available models",
    "/model":   "Show current model or switch  e.g. /model gpt-4o",
    "/exit":    "Exit the session",
}

# Models to surface first in the picker (in order)
PREFERRED_MODELS = [
    "gpt-4o",
    "gpt-4o-mini",
    "gpt-4-turbo",
    "gpt-4",
    "gpt-3.5-turbo",
    "o1",
    "o1-mini",
    "o3-mini",
]

PROMPT_STYLE = Style.from_dict({
    "prompt":       "#a8ff78 bold",
    "prompt.arrow": "#a8ff78",
})

# ── Key bindings ──────────────────────────────────────────────────────────────

def make_bindings() -> KeyBindings:
    kb = KeyBindings()

    @kb.add("enter")
    def _submit(event):
        buf = event.app.current_buffer
        if buf.text.strip():
            buf.validate_and_handle()
        else:
            buf.insert_text("\n")

    @kb.add("escape", "enter")
    def _newline(event):
        event.app.current_buffer.insert_text("\n")

    return kb


# ── Model fetching ────────────────────────────────────────────────────────────

def fetch_models(client) -> list[dict]:
    """
    Fetch available models from the OpenAI API.
    Returns a sorted list of dicts: {id, owned_by, type}
    GPT and O-series chat models are prioritised; fine-tunes and embeddings filtered out.
    """
    try:
        response = client._client.models.list()
        all_models = [m for m in response.data]

        # Keep only chat-relevant models
        def is_chat_model(m) -> bool:
            mid = m.id.lower()
            if any(x in mid for x in ("embed", "tts", "whisper", "dall-e", "babbage", "davinci", "ada", "curie")):
                return False
            if any(mid.startswith(p) for p in ("gpt-", "o1", "o3", "o4", "chatgpt")):
                return True
            return False

        chat_models = [m for m in all_models if is_chat_model(m)]

        # Sort: preferred first, then alphabetical
        def sort_key(m):
            mid = m.id
            try:
                return (0, PREFERRED_MODELS.index(mid))
            except ValueError:
                return (1, mid)

        chat_models.sort(key=sort_key)

        return [{"id": m.id, "owned_by": getattr(m, "owned_by", "openai")} for m in chat_models]

    except Exception as e:
        return []


# ── Interactive model picker ──────────────────────────────────────────────────

def pick_model(models: list[dict], current: str, console: Console) -> Optional[str]:
    """
    Render a numbered table of models and let the user pick one by number.
    Returns the chosen model ID, or None if cancelled.
    """
    if not models:
        console.print("  [yellow]⚠  Could not fetch model list from API.[/yellow]\n")
        return None

    table = Table(
        box=box.SIMPLE_HEAVY,
        border_style="dim",
        show_header=True,
        header_style="bold green",
        padding=(0, 1),
    )
    table.add_column("#",        style="dim",        width=4,  justify="right")
    table.add_column("Model",    style="bold white",  min_width=28)
    table.add_column("Owner",    style="dim",         min_width=10)
    table.add_column("",        width=8)   # active marker

    for i, m in enumerate(models, 1):
        active = "[bold green]← active[/bold green]" if m["id"] == current else ""
        table.add_row(str(i), m["id"], m["owned_by"], active)

    console.print()
    console.print(
        Panel(
            table,
            title="[bold]Available Models[/bold]",
            border_style="green",
            box=box.ROUNDED,
            padding=(0, 1),
        )
    )
    console.print("  [dim]Enter a number to switch, or press Enter to keep current.[/dim]\n")

    try:
        raw = input("  Select model: ").strip()
    except (EOFError, KeyboardInterrupt):
        return None

    if not raw:
        return None

    try:
        idx = int(raw)
        if 1 <= idx <= len(models):
            return models[idx - 1]["id"]
        else:
            console.print(f"  [yellow]⚠  Out of range — enter 1–{len(models)}.[/yellow]\n")
            return None
    except ValueError:
        # Maybe they typed a model name directly
        ids = [m["id"] for m in models]
        if raw in ids:
            return raw
        console.print(f"  [yellow]⚠  '{raw}' not recognised. Enter a number or exact model ID.[/yellow]\n")
        return None


# ── REPL class ────────────────────────────────────────────────────────────────

class InteractiveREPL:
    """Claude CLI-style interactive session."""

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

            if text.startswith("/"):
                if self._handle_command(text):
                    break
                continue

            if first and stdin_prefix:
                text = f"{stdin_prefix}\n\n{text}"
            first = False

            self._send(text)

    # ── Input ─────────────────────────────────────────────────────────────────

    def _get_input(self) -> Optional[str]:
        # Rebuild prompt each time so model name stays current
        prompt_html = (
            f"<prompt>❯ </prompt>"
        )
        try:
            return self._session.prompt(
                HTML(prompt_html),
                style=PROMPT_STYLE,
            )
        except KeyboardInterrupt:
            self.console.print()
            return None

    # ── Sending a message ─────────────────────────────────────────────────────

    def _send(self, text: str):
        from utils import detect_content_type

        self.history.append({"role": "user", "content": text})
        content_type = detect_content_type(text)

        self.console.print()

        response = self.client.chat(
            messages=self.history,
            stream=True,
            content_hint=content_type,
        )

        if response:
            self.history.append({"role": "assistant", "content": response})
            self.memory.save(self.history)

        self.console.print()

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

        elif cmd == "/models":
            self._select_model()

        elif cmd == "/model":
            if arg:
                self._switch_model(arg)
            else:
                self._info(f"Current model: [bold]{self.client.model}[/bold]  [dim](use /models to browse)[/dim]")

        elif cmd == "/help":
            self._print_help()

        else:
            self._warn(f"Unknown command [bold]{cmd}[/bold]. Type [bold]/help[/bold].")

        return False

    # ── Model selector ────────────────────────────────────────────────────────

    def _select_model(self):
        """Fetch models from API and show interactive picker."""
        self.console.print()
        self.console.print("  [dim]Fetching available models…[/dim]")

        models = fetch_models(self.client)

        if not models:
            self._warn("Could not fetch models. Check your API key and connection.")
            return

        chosen = pick_model(models, self.client.model, self.console)

        if chosen and chosen != self.client.model:
            self._switch_model(chosen)
        elif chosen == self.client.model:
            self._info(f"Already using [bold]{chosen}[/bold].")
        else:
            self._info("No change.")

    def _switch_model(self, model_id: str):
        self.client.model = model_id
        self.model = model_id
        self._info(f"Switched to [bold green]{model_id}[/bold green]")
        # Update banner hint on next prompt — reprint a compact notice
        self.console.print(
            f"  [dim]Tip: conversation history carries over to the new model.[/dim]\n"
        )

    # ── UI helpers ────────────────────────────────────────────────────────────

    def _print_banner(self):
        self.console.print()
        self.console.print(
            Panel(
                f"[bold green]OpenAI CLI[/bold green]  [dim]·  model: {self.model}[/dim]\n"
                "[dim]Type a message to start. "
                "[bold]/help[/bold] for commands.  "
                "[bold]/models[/bold] to switch model.  "
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
