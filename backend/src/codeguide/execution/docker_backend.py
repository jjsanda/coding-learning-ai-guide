"""Docker execution backend — the sandbox used by the docker-compose setup.

Isolation applied to every run:

* ``network_disabled`` — the container has **no network interface at all**;
  results come back via stdout (see :mod:`codeguide.execution.base`)
* read-only root filesystem; ``/work`` and ``/tmp`` are small tmpfs mounts,
  the only writable paths
* non-root user (65534), all capabilities dropped, ``no-new-privileges``
* memory / CPU / pids limits, and a hard wall-clock timeout after which the
  container is killed

The submission and ``plan.json`` are streamed to the harness over the
container's stdin as a gzipped JSON payload — nothing is written through the
Docker filesystem API, which keeps the read-only rootfs intact.
"""

import asyncio
import gzip
import json
import socket

import structlog

from codeguide.config import Settings
from codeguide.execution.base import (
    ExecutionPlan,
    SandboxResult,
    parse_harness_output,
)
from codeguide.execution.plan import runner_image

log = structlog.get_logger()

_SANDBOX_UID = 65534


def _payload(plan: ExecutionPlan) -> bytes:
    files = dict(plan.files)
    files["plan.json"] = json.dumps(plan.harness_payload())
    return gzip.compress(json.dumps({"files": files}).encode())


class DockerBackend:
    def __init__(self, settings: Settings) -> None:
        import docker

        self._settings = settings
        self._client = docker.from_env()

    async def run(self, plan: ExecutionPlan) -> SandboxResult:
        return await asyncio.to_thread(self._run_sync, plan)

    def _run_sync(self, plan: ExecutionPlan) -> SandboxResult:
        from requests.exceptions import RequestException

        image = runner_image(plan.language, self._settings)
        limits = plan.limits
        work_tmpfs_mb = max(64, limits.memory_mb // 4)
        container = self._client.containers.create(
            image=image,
            network_disabled=True,
            read_only=True,
            stdin_open=True,
            user=f"{_SANDBOX_UID}:{_SANDBOX_UID}",
            cap_drop=["ALL"],
            security_opt=["no-new-privileges"],
            mem_limit=f"{limits.memory_mb}m",
            memswap_limit=f"{limits.memory_mb}m",
            pids_limit=limits.pids,
            nano_cpus=int(limits.cpus * 1_000_000_000),
            # the tmpfs mounts are the sandbox's only writable paths by design.
            # /work (student code) is also noexec so a submission can't drop and
            # run a binary; /tmp stays exec-able because some analyzers stage
            # helpers there. nosuid,nodev harden both.
            tmpfs={
                "/work": (
                    f"size={work_tmpfs_mb}m,uid={_SANDBOX_UID},gid={_SANDBOX_UID}"
                    ",noexec,nosuid,nodev"
                ),
                "/tmp": (  # noqa: S108
                    f"size={work_tmpfs_mb}m,uid={_SANDBOX_UID},gid={_SANDBOX_UID},nosuid,nodev"
                ),
            },
            labels={"app": "coding-learning-ai-guide", "role": "sandbox"},
        )
        try:
            stdin = container.attach_socket(params={"stdin": 1, "stream": 1})
            container.start()
            raw_sock = stdin._sock
            raw_sock.sendall(_payload(plan))
            raw_sock.shutdown(socket.SHUT_WR)  # EOF tells the harness to begin
            stdin.close()

            try:
                container.wait(timeout=limits.wall_timeout_s)
            except RequestException:
                log.warning("sandbox_wall_timeout", container=container.short_id)
                container.kill()
                return SandboxResult(
                    ok=False,
                    error=f"sandbox exceeded the {limits.wall_timeout_s}s wall-clock limit",
                )
            raw = container.logs(stdout=True, stderr=False).decode(errors="replace")
            return parse_harness_output(raw)
        finally:
            try:
                container.remove(force=True)
            except Exception:
                log.warning("sandbox_cleanup_failed", container=container.short_id)
