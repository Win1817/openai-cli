"""
utils.py — Prompt building, content detection, and file helpers.
"""

import logging
import re
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Patterns for intelligent content-type detection
YAML_PATTERNS = [
    r"^\s*[\w\-]+:\s+",      # key: value
    r"^\s*-\s+[\w\-]+:",     # - key:
    r"apiVersion:",
    r"kind:\s+\w+",
    r"metadata:",
    r"spec:",
]

LOG_PATTERNS = [
    r"\d{4}-\d{2}-\d{2}[T\s]\d{2}:\d{2}:\d{2}",  # timestamp
    r"\[(ERROR|WARN|INFO|DEBUG|FATAL|CRITICAL)\]",
    r"Traceback \(most recent call last\)",
    r"Exception in thread",
    r"(ERROR|WARN|FATAL):",
    r"\bstacktrace\b",
    r"at\s+[\w\.]+\([\w\.]+:\d+\)",              # Java stack frame
]

JSON_PATTERNS = [
    r'^\s*\{',
    r'^\s*\[',
    r'"[\w\-]+":\s*["{{\[\d]',
]

CODE_EXTENSIONS = {
    ".py", ".js", ".ts", ".go", ".rs", ".java", ".cpp", ".c", ".cs",
    ".rb", ".php", ".sh", ".bash", ".sql", ".swift", ".kt",
}

TEXT_EXTENSIONS = {
    ".txt", ".md", ".rst", ".log", ".csv", ".ini", ".toml", ".env",
}


def detect_content_type(text: str) -> str:
    """
    Heuristically detect what kind of content the prompt contains.
    Returns: 'yaml' | 'logs' | 'json' | 'code' | 'default'
    """
    if not text:
        return "default"

    sample = text[:3000]  # Only inspect the first chunk

    for pattern in LOG_PATTERNS:
        if re.search(pattern, sample, re.MULTILINE | re.IGNORECASE):
            logger.debug("Content type detected: logs")
            return "logs"

    for pattern in JSON_PATTERNS:
        if re.search(pattern, sample, re.MULTILINE):
            logger.debug("Content type detected: json")
            return "json"

    yaml_hits = sum(
        1 for p in YAML_PATTERNS if re.search(p, sample, re.MULTILINE)
    )
    if yaml_hits >= 2:
        logger.debug("Content type detected: yaml")
        return "yaml"

    # Rough code detection: look for common programming constructs
    code_signals = [
        r"\bdef\s+\w+\s*\(",       # Python
        r"\bfunction\s+\w+\s*\(",  # JS
        r"\bfunc\s+\w+\s*\(",      # Go
        r"\bclass\s+\w+",          # many languages
        r"\bimport\s+[\w\.]+",     # imports
        r"\bconst\s+\w+\s*=",      # JS const
        r"\blet\s+\w+\s*=",
        r"\bvar\s+\w+\s*=",
        r"#include\s*<",           # C/C++
        r"\bpublic\s+static\s+void\b",  # Java
    ]
    code_hits = sum(1 for p in code_signals if re.search(p, sample, re.MULTILINE))
    if code_hits >= 2:
        logger.debug("Content type detected: code")
        return "code"

    return "default"


def build_prompt(
    prompt: Optional[str],
    stdin_content: Optional[str],
    file_content: Optional[str],
) -> str:
    """
    Combine prompt, stdin, and file content into a single message.
    """
    parts = []

    if file_content:
        parts.append(f"--- FILE CONTENT ---\n{file_content}\n--- END FILE ---")

    if stdin_content:
        parts.append(f"--- INPUT ---\n{stdin_content}\n--- END INPUT ---")

    if prompt:
        parts.append(prompt)

    return "\n\n".join(parts).strip()


def read_file_content(path: Path, ui) -> Optional[str]:
    """
    Safely read a file and return its content as a string.
    """
    try:
        suffix = path.suffix.lower()

        # Binary file guard
        if suffix in {".png", ".jpg", ".jpeg", ".gif", ".pdf", ".zip", ".tar", ".gz"}:
            ui.error(f"Binary file type [bold]{suffix}[/bold] is not supported as text input.")
            return None

        with open(path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()

        # Annotate file type for better context
        label = _file_label(suffix)
        logger.debug(f"Read {len(content)} chars from {path} (type: {label})")
        return f"[{label}: {path.name}]\n{content}"

    except OSError as e:
        ui.error(f"Could not read file [bold]{path}[/bold]: {e}")
        return None


def _file_label(suffix: str) -> str:
    labels = {
        ".yaml": "YAML",
        ".yml": "YAML",
        ".json": "JSON",
        ".py": "Python",
        ".js": "JavaScript",
        ".ts": "TypeScript",
        ".go": "Go",
        ".sh": "Shell",
        ".sql": "SQL",
        ".md": "Markdown",
        ".txt": "Text",
        ".log": "Log",
        ".toml": "TOML",
        ".ini": "INI",
        ".env": "Env",
        ".csv": "CSV",
    }
    return labels.get(suffix, "File")
