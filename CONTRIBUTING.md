# Contributing

Thanks for your interest in improving coding-learning-ai-guide. Contributions
of all kinds are welcome — bug reports, docs, new analyzers, new languages.

## Getting set up

```bash
make install          # backend virtualenv (uv) + frontend dependencies
make dev              # run the API with auto-reload
# in another terminal:
cd frontend && npm run dev
```

The backend needs Docker for the sandboxed integration tests. A fresh checkout
runs on SQLite and built-in feedback templates, so you need no database and no
API key to start hacking.

## Before you open a pull request

Run the same checks CI runs:

```bash
make lint             # ruff (backend) + eslint (frontend)
make typecheck        # mypy (backend) + tsc (frontend)
make test             # backend unit tests
cd frontend && npm test
```

If your change touches the sandbox, analyzers or runners, also run the
integration suite (needs Docker and the built runner images):

```bash
make test-integration
```

## Guidelines

- **Match the surrounding style.** The backend is typed (`mypy` runs strict-ish)
  and the frontend is TypeScript `strict`. Keep it that way.
- **Analyzer findings are facts.** The feedback layer only explains findings; it
  never decides what is wrong. Keep that boundary — the instructor dashboard
  aggregates deterministic tags, never model output.
- **Adding a language?** See [docs/adding-a-language.md](docs/adding-a-language.md).
  It's a runner image, a couple of `Analyzer` classes, a registry entry, and
  some misconception-taxonomy rows.
- **Adding a security rule?** Vendored Semgrep rules live in
  `runners/rules/semgrep/`. The sandbox has no network, so rules must be
  vendored rather than pulled from the registry.
- **Commit messages** describe the *why*, not just the *what*.

## Security issues

Please do not open a public issue for a security vulnerability. See
[SECURITY.md](SECURITY.md).
