# codeguide backend

FastAPI service that powers coding-learning-ai-guide: it accepts student
submissions, schedules sandboxed execution and static analysis, and produces
formative feedback. See the [repository README](../README.md) for the full
picture and [docs/architecture.md](../docs/architecture.md) for internals.

## Development

```bash
uv venv .venv && uv pip install -p .venv -e ".[dev]"
.venv/bin/uvicorn codeguide.main:app --reload
```

Run checks:

```bash
.venv/bin/ruff check src tests
.venv/bin/mypy
.venv/bin/pytest
```
