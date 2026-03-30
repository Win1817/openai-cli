"""
ui.py — Rich-powered terminal output, prompts, and indicators.
"""

from contextlib import contextmanager
from typing import Callable

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.prompt import Prompt
from rich.spinner import Spinner
from rich.live import Live
from rich.text import Text
from rich.rule import Rule
from rich import box


BANNER = """[bold green]
  ██████╗ ██████╗ ███████╗███╗   ██╗ █████╗ ██╗
 ██╔═══██╗██╔══██╗██╔════╝████╗  ██║██╔══██╗██║
 ██║   ██║██████╔╝█████╗  ██╔██╗ ██║███████║██║
 ██║   ██║██╔═══╝ ██╔══╝  ██║╚██╗██║██╔══██║██║
 ╚██████╔╝██║     ███████╗██║ ╚████║██║  ██║██║
  ╚═════╝ ╚═╝     ╚══════╝╚═╝  ╚═══╝╚═╝  ╚═╝╚═╝
[/bold green]"""

HELP_TEXT = """
[bold]Commands:[/bold]
  [green]exit[/green], [green]quit[/green], [green]:q[/green]  — End the session
  [green]clear[/green]          — Clear conversation history
  [green]history[/green]        — Show current session history
  [green]save[/green]           — Save history to disk
  [green]help[/green]           — Show this help

[bold]Tips:[/bold]
  • Paste code, YAML, or logs — the model adapts its response style
  • Ctrl+C exits gracefully
"""


class StreamPrinter:
    """Accumulates streamed tokens and prints them to the terminal."""

    def __init__(self, console: Console):
        self.console = console
        self._buffer = []
        self._started = False

    def print_token(self, token: str):
        if not self._started:
            self.console.print()
            self.console.print("[bold cyan]◆ Assistant[/bold cyan]")
            self._started = True
        self.console.print(token, end="", markup=False, highlight=False)
        self._buffer.append(token)

    def finish(self):
        if self._started:
            self.console.print("\n")


class UI:
    def __init__(self, console: Console):
        self.console = console

    def print_banner(self):
        self.console.print(BANNER)
        self.console.print(
            Panel(
                "[dim]Type your message and press Enter. Type [bold]help[/bold] for commands.[/dim]",
                border_style="green",
                box=box.ROUNDED,
                padding=(0, 2),
            )
        )
        self.console.print()

    def print_user(self, text: str):
        self.console.print(f"\n[bold yellow]▶ You[/bold yellow]")
        self.console.print(f"[yellow]{text}[/yellow]\n")

    def print_ai(self, text: str):
        """Print full response (non-streaming) as markdown."""
        self.console.print()
        self.console.print("[bold cyan]◆ Assistant[/bold cyan]")
        self.console.print(Markdown(text))
        self.console.print()

    def prompt_user(self) -> str:
        """Show the interactive input prompt."""
        self.console.print("[bold yellow]▶ You[/bold yellow]", end=" ")
        try:
            return input()
        except EOFError:
            return "exit"

    @contextmanager
    def ai_response_context(self):
        """
        Context manager yielding a callable that prints tokens.
        Handles the start/end formatting around the streamed response.
        """
        printer = StreamPrinter(self.console)
        try:
            yield printer.print_token
        finally:
            printer.finish()

    @contextmanager
    def spinner(self, message: str = "Thinking..."):
        """Context manager showing a spinner while blocking."""
        with Live(
            Spinner("dots", text=f"[dim]{message}[/dim]"),
            console=self.console,
            transient=True,
        ):
            yield

    def info(self, message: str):
        self.console.print(f"[dim]ℹ  {message}[/dim]")

    def error(self, message: str):
        self.console.print(
            Panel(
                f"[bold red]Error:[/bold red] {message}",
                border_style="red",
                box=box.ROUNDED,
                padding=(0, 2),
            )
        )

    def goodbye(self):
        self.console.print()
        self.console.print(Rule("[dim]Session ended[/dim]", style="dim"))
        self.console.print()

    def print_help(self):
        self.console.print(
            Panel(
                HELP_TEXT,
                title="[bold]Help[/bold]",
                border_style="blue",
                box=box.ROUNDED,
                padding=(0, 2),
            )
        )
