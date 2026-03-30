# openai-cli

A developer-grade OpenAI terminal CLI built to feel like Claude CLI — interactive by default, streaming, file-aware, and session-persistent.

Built with Python · Typer · Rich · prompt_toolkit · OpenAI SDK

---

## Features

| | |
|---|---|
| **Interactive by default** | Drops straight into a REPL — no flags needed |
| **Streaming output** | Tokens print live as they arrive, then re-render as markdown |
| **Smart system prompts** | Detects YAML / logs / JSON / code and adapts the AI's role |
| **Session memory** | Conversation history saved to `~/.openai/history.json` |
| **Input history** | Arrow keys navigate past inputs across sessions |
| **File input** | Attach any text file with `-f` |
| **Piped input** | `cat logs.txt | openai` just works |
| **Hot-swap model** | Change model mid-session with `/model gpt-4-turbo` |
| **One-shot mode** | `openai "prompt"` for scripting and quick queries |

---

## Installation

### One command

```bash
git clone https://github.com/Win1817/openai-cli.git
cd openai-cli
bash install.sh
```

`install.sh` will:

1. Check for Python 3.10+
2. Install all dependencies from `requirements.txt`
3. Prompt you to enter your OpenAI API key *(input is hidden)*
4. Write the key to `.env` automatically with `chmod 600`
5. Install a global `openai` command to `~/.local/bin`
6. Validate the full setup before finishing

> Get your API key at [platform.openai.com/api-keys](https://platform.openai.com/api-keys)

---

### Manual setup (optional)

If you prefer to set things up yourself:

```bash
pip install -r requirements.txt

cp .env.example .env
# Open .env and set:
# OPENAI_API_KEY=sk-...

python main.py
```

---

## Usage

### Interactive session (default)

```bash
openai
```

Just run `openai` with no arguments. You'll land in a full REPL with history, autocomplete, and streaming output.

### One-shot prompt

```bash
openai "Explain Kubernetes ingress"
openai --no-stream "List 5 Linux performance tips" > tips.txt
```

### Piped input

```bash
cat logs.txt | openai
cat logs.txt | openai "Focus on 5xx errors"
echo '{"status": "error", "code": 503}' | openai "What does this mean?"
```

### File input

```bash
openai -f deployment.yaml
openai -f deployment.yaml "What does this deploy?"
openai -f src/auth.py "Review for security issues"
openai -f access.log "Which IPs are causing 500 errors?"
```

### Resume a previous session

```bash
openai --history
```

---

## Session commands

Once inside the interactive REPL:

| Command | Description |
|---|---|
| `/help` | Show available commands |
| `/clear` | Clear conversation history for this session |
| `/history` | Print all messages in the current session |
| `/save` | Save history to disk now |
| `/model` | Show current model |
| `/model gpt-4-turbo` | Switch model mid-session |
| `/exit` | End the session |

**Keyboard shortcuts:**

| Key | Action |
|---|---|
| `Enter` | Submit message |
| `Alt+Enter` | Insert a newline (multiline input) |
| `↑ / ↓` | Browse input history |
| `Ctrl+C` | Clear current line (does not exit) |

---

## CLI options

```
Usage: openai [OPTIONS] [PROMPT]

Arguments:
  [PROMPT]          One-shot prompt — skips interactive mode

Options:
  -f, --file PATH   Attach a file's content to your prompt
  --no-stream       Disable streaming (useful for piping output)
  --model TEXT      Model to use  [default: gpt-4o]
  --history         Resume previous conversation on startup
  --debug           Verbose debug logging
  --version         Show version and exit
  --help            Show this message and exit
```

---

## Project structure

```
openai-cli/
├── install.sh       # One-shot installer: deps + API key + global command
├── main.py          # CLI entrypoint (Typer), mode routing
├── repl.py          # Interactive REPL (prompt_toolkit)
├── client.py        # OpenAI SDK wrapper — streaming + blocking
├── memory.py        # History persistence (~/.openai/history.json)
├── utils.py         # Content detection, prompt building, file reading
├── requirements.txt
├── pyproject.toml
└── .env.example
```

---

## How streaming works

Responses stream token-by-token to the terminal as they arrive, giving the Claude CLI typing effect. Once the full response lands, it's re-rendered as proper markdown — so code blocks, bold text, and lists all display correctly.

---

## Content detection

When you paste or pipe content, the CLI detects what it is and assigns the right AI persona automatically:

| Content type | AI persona |
|---|---|
| YAML / Kubernetes manifests | DevOps / infrastructure engineer |
| Log files / stack traces | Site reliability engineer |
| Code | Senior software engineer / code reviewer |
| JSON | Data engineer / API expert |
| Everything else | General developer assistant |

---

## History & storage

| Path | Contents |
|---|---|
| `~/.openai/history.json` | Conversation messages (capped at 100) |
| `~/.openai/input_history` | Raw input history for arrow-key navigation |

Clear everything:

```bash
rm -rf ~/.openai
```

---

## Requirements

- Python 3.10+
- OpenAI API key — [platform.openai.com/api-keys](https://platform.openai.com/api-keys)
