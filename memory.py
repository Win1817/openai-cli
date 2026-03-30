"""
memory.py — Local conversation history persistence.
Stores sessions in ~/.openai/history.json
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

from rich.console import Console
from rich.table import Table
from rich import box

logger = logging.getLogger(__name__)

HISTORY_DIR = Path.home() / ".openai"
HISTORY_FILE = HISTORY_DIR / "history.json"
MAX_HISTORY_MESSAGES = 100  # Cap to avoid giant files


class ConversationMemory:
    def __init__(self, history_path: Path = HISTORY_FILE):
        self.history_path = history_path
        self._ensure_dir()

    def _ensure_dir(self):
        self.history_path.parent.mkdir(parents=True, exist_ok=True)

    def save(self, messages: list):
        """Persist conversation messages to disk."""
        if not messages:
            return

        # Keep last N messages to avoid unbounded growth
        trimmed = messages[-MAX_HISTORY_MESSAGES:]

        payload = {
            "saved_at": datetime.now().isoformat(),
            "message_count": len(trimmed),
            "messages": trimmed,
        }

        try:
            with open(self.history_path, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2, ensure_ascii=False)
            logger.debug(f"Saved {len(trimmed)} messages to {self.history_path}")
        except OSError as e:
            logger.warning(f"Could not save history: {e}")

    def load(self) -> list:
        """Load conversation messages from disk."""
        if not self.history_path.exists():
            return []

        try:
            with open(self.history_path, "r", encoding="utf-8") as f:
                payload = json.load(f)

            messages = payload.get("messages", [])
            logger.debug(f"Loaded {len(messages)} messages from {self.history_path}")
            return messages
        except (OSError, json.JSONDecodeError) as e:
            logger.warning(f"Could not load history: {e}")
            return []

    def clear(self):
        """Delete the history file."""
        try:
            if self.history_path.exists():
                self.history_path.unlink()
                logger.debug("History cleared.")
        except OSError as e:
            logger.warning(f"Could not clear history: {e}")

    def print_history(self, console: Console, messages: Optional[list] = None):
        """Render conversation history in a rich table."""
        if messages is None:
            messages = self.load()

        if not messages:
            console.print("[dim]No history found.[/dim]")
            return

        table = Table(
            title="Conversation History",
            box=box.ROUNDED,
            border_style="dim",
            show_lines=True,
            expand=True,
        )
        table.add_column("#", style="dim", width=4)
        table.add_column("Role", style="bold", width=12)
        table.add_column("Content", overflow="fold")

        for i, msg in enumerate(messages, 1):
            role = msg.get("role", "?")
            content = msg.get("content", "")
            # Truncate long messages in table view
            preview = content[:200] + "…" if len(content) > 200 else content

            role_style = "yellow" if role == "user" else "cyan"
            table.add_row(str(i), f"[{role_style}]{role}[/{role_style}]", preview)

        console.print(table)
