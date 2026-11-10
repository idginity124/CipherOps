# ⚡ CipherOps

> **Enterprise-Grade Local Autonomous AI Agent with Privacy Guardrails, Human-in-the-Loop Execution, and Full Audit Logging**

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue?logo=python)](https://python.org)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Tests](https://img.shields.io/badge/tests-5%20passed-brightgreen)](#testing)
[![On-Premise](https://img.shields.io/badge/Runs-100%25%20Local-blueviolet)](#setup)
[![Model Agnostic](https://img.shields.io/badge/Model-Agnostic-orange)](#models)

CipherOps is a **privacy-first, locally-executed autonomous AI agent** built for enterprise and regulated industry environments (banking, finance, healthcare). It runs entirely on your machine—no data ever leaves to external servers—while providing the sophisticated control mechanisms that production systems demand.

---

## 🎯 Key Features

| Feature | Details |
|---|---|
| **🔒 PII Sanitization** | Auto-redacts TCKN, IBAN, credit cards, API keys, emails & phone numbers before model inference (KVKK / GDPR compliant) |
| **🛡️ Command Firewall** | 4-tier risk engine (`SAFE` → `CAUTION` → `HIGH` → `BLOCKED`). Catastrophic commands (`rm -rf /`, `mkfs`, fork bombs, raw disk writes) are **unconditionally blocked** |
| **👤 Human-in-the-Loop** | Every destructive or state-altering command requires explicit operator confirmation in-terminal before execution |
| **📋 Immutable Audit Trail** | Every tool call, security event, and PII redaction is written to a structured, append-only JSON Lines audit log |
| **🧠 ReAct Agent Loop** | Multi-step Reasoning + Acting loop with up to 15 autonomous iterations; works with any OpenAI-compatible local LLM |
| **🏠 100% On-Premise** | Communicates only with your local Ollama instance. Zero cloud dependency, zero telemetry |
| **🔧 Extensible Tool System** | Clean `BaseTool` interface: add new capabilities in <30 lines of Python |

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────┐
│                   CLI / Interactive Chat                 │
│               (Typer + Rich Terminal UI)                 │
└──────────────────────────┬──────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────┐
│          PRIVACY GUARDRAIL  (Runs BEFORE LLM)           │
│   • PIISanitizer: TCKN · IBAN · Cards · API Keys · Email│
└──────────────────────────┬──────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────┐
│            CipherAgent — ReAct Core Loop                │
│    Think → Plan → Tool Call → Observe → Repeat          │
│    (OllamaClient — model-agnostic HTTP interface)       │
└──────────────────────────┬──────────────────────────────┘
                           │
       ┌───────────────────┼───────────────────┐
       │                   │                   │
┌──────▼──────┐  ┌─────────▼────────┐  ┌──────▼──────────┐
│  BashTool   │  │  FileTools       │  │  ToolRegistry   │
│  (Secure    │  │  Read · Write    │  │  (Plug-in any   │
│   Shell)    │  │  · List Dir      │  │   custom tool)  │
└──────┬──────┘  └──────────────────┘  └─────────────────┘
       │
┌──────▼──────────────────────────────────────────────────┐
│          COMMAND FIREWALL  (Runs BEFORE every exec)     │
│   BLOCKED: rm -rf / · mkfs · dd to disk · fork bombs   │
│   HIGH:    rm · kill · chmod → requires human approval  │
│   CAUTION: pip install · build scripts → asks operator  │
│   SAFE:    ls · git · cat · grep → auto-approved        │
└──────┬──────────────────────────────────────────────────┘
       │
┌──────▼──────────────────────────────────────────────────┐
│          AUDIT LOGGER  (append-only JSONL)              │
│   Every event · tool call · block · PII hit · decision  │
└─────────────────────────────────────────────────────────┘
```

---

## 🚀 Setup

### Prerequisites
- Python 3.10+
- [Ollama](https://ollama.com) running locally

#### Install Ollama (CachyOS / Arch with AMD GPU)
```bash
# ROCm-accelerated build for AMD GPUs (RX 6000 series+)
sudo pacman -S ollama-rocm
sudo systemctl enable --now ollama

# Pull the recommended coding model (~9 GB)
ollama pull qwen2.5-coder:14b
```

### Install CipherOps

```bash
git clone https://github.com/YOUR_USERNAME/CipherOps.git
cd CipherOps

python -m venv .venv
source .venv/bin/activate

pip install -e .
```

---

## 💻 Usage

### Diagnose System Readiness
```bash
cipherops doctor
```

```
╭─────────────────────────╮
│ CipherOps System Doctor │
╰─────────────────────────╯
  Component             │ Status    │ Details
  Python Runtime        │ OK        │ 3.14.9
  Ollama Service        │ ACTIVE    │ Connected to http://localhost:11434
  Local Models          │ FOUND     │ qwen2.5-coder:14b
  Audit Trail Directory │ CONFIGURED│ /home/user/.cipherops/audit
```

### Single Task Execution
```bash
cipherops run "Check if there are any broken Python imports in this project and fix them"
```

### Interactive Session
```bash
cipherops chat
```

```
CipherOps > Sistemde hangi portlar açık?
🧠 Step 1: Analyzing state & planning...
⚙️  Executing Tool: execute_bash args={'command': 'ss -tlnp'}
   ↳ SUCCESS (Code 0): ...

CipherOps > src/api.py dosyasındaki authentication fonksiyonunu incele
⚙️  Executing Tool: read_file args={'file_path': 'src/api.py'}
   ...
```

### Human-in-the-Loop in Action
```
⚙️  Executing Tool: execute_bash args={'command': 'rm -f old_logs/*.log'}

┌─────────────────────────────────────┐
│  🛡️  Operator Confirmation Required  │
│  SECURITY RISK ASSESSMENT: HIGH     │
│  Reason: Command contains 'rm'      │
│  Command: rm -f old_logs/*.log      │
└─────────────────────────────────────┘
Execute this command on host? [y/N]:
```

---

## 🔒 Privacy & Compliance

CipherOps is designed from the ground up for **KVKK (Turkey)** and **GDPR (EU)** compliant environments:

### PII Detection Coverage

| Type | Example | Redacted As |
|---|---|---|
| Turkish Republic ID (TCKN) | `10000000146` | `[REDACTED_TCKN]` |
| IBAN (TR + International) | `TR33 0006 1005 1112 3456 7890 12` | `[REDACTED_IBAN]` |
| Credit Card Numbers | `4111 1111 1111 1111` | `[REDACTED_CARD]` |
| API Keys & Tokens | `sk-proj-...`, `ghp_...`, `AKIA...` | `[REDACTED_API_KEY]` |
| Email Addresses | `user@example.com` | `[REDACTED_EMAIL]` |
| Turkish Phone Numbers | `0532 123 45 67` | `[REDACTED_PHONE]` |

TCKN validation uses the official 11-digit checksum algorithm to minimize false positives.

### Audit Log Format

Every agent action produces a structured, immutable log entry:
```json
{
  "timestamp": "2025-11-10T18:30:01.123Z",
  "event_type": "tool_execution",
  "level": "INFO",
  "tool_name": "execute_bash",
  "command_or_input": "{\"command\": \"ls -la\"}",
  "output_summary": "total 32\\ndrwxr-xr-x ...",
  "exit_code": 0,
  "human_approved": true
}
```

---

## 🧪 Testing

```bash
source .venv/bin/activate
pytest tests/ -v
```

```
tests/test_guardrails.py::test_tckn_masking                              PASSED
tests/test_guardrails.py::test_iban_masking                              PASSED
tests/test_guardrails.py::test_api_key_masking                           PASSED
tests/test_guardrails.py::test_command_firewall_blocks_catastrophic      PASSED
tests/test_guardrails.py::test_command_firewall_classifies_safe_and_caution PASSED

5 passed in 0.01s
```

---

## 🔧 Extending CipherOps

Add a custom tool in under 30 lines:

```python
from cipherops.tools.base import BaseTool, ToolResult

class WebSearchTool(BaseTool):
    name = "web_search"
    description = "Search the web and return a summary of results"
    parameters = {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Search query"}
        },
        "required": ["query"],
    }

    def execute(self, query: str, **kwargs) -> ToolResult:
        # Your implementation here
        return ToolResult(success=True, output=f"Results for: {query}")
```

Register it:
```python
from cipherops.tools.registry import create_default_registry

registry = create_default_registry()
registry.register(WebSearchTool())
```

---

## 📁 Project Structure

```
CipherOps/
├── src/cipherops/
│   ├── core/
│   │   ├── agent.py          # ReAct autonomous agent loop
│   │   └── llm.py            # Ollama / OpenAI-compatible client
│   ├── guardrails/
│   │   ├── pii_sanitizer.py  # TCKN, IBAN, card, key redaction
│   │   └── command_validator.py  # 4-tier command firewall
│   ├── tools/
│   │   ├── base.py           # BaseTool abstract interface
│   │   ├── bash_tool.py      # Secure shell executor
│   │   ├── file_tool.py      # Read / Write / List tools
│   │   └── registry.py       # Tool registry & factory
│   ├── audit/
│   │   └── logger.py         # Immutable JSON Lines audit logger
│   └── cli.py                # Typer CLI (doctor / run / chat)
├── tests/
│   └── test_guardrails.py    # Unit tests for PII & command firewall
├── pyproject.toml
├── requirements.txt
└── README.md
```

---

## 🗺️ Roadmap

- [ ] **v0.2** — Vector memory (ChromaDB) for long-term context across sessions
- [ ] **v0.3** — Web search & browser automation tool
- [ ] **v0.4** — Multi-agent orchestration (planner + executor split)
- [ ] **v0.5** — REST API server mode (FastAPI) for headless / CI integrations
- [ ] **v1.0** — Docker-based sandboxed execution environment

---

## 📄 License

MIT © 2025 — Built with ❤️ for privacy-first AI engineering
