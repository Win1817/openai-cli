# openai-cli

A production-ready OpenAI terminal CLI — streaming, file-aware, and session-persistent.
Built with Python, Typer, Rich, and the official OpenAI SDK.

---

## Features

| Feature | Details |
|---|---|
| **Streaming output** | Token-by-token response, just like Claude CLI |
| **Interactive mode** | Persistent session with conversation memory |
| **File input** | Pass YAML, code, logs, or text files with `-f` |
| **Piped input** | `cat logs.txt \| openai "summarize"` |
| **Smart prompts** | Detects YAML / logs / JSON / code and adjusts system prompt |
| **Local history** | Saved to `~/.openai/history.json` between sessions |
| **Model override** | `--model gpt-4-turbo` or any OpenAI model |
| **Rich UI** | Colored output, spinners, tables, banners |

---

## Installation

### 1. Clone & install dependencies

```bash
git clone https://github.com/yourname/openai-cli
cd openai-cli
pip install -r requirements.txt
```

### 2. Set your API key

```bash
cp .env.example .env
# Edit .env and add your key:
# OPENAI_API_KEY=sk-...
```

Or export directly:

```bash
export OPENAI_API_KEY=sk-...
```

### 3. Run it

```bash
python main.py "Explain Kubernetes ingress"
```

### 4. Install as a global `openai` command (optional)

```bash
pip install -e .
# Now you can run:
openai "Hello world"
```

---

## Usage

### One-shot prompt

```bash
openai "Explain Kubernetes ingress"
```

### Piped input

```bash
cat logs.txt | openai "Summarize the errors"
echo '{"status": "error"}' | openai "What does this mean?"
```

### File input

```bash
openai -f deployment.yaml "What does this deploy?"
openai -f script.py "Review this for bugs"
openai -f access.log "What IPs are causing 500 errors?"
```

### Interactive mode

```bash
openai -i
openai --interactive
```

Interactive session commands:

| Command | Action |
|---|---|
| `exit`, `quit`, `:q` | End session |
| `clear` | Clear conversation history |
| `history` | Print current session messages |
| `save` | Save history to disk |
| `help` | Show help panel |

### Load previous session

```bash
openai -i --history
```

---

## CLI Options

```
Usage: openai [OPTIONS] [PROMPT]

Arguments:
  [PROMPT]  Prompt to send to the model

Options:
  -i, --interactive        Launch interactive chat session
  -f, --file PATH          Include file content in prompt
  --no-stream              Disable streaming output
  --model TEXT             Model to use  [default: gpt-4o]
  --history                Load previous conversation history
  --debug                  Enable verbose debug logging
  --version                Show version and exit
  --help                   Show this message and exit
```

---

## Project Structure

```
openai-cli/
├── main.py          # CLI entrypoint and command routing
├── client.py        # OpenAI API wrapper (streaming + blocking)
├── ui.py            # Rich terminal output, prompts, spinners
├── memory.py        # Local history persistence (~/.openai/history.json)
├── utils.py         # Content detection, prompt building, file reading
├── requirements.txt
├── pyproject.toml   # Package definition for `pip install -e .`
└── .env.example
```

---

## Examples

### Summarize error logs

```bash
tail -100 /var/log/nginx/error.log | openai "What's causing the most errors?"
```

### Explain infrastructure config

```bash
openai -f k8s/ingress.yaml "Explain this ingress configuration"
```

### Code review

```bash
openai -f src/auth.py "Review this for security issues"
```

### Non-streaming (e.g. for scripts)

```bash
openai --no-stream "List 5 Linux performance commands" > tips.txt
```

### Override model

```bash
openai --model gpt-4-turbo "Write a haiku about Kubernetes"
```

---

## History File

History is stored at `~/.openai/history.json` and capped at 100 messages.
Delete it to start fresh:

```bash
rm ~/.openai/history.json
```

---

## Requirements

- Python 3.10+
- OpenAI API key (https://platform.openai.com/api-keys)
