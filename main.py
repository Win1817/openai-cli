#!/usr/bin/env python3
"""
openai-cli — A production-ready OpenAI terminal CLI.
Mirrors the Claude CLI experience with streaming, memory, and rich output.
"""

import sys
import select
import logging
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console

from client import OpenAIClient
from ui import UI
from memory import ConversationMemory
from utils import detect_content_type, build_prompt, read_file_content

app = typer.Typer(
    name="openai",
    help="A developer-grade OpenAI CLI — conversational, streaming, and file-aware.",
    add_completion=True,
    rich_markup_mode="rich",
)
console = Console()


@app.command()
def main(
    prompt: Optional[str] = typer.Argument(None, help="Prompt to send to the model"),
    interactive: bool = typer.Option(False, "-i", "--interactive", help="Launch interactive chat session"),
    file: Optional[Path] = typer.Option(None, "-f", "--file", help="Include file content in prompt", exists=True, readable=True),
    no_stream: bool = typer.Option(False, "--no-stream", help="Disable streaming output"),
    model: str = typer.Option("gpt-4o", "--model", help="Model to use (default: gpt-4o)"),
    load_history: bool = typer.Option(False, "--history", help="Load previous conversation history"),
    debug: bool = typer.Option(False, "--debug", help="Enable verbose debug logging"),
    version: bool = typer.Option(False, "--version", help="Show version and exit"),
):
    """
    [bold green]openai[/bold green] — Chat with OpenAI from your terminal.

    \b
    Examples:
      openai "Explain Kubernetes ingress"
      cat logs.txt | openai "Summarize errors"
      openai -i
      openai -f config.yaml "Explain this"
    """
    if version:
        console.print("[bold]openai-cli[/bold] v1.0.0")
        raise typer.Exit()

    if debug:
        logging.basicConfig(level=logging.DEBUG, format="%(levelname)s: %(message)s")

    ui = UI(console)
    memory = ConversationMemory()
    client = OpenAIClient(model=model, ui=ui)

    # Load history if requested
    history = []
    if load_history:
        history = memory.load()
        if history:
            ui.info(f"Loaded {len(history) // 2} previous exchanges from history.")

    # Check for piped stdin
    stdin_content = None
    if not sys.stdin.isatty():
        try:
            stdin_content = sys.stdin.read().strip()
        except Exception:
            pass

    # Interactive mode
    if interactive:
        _run_interactive(client, ui, memory, history, stdin_content, no_stream)
        return

    # One-shot mode
    if not prompt and not stdin_content:
        ui.error("No prompt provided. Use [bold]openai --help[/bold] for usage.")
        raise typer.Exit(code=1)

    # Read file if provided
    file_content = None
    if file:
        file_content = read_file_content(file, ui)
        if file_content is None:
            raise typer.Exit(code=1)

    full_prompt = build_prompt(prompt, stdin_content, file_content)
    content_type = detect_content_type(full_prompt)

    if debug:
        logging.debug(f"Detected content type: {content_type}")
        logging.debug(f"Model: {model}")
        logging.debug(f"Prompt length: {len(full_prompt)} chars")

    history.append({"role": "user", "content": full_prompt})

    ui.print_user(prompt or "(stdin)")

    response = client.chat(
        messages=history,
        stream=not no_stream,
        content_hint=content_type,
    )

    history.append({"role": "assistant", "content": response})
    memory.save(history)


def _run_interactive(client, ui, memory, history, initial_stdin, no_stream):
    """Run the persistent interactive chat loop."""
    ui.print_banner()

    if initial_stdin:
        ui.info("Stdin content will be prepended to your first message.")

    first_turn = True

    while True:
        try:
            user_input = ui.prompt_user()
        except (KeyboardInterrupt, EOFError):
            ui.goodbye()
            break

        if not user_input:
            continue

        cmd = user_input.strip().lower()
        if cmd in ("exit", "quit", "bye", ":q"):
            ui.goodbye()
            break
        if cmd in ("clear", "/clear"):
            history.clear()
            ui.info("Conversation history cleared.")
            continue
        if cmd in ("history", "/history"):
            memory.print_history(console, history)
            continue
        if cmd in ("save", "/save"):
            memory.save(history)
            ui.info(f"History saved to [bold]{memory.history_path}[/bold]")
            continue
        if cmd in ("help", "/help"):
            ui.print_help()
            continue

        # Prepend stdin to first turn
        full_input = user_input
        if first_turn and initial_stdin:
            full_input = build_prompt(user_input, initial_stdin, None)
            first_turn = False

        content_type = detect_content_type(full_input)
        history.append({"role": "user", "content": full_input})

        response = client.chat(
            messages=history,
            stream=not no_stream,
            content_hint=content_type,
        )

        if response:
            history.append({"role": "assistant", "content": response})
            memory.save(history)


if __name__ == "__main__":
    app()
