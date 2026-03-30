#!/usr/bin/env python3
"""
openai-cli — A production-ready OpenAI terminal CLI.
Interactive by default, just like Claude CLI.
"""

import sys
import logging
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console

from client import OpenAIClient
from memory import ConversationMemory
from utils import detect_content_type, build_prompt, read_file_content

app = typer.Typer(
    name="openai",
    help="A developer-grade OpenAI CLI — interactive, streaming, and file-aware.",
    add_completion=True,
    rich_markup_mode="rich",
    invoke_without_command=True,
)

console = Console()


@app.command()
def main(
    prompt: Optional[str] = typer.Argument(None, help="One-shot prompt (skips interactive mode)"),
    file: Optional[Path] = typer.Option(None, "-f", "--file", help="Include file content in prompt"),
    no_stream: bool = typer.Option(False, "--no-stream", help="Disable streaming"),
    model: str = typer.Option("gpt-4o", "--model", help="Model to use"),
    history: bool = typer.Option(False, "--history", help="Resume previous session"),
    debug: bool = typer.Option(False, "--debug", help="Verbose debug logging"),
    version: bool = typer.Option(False, "--version", help="Show version"),
):
    """
    [bold green]openai[/bold green] — Chat with OpenAI from your terminal.

    \b
    Runs interactive mode by default (like Claude CLI).
    Pass a prompt argument for one-shot use.

    \b
    Examples:
      openai                          # interactive session
      openai "Explain K8s ingress"    # one-shot
      cat logs.txt | openai           # pipe into interactive
      openai -f deploy.yaml           # file + interactive
    """
    if version:
        console.print("[bold]openai-cli[/bold] v2.0.0")
        raise typer.Exit()

    if debug:
        logging.basicConfig(level=logging.DEBUG, format="%(levelname)s %(name)s: %(message)s")

    memory = ConversationMemory()
    client = OpenAIClient(model=model, console=console)

    # Read piped stdin (non-blocking check)
    stdin_content = None
    if not sys.stdin.isatty():
        try:
            stdin_content = sys.stdin.read().strip() or None
        except Exception:
            pass

    # Read file if provided
    file_content = None
    if file:
        file_content = read_file_content(file, _FakeUI(console))
        if file_content is None:
            raise typer.Exit(code=1)

    # ── One-shot mode: prompt given as argument ───────────────────────────────
    if prompt:
        full_prompt = build_prompt(prompt, stdin_content, file_content)
        content_type = detect_content_type(full_prompt)
        msgs = [{"role": "user", "content": full_prompt}]
        response = client.chat(messages=msgs, stream=not no_stream, content_hint=content_type)
        if response:
            memory.save(msgs + [{"role": "assistant", "content": response}])
        return

    # ── Interactive mode (default) ────────────────────────────────────────────
    # Attach stdin_content + file_content as context prefix if present
    prefix_parts = []
    if file_content:
        prefix_parts.append(file_content)
    if stdin_content:
        prefix_parts.append(stdin_content)
    prefix = "\n\n".join(prefix_parts) if prefix_parts else None

    from repl import InteractiveREPL
    repl = InteractiveREPL(
        client=client,
        memory=memory,
        console=console,
        initial_model=model,
    )
    repl.run(load_history=history, stdin_prefix=prefix)


class _FakeUI:
    """Minimal shim so read_file_content can call ui.error()."""
    def __init__(self, console):
        self._c = console
    def error(self, msg):
        self._c.print(f"[bold red]Error:[/bold red] {msg}")


if __name__ == "__main__":
    app()
