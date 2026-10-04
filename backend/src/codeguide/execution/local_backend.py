"""Local subprocess backend — **not a sandbox**.

Runs the harness directly on the host with nothing but rlimits between the
submission and the machine. It exists for CI environments and unit tests
where Docker is unavailable, and refuses to start unless
``CODEGUIDE_ALLOW_UNSAFE_LOCAL=1`` makes the choice explicit.
"""

import asyncio
import json
import os
import sys
import tempfile
from pathlib import Path

import structlog

from codeguide.config import Settings
from codeguide.execution.base import ExecutionPlan, SandboxResult, parse_harness_output

log = structlog.get_logger()


def _default_harness() -> Path:
    # backend/src/codeguide/execution/local_backend.py -> repo root
    return Path(__file__).resolve().parents[4] / "runners" / "harness" / "entrypoint.py"


class LocalBackend:
    def __init__(self, settings: Settings) -> None:
        if not settings.allow_unsafe_local:
            raise RuntimeError(
                "The local execution backend runs submissions WITHOUT isolation. "
                "Set CODEGUIDE_ALLOW_UNSAFE_LOCAL=1 only for CI/testing."
            )
        self._settings = settings
        self._harness = Path(os.environ.get("CODEGUIDE_HARNESS_PATH", _default_harness()))
        if not self._harness.exists():
            raise FileNotFoundError(f"harness not found: {self._harness}")
        log.warning("local_backend_enabled", harness=str(self._harness))

    async def run(self, plan: ExecutionPlan) -> SandboxResult:
        with tempfile.TemporaryDirectory(prefix="codeguide-local-") as work_dir:
            work = Path(work_dir)
            for rel_path, content in plan.files.items():
                target = work / rel_path
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(content)
            (work / "plan.json").write_text(json.dumps(plan.harness_payload()))

            proc = await asyncio.create_subprocess_exec(
                sys.executable,
                str(self._harness),
                cwd=work_dir,
                env={**os.environ, "CODEGUIDE_WORK_DIR": work_dir},
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.DEVNULL,
            )
            try:
                stdout, _ = await asyncio.wait_for(
                    proc.communicate(), timeout=plan.limits.wall_timeout_s
                )
            except TimeoutError:
                proc.kill()
                return SandboxResult(
                    ok=False,
                    error=f"run exceeded the {plan.limits.wall_timeout_s}s wall-clock limit",
                )
            return parse_harness_output(stdout.decode(errors="replace"))
