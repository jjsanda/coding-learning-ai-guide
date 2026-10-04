# ADR 0003: Sandbox results via stdout, never the network

## Status

Accepted

## Context

The sandbox exists to run genuinely malicious code — that is the threat model,
not an edge case. Any channel the sandbox can use to report results is also a
channel the student's code can reach. If results came back over HTTP to the
orchestrator, the sandbox would need a network interface, and every "no
egress" claim would rest on filtering rules being exactly right.

## Decision

The sandbox has **no network interface at all** — `network_disabled=True` in
the Docker backend, a default-deny NetworkPolicy for the Kubernetes Jobs
namespace. Results come back over the only channel that remains: the
container's stdout (pod logs on Kubernetes).

The in-sandbox harness prints one JSON document after a sentinel line,
`===CODEGUIDE_RESULT_v1===`. The orchestrator (`parse_harness_output`) parses
only what follows the **last exact sentinel line**. Student output is captured
by the harness and can only appear embedded inside JSON string values — a
submission that prints the sentinel followed by forged JSON just moves the
real sentinel later, so the harness's own document still wins.

Everything that touches the untrusted submission — running the tests *and*
the static analyzers — happens inside the sandbox, so a crafted file that
exploits an analyzer bug is still contained.

## Consequences

- The strongest network posture available: there is no socket to filter,
  firewall or misconfigure. Exfiltration and callback attacks have no channel.
- The orchestrator must parse logs, which is inherently messier than an API
  call: the Kubernetes backend retries log reads because a Job can report
  completion before logs are readable.
- Output size is bounded — very large stdout is truncated by the harness's
  capture limits, so a result can lose detail that a streaming channel would
  have kept.
