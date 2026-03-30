"""
client.py — OpenAI API wrapper.
Streaming output matches Claude CLI: tokens print live, then markdown is rendered.
"""

import logging
import os
from typing import Optional

from dotenv import load_dotenv
from rich.console import Console
from rich.markdown import Markdown

load_dotenv()
logger = logging.getLogger(__name__)

SYSTEM_PROMPTS = {
    "yaml": (
        "You are an expert DevOps and infrastructure engineer. "
        "The user is sharing YAML configuration. Analyze it carefully, explain what it does, "
        "identify any issues, and suggest improvements. Be concise and precise."
    ),
    "logs": (
        "You are a senior site reliability engineer. "
        "The user is sharing log output. Identify errors, warnings, patterns, and root causes. "
        "Lead with the most critical issues first."
    ),
    "code": (
        "You are a senior software engineer and code reviewer. "
        "Analyze the provided code. Explain what it does, spot bugs, suggest refactors, "
        "and flag security issues. Be specific and actionable."
    ),
    "json": (
        "You are a data engineer and API expert. "
        "The user is sharing JSON data. Explain its structure, identify anomalies, "
        "and answer questions about it."
    ),
    "default": (
        "You are a helpful, knowledgeable assistant for developers and engineers. "
        "Be concise, accurate, and direct. Prefer examples over abstract explanations. "
        "Format responses in markdown when it improves readability."
    ),
}


class OpenAIClient:
    def __init__(self, model: str = "gpt-4o", console: Optional[Console] = None):
        self.model = model
        self.console = console or Console()
        self._client = None
        self._init_client()

    def _init_client(self):
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            self.console.print(
                "\n[bold red]Error:[/bold red] [red]OPENAI_API_KEY not set.[/red]\n"
                "  Add it to [bold].env[/bold] or run:\n"
                "  [dim]export OPENAI_API_KEY=sk-...[/dim]\n"
            )
            raise SystemExit(1)

        try:
            from openai import OpenAI
            self._client = OpenAI(api_key=api_key)
        except ImportError:
            self.console.print("[red]openai package missing. Run: pip install openai[/red]")
            raise SystemExit(1)

    def chat(
        self,
        messages: list,
        stream: bool = True,
        content_hint: str = "default",
    ) -> Optional[str]:
        system_prompt = SYSTEM_PROMPTS.get(content_hint, SYSTEM_PROMPTS["default"])
        full_messages = [{"role": "system", "content": system_prompt}] + messages

        try:
            if stream:
                return self._stream(full_messages)
            else:
                return self._blocking(full_messages)
        except Exception as e:
            self._handle_error(e)
            return None

    def _stream(self, messages: list) -> str:
        """
        Stream tokens exactly like Claude CLI:
        - Tokens printed raw as they arrive (live typing effect)
        - After stream ends, re-render the full response as markdown
        """
        tokens: list[str] = []

        api_stream = self._client.chat.completions.create(
            model=self.model,
            messages=messages,
            stream=True,
        )

        for chunk in api_stream:
            delta = chunk.choices[0].delta
            if delta and delta.content:
                token = delta.content
                tokens.append(token)
                print(token, end="", flush=True)

        full_text = "".join(tokens)

        # Clear the raw stream, re-render cleanly as markdown
        print("\n")
        self.console.print(Markdown(full_text))

        return full_text

    def _blocking(self, messages: list) -> str:
        from rich.live import Live
        from rich.spinner import Spinner

        with Live(Spinner("dots", text="[dim]Thinking…[/dim]"), console=self.console, transient=True):
            resp = self._client.chat.completions.create(
                model=self.model,
                messages=messages,
                stream=False,
            )

        text = resp.choices[0].message.content
        self.console.print(Markdown(text))
        return text

    def _handle_error(self, error: Exception):
        try:
            from openai import AuthenticationError, RateLimitError, APIConnectionError, APIStatusError
            if isinstance(error, AuthenticationError):
                msg = "Authentication failed — check your [bold]OPENAI_API_KEY[/bold]."
            elif isinstance(error, RateLimitError):
                msg = "Rate limit hit. Please wait a moment and retry."
            elif isinstance(error, APIConnectionError):
                msg = "Cannot reach OpenAI API. Check your internet connection."
            elif isinstance(error, APIStatusError):
                msg = f"API error {error.status_code}: {error.message}"
            else:
                msg = f"{type(error).__name__}: {error}"
        except ImportError:
            msg = str(error)

        self.console.print(f"\n[bold red]Error:[/bold red] {msg}\n")
        logger.debug("API error", exc_info=True)
