# ADR 0002: Pluggable execution backend

## Status

Accepted

## Context

The project needs two very different deployment stories from one codebase: a
zero-friction local demo (`make demo` on a laptop with nothing but Docker) and
a credible production path on Kubernetes with per-submission Jobs,
NetworkPolicies and optional gVisor. Hard-wiring the pipeline to either one
would mean maintaining two pipelines — or shipping a demo-only toy.

## Decision

Define a small protocol in `execution/base.py`:

```python
class ExecutionBackend(Protocol):
    async def run(self, plan: ExecutionPlan) -> SandboxResult: ...
```

An `ExecutionPlan` is the complete, backend-agnostic description of a run:
the student's files, the entrypoint, the test cases, the analyzer steps and
the resource limits. A `SandboxResult` is the uniform outcome: per-step
outputs plus structured test results.

Three implementations exist — `DockerBackend` (compose/demo),
`KubernetesBackend` (Helm/Jobs) and a `local` backend for tests — selected by
the `CODEGUIDE_EXECUTION_BACKEND` setting. The submission queue and the
analyzers never learn which backend ran; they consume `SandboxResult` and
nothing else.

## Consequences

- One pipeline, many deployments: the queue, finding normalization, taxonomy
  tagging and feedback generation are identical code in the demo and in a
  cluster, so the demo genuinely exercises the production logic.
- Each backend keeps its own file-delivery quirk behind the interface: Docker
  streams a gzipped payload over the container's stdin (to preserve the
  read-only rootfs), Kubernetes mounts a ConfigMap at `/work-src` that the
  harness copies into an emptyDir. These differences are invisible above the
  protocol but must be reimplemented — and separately tested — per backend.
- The plan/result contract is a commitment: anything a new backend needs must
  fit through `ExecutionPlan`, which constrains how exotic a backend can be.
