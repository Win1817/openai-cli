"""
client.py — OpenAI API wrapper with streaming support.
"""

import logging
import os
from typing import Optional

from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

# System prompts keyed by content type
SYSTEM_PROMPTS = {
    "yaml": (
        "You are an expert DevOps and infrastructure engineer. "
        "The user is sharing YAML configuration. Analyze it carefully, explain what it does, "
        "identify any issues, and suggest improvements. Be concise and precise."
    ),
    "logs": (
        "You are a senior site reliability engineer. "
        "The user is sharing log output. Identify errors, warnings, patterns, and root causes. "
        "Be direct — lead with the most critical issues first."
    ),
    "code": (
        "You are a senior software engineer and code reviewer. "
        "Analyze the provided code thoroughly. Explain what it does, spot bugs, "
        "suggest refactors, and flag security issues. Be specific and actionable."
    ),
    "json": (
        "You are a data engineer and API expert. "
        "The user is sharing JSON data. Parse and explain its structure, "
        "identify anomalies, and answer questions about the data."
    ),
    "default": (
        "You are a helpful, knowledgeable assistant for developers and engineers. "
        "Be concise, accurate, and direct. Prefer examples over abstract explanations. "
        "Use markdown formatting when it improves readability."
    ),
}


class OpenAIClient:
    def __init__(self, model: str = "gpt-4o", ui=None):
        self.model = model
        self.ui = ui
        self._client = None
        self._init_client()

    def _init_client(self):
        """Initialize the OpenAI client with API key validation."""
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            if self.ui:
                self.ui.error(
                    "OPENAI_API_KEY not found.\n"
                    "  Set it in [bold].env[/bold] or export it:\n"
                    "  [dim]export OPENAI_API_KEY=sk-...[/dim]"
                )
            raise SystemExit(1)

        try:
            from openai import OpenAI
            self._client = OpenAI(api_key=api_key)
            logger.debug(f"OpenAI client initialized. Model: {self.model}")
        except ImportError:
            if self.ui:
                self.ui.error("openai package not installed. Run: [bold]pip install openai[/bold]")
            raise SystemExit(1)

    def _get_system_prompt(self, content_hint: str) -> str:
        return SYSTEM_PROMPTS.get(content_hint, SYSTEM_PROMPTS["default"])

    def chat(
        self,
        messages: list,
        stream: bool = True,
        content_hint: str = "default",
    ) -> Optional[str]:
        """
        Send messages to the OpenAI API.
        Returns the full response text.
        """
        system_prompt = self._get_system_prompt(content_hint)
        full_messages = [{"role": "system", "content": system_prompt}] + messages

        logger.debug(f"Sending {len(full_messages)} messages to {self.model} (stream={stream})")

        try:
            if stream:
                return self._stream_response(full_messages)
            else:
                return self._blocking_response(full_messages)

        except Exception as e:
            self._handle_api_error(e)
            return None

    def _stream_response(self, messages: list) -> str:
        """Stream tokens as they arrive and return full response."""
        collected = []

        with self.ui.ai_response_context() as printer:
            stream = self._client.chat.completions.create(
                model=self.model,
                messages=messages,
                stream=True,
            )
            for chunk in stream:
                delta = chunk.choices[0].delta
                if delta and delta.content:
                    token = delta.content
                    collected.append(token)
                    printer(token)

        return "".join(collected)

    def _blocking_response(self, messages: list) -> str:
        """Get a full response without streaming."""
        with self.ui.spinner("Thinking..."):
            response = self._client.chat.completions.create(
                model=self.model,
                messages=messages,
                stream=False,
            )

        text = response.choices[0].message.content
        self.ui.print_ai(text)
        return text

    def _handle_api_error(self, error: Exception):
        """Handle and display API errors gracefully."""
        from openai import AuthenticationError, RateLimitError, APIConnectionError, APIStatusError

        if isinstance(error, AuthenticationError):
            self.ui.error("Authentication failed. Check your [bold]OPENAI_API_KEY[/bold].")
        elif isinstance(error, RateLimitError):
            self.ui.error("Rate limit exceeded. Please wait before retrying.")
        elif isinstance(error, APIConnectionError):
            self.ui.error("Could not connect to OpenAI API. Check your internet connection.")
        elif isinstance(error, APIStatusError):
            self.ui.error(f"API error {error.status_code}: {error.message}")
        else:
            self.ui.error(f"Unexpected error: {type(error).__name__}: {error}")
            logger.debug("Full error:", exc_info=True)
