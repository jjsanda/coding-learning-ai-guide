"""Execution backend contract.

A backend takes an :class:`ExecutionPlan` (student files + the commands to
run over them), executes it inside an isolated sandbox and returns a
:class:`SandboxResult`. The rest of the application never knows *how* the
sandbox is implemented — Docker containers in the docker-compose setup,
Kubernetes Jobs in cluster deployments.

The sandbox communication contract: the sandbox has no network access at
all. Results come back as a JSON document printed to the container's stdout
after a sentinel line. Everything that touches the untrusted submission —
test execution *and* static analyzers — happens inside the sandbox.
"""

from dataclasses import dataclass, field
from typing import Any, Protocol

SENTINEL = "===CODEGUIDE_RESULT_v1==="


@dataclass(frozen=True)
class Step:
    """One analyzer command to run inside the sandbox."""

    id: str
    cmd: list[str]
    timeout_s: int = 60


@dataclass(frozen=True)
class Limits:
    cpus: float = 1.0
    memory_mb: int = 512
    pids: int = 128
    wall_timeout_s: int = 120


@dataclass(frozen=True)
class ExecutionPlan:
    language: str
    entrypoint: str
    files: dict[str, str]  # path -> content
    test_cases: list[dict[str, Any]]
    steps: list[Step]
    limits: Limits = field(default_factory=Limits)

    def harness_payload(self) -> dict[str, Any]:
        """The plan.json document the in-sandbox harness consumes.

        Only the inputs the sandbox needs to *run* each case are sent — never
        the expected output. The expected value stays server-side and the
        orchestrator computes the verdict, so hidden test cases can't be read
        by the student's own program and the pass/fail decision is never made
        in untrusted territory.
        """
        return {
            "language": self.language,
            "entrypoint": self.entrypoint,
            "test_cases": [
                {
                    "name": tc["name"],
                    "stdin": tc.get("stdin", ""),
                    "timeout_ms": tc.get("timeout_ms", 5000),
                }
                for tc in self.test_cases
            ],
            "steps": [
                {"id": s.id, "cmd": s.cmd, "timeout_s": s.timeout_s} for s in self.steps
            ],
        }


@dataclass
class StepOutput:
    exit_code: int
    stdout: str
    stderr: str
    duration_ms: int
    timed_out: bool


@dataclass
class SandboxResult:
    ok: bool
    steps: dict[str, StepOutput] = field(default_factory=dict)
    tests: list[dict[str, Any]] = field(default_factory=list)
    error: str | None = None


def parse_harness_output(raw_logs: str) -> SandboxResult:
    """Parse the sentinel-delimited harness JSON from container output.

    The document after the *last exact sentinel line* wins: student output can
    only ever appear embedded inside JSON string values (the harness captures
    it), never as a bare sentinel line followed by attacker-chosen JSON.
    """
    import json

    lines = raw_logs.splitlines()
    sentinel_at = [i for i, line in enumerate(lines) if line.strip() == SENTINEL]
    if not sentinel_at:
        return SandboxResult(ok=False, error="no result sentinel in sandbox output")
    payload = "\n".join(lines[sentinel_at[-1] + 1 :]).strip()
    try:
        doc = json.loads(payload)
    except json.JSONDecodeError as exc:
        return SandboxResult(ok=False, error=f"malformed sandbox result: {exc}")

    steps = {
        step_id: StepOutput(
            exit_code=data.get("exit_code", -1),
            stdout=data.get("stdout", ""),
            stderr=data.get("stderr", ""),
            duration_ms=data.get("duration_ms", 0),
            timed_out=data.get("timed_out", False),
        )
        for step_id, data in doc.get("steps", {}).items()
    }
    return SandboxResult(
        ok=doc.get("error") is None,
        steps=steps,
        tests=doc.get("tests", []),
        error=doc.get("error"),
    )


class ExecutionBackend(Protocol):
    async def run(self, plan: ExecutionPlan) -> SandboxResult:
        """Execute the plan in an isolated sandbox."""
        ...
