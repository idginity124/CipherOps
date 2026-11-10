# Contributing to CipherOps

First off — thank you for taking the time to contribute! 🎉

CipherOps is a local-first, privacy-focused autonomous agent. Every contribution that makes it faster, safer, or more useful is welcome.

---

## Quick start

```bash
git clone https://github.com/idginity124/CipherOps.git
cd CipherOps
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

Run the test suite to make sure everything passes before you change anything:

```bash
pytest tests/ -v
```

---

## Ways to contribute

| Type | How |
|---|---|
| 🐛 Bug report | Open an [issue](https://github.com/idginity124/CipherOps/issues) with steps to reproduce |
| 💡 Feature idea | Open an issue first so we can discuss before you build |
| 🔧 Code fix | Fork → branch → PR |
| 🧪 New tests | Always welcome — the coverage bar is always too low |
| 📝 Docs improvement | Typos, clarity, Turkish/English parity |
| 🌍 Translation | New language README or in-code messages |

---

## Pull request checklist

Before opening a PR, please make sure:

- [ ] `pytest tests/ -v` passes with **no failures**
- [ ] New behaviour is covered by at least one new test
- [ ] Public functions and classes have docstrings
- [ ] No secrets, credentials, or PII are committed
- [ ] The PR description explains *what* changed and *why*

---

## Adding a new tool

1. Create `src/cipherops/tools/my_tool.py` inheriting from `BaseTool`
2. Implement `execute(**kwargs) -> ToolResult`
3. Register it in `create_default_registry()` inside `tools/registry.py` (or document how users register it themselves)
4. Add tests in `tests/test_tools.py`

```python
from cipherops.tools.base import BaseTool, ToolResult

class MyTool(BaseTool):
    name = "my_tool"
    description = "What this tool does, one sentence."
    parameters = {
        "type": "object",
        "properties": {
            "input": {"type": "string", "description": "..."}
        },
        "required": ["input"],
    }

    def execute(self, input: str, **kwargs) -> ToolResult:
        try:
            result = do_something(input)
            return ToolResult(success=True, output=result)
        except Exception as e:
            return ToolResult(success=False, output="", error=str(e), exit_code=1)
```

---

## Code style

- Python 3.10+ syntax
- Type hints on all public functions
- `snake_case` for functions and variables, `PascalCase` for classes
- Keep lines under 100 characters where possible
- No external formatters enforced yet — just be consistent with the surrounding code

---

## Commit message format

```
<type>: short imperative description (max 72 chars)

Optional longer explanation if needed.
```

Types: `feat`, `fix`, `security`, `docs`, `test`, `refactor`, `chore`

Examples:
```
feat: add web search tool with DuckDuckGo backend
fix: resolve context window overflow in long chat sessions
security: block execution wrappers in CommandValidator
test: add thread-safety test for AuditLogger
```

---

## Security issues

**Please do not open public issues for security vulnerabilities.**

If you find a security bug, contact the maintainer directly via the email on the [GitHub profile](https://github.com/idginity124) or via LinkedIn. We'll acknowledge within 48 hours.

---

## License

By contributing, you agree that your contributions will be licensed under the [MIT License](LICENSE).
