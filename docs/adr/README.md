# Architecture Decision Records

An ADR captures one significant architectural decision: the context that
forced it, the decision itself, and its consequences — including what we gave
up. They are written when the decision is made and kept even if it is later
superseded, so the reasoning stays with the code.

| ADR | Decision |
|---|---|
| [0001](0001-hybrid-deterministic-plus-llm.md) | Deterministic analyzers and tests produce the findings; the LLM only explains them, and the dashboard aggregates only deterministic misconception tags. |
| [0002](0002-execution-backend-abstraction.md) | One `ExecutionBackend` protocol (`ExecutionPlan → SandboxResult`) with Docker, Kubernetes and local implementations behind a config switch. |
| [0003](0003-sandbox-results-via-stdout-no-network.md) | The sandbox has no network interface; results return as sentinel-delimited JSON on stdout, parsed after the last exact sentinel so student output can't forge a result. |
| [0004](0004-sqlite-default-postgres-production.md) | SQLite by default for zero-setup development, Postgres in compose and Helm — and the portability lesson that taught us about FK enforcement. |
| [0005](0005-in-process-queue-over-broker.md) | An in-process asyncio worker pool with DB-backed, restart-safe status instead of Celery/Redis/Kafka. |
| [0006](0006-multi-provider-llm-with-deterministic-fallback.md) | Anthropic/OpenAI/Ollama behind one provider protocol, with a deterministic template provider that always terminates the chain and honest fallback attribution. |
