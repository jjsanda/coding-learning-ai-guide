# ADR 0005: In-process asyncio queue over an external broker

## Status

Accepted

## Context

Submissions must be processed asynchronously — a sandbox run takes seconds to
minutes, far too long to hold an HTTP request open. The reflexive answer is a
broker: Celery with Redis, or Kafka. But that adds two more services to
deploy, monitor and explain, for a workload that is a classroom's worth of
submissions, not a firehose. The system should be right-sized.

## Decision

Use an in-process `asyncio.Queue` with a small worker pool
(`worker_concurrency` tasks) inside the API service — see
`codeguide/queue.py`. Durability comes from the database, not the queue:
every submission's status (`queued → running → analyzing → feedback →
completed | failed`) is persisted, and the in-memory queue holds only IDs.

On startup, `_requeue_interrupted()` selects every submission left in a
non-terminal state and puts it back on the queue, so a crash or redeploy
loses no work — at worst a submission is processed again from the top, which
is safe because each stage overwrites rather than appends per-run state.

No Celery, no Redis, no Kafka.

## Consequences

- One service to run. The demo, the compose stack and the Helm chart all get
  async processing with zero extra infrastructure, and the failure story is
  simple: restart the process and it picks up where it left off.
- Throughput is bounded by one process: `worker_concurrency` sandbox runs in
  flight, on one machine. That is ample for a course and honest about its
  ceiling.
- **Horizontal scale-out is future work, and a real trade-off.** Running two
  API replicas today would double-process interrupted submissions, since each
  replica re-queues from the shared database. Scaling out means introducing
  work claiming (e.g. `SELECT ... FOR UPDATE SKIP LOCKED`) or, at that point,
  an actual broker — a cost deliberately deferred until someone has the
  problem.
