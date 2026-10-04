# ADR 0004: SQLite by default, Postgres in production

## Status

Accepted

## Context

A fresh checkout should run with zero setup — `make dev` and go, no database
server to install. But production (and even the compose demo, with its worker
pool writing findings concurrently) wants a real database with proper
concurrent writes and enforced constraints.

## Decision

The default `CODEGUIDE_DATABASE_URL` is SQLite via `aiosqlite`
(`sqlite+aiosqlite:///./data/app.db`), so the API works on a bare checkout.
Docker Compose and the Helm chart override it to Postgres via `asyncpg`. Both
drivers sit behind SQLAlchemy's async engine, and Alembic migrations run on
startup so either database is brought to the current schema automatically.

## Consequences

- Development is trivial: clone, install, run. No container or daemon needed
  for the unit-test and local-dev loop.
- Every query and migration must stay portable across both engines. We avoid
  Postgres-only column types and use `native_enum=False` string enums so the
  schema means the same thing in both.
- **A lesson we actually hit:** the two engines differ in what they *enforce*,
  not just what they support. A raw `DELETE` against a parent table appeared
  to cascade fine in development — because SQLite wasn't enforcing foreign
  keys, orphan child rows silently remained — and then failed on Postgres,
  which enforces the constraints. The cascade behaviour lived in the ORM
  relationships (`cascade="all, delete-orphan"`), so deletes must go through
  the ORM (or the schema needs `ON DELETE CASCADE` in the DDL itself). The
  fix was easy; the takeaway is durable: "portable SQL" includes portable
  *enforcement*, and destructive operations need testing against Postgres,
  not just the convenient default.
