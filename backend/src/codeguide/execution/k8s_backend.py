"""Kubernetes Jobs execution backend (used by the Helm deployment).

Each submission runs as a one-shot Job in a locked-down sandbox namespace:

* files + plan.json are delivered via a read-only ConfigMap mounted at
  ``/work-src``; the harness copies them into a writable emptyDir at ``/work``
* the pod runs non-root, read-only rootfs, all capabilities dropped,
  ``seccompProfile: RuntimeDefault``, no privilege escalation
* an optional gVisor ``runtimeClassName`` adds kernel-level isolation
* a NetworkPolicy in the namespace denies all ingress and egress — results
  come back via pod logs, so the sandbox never needs a socket
* ``activeDeadlineSeconds`` bounds wall-clock time; ``ttlSecondsAfterFinished``
  and explicit cleanup reap the Job and ConfigMap
"""

import asyncio
import base64
import json
import time

import structlog

from codeguide.config import Settings
from codeguide.execution.base import ExecutionPlan, SandboxResult, parse_harness_output
from codeguide.execution.plan import runner_image

log = structlog.get_logger()

_SANDBOX_UID = 65534


class KubernetesBackend:
    def __init__(self, settings: Settings) -> None:
        from kubernetes import client, config

        try:
            config.load_incluster_config()
        except config.ConfigException:
            config.load_kube_config()

        self._settings = settings
        self._core = client.CoreV1Api()
        self._batch = client.BatchV1Api()
        self._namespace = settings.k8s_sandbox_namespace

    async def run(self, plan: ExecutionPlan) -> SandboxResult:
        return await asyncio.to_thread(self._run_sync, plan)

    def _run_sync(self, plan: ExecutionPlan) -> SandboxResult:
        from kubernetes import client, watch

        name = f"sub-{_short_id()}"
        self._create_configmap(name, plan)
        try:
            self._create_job(name, plan)
            result = self._await_result(name, plan, client, watch)
            return result
        finally:
            self._cleanup(name)

    def _create_configmap(self, name: str, plan: ExecutionPlan) -> None:
        from kubernetes import client

        data = dict(plan.files)
        data["plan.json"] = json.dumps(plan.harness_payload())
        self._core.create_namespaced_config_map(
            namespace=self._namespace,
            body=client.V1ConfigMap(
                metadata=client.V1ObjectMeta(
                    name=name, labels={"app": "coding-learning-ai-guide", "role": "sandbox"}
                ),
                data=data,
            ),
        )

    def _create_job(self, name: str, plan: ExecutionPlan) -> None:
        from kubernetes import client

        limits = plan.limits
        security_context = client.V1SecurityContext(
            run_as_non_root=True,
            run_as_user=_SANDBOX_UID,
            run_as_group=_SANDBOX_UID,
            allow_privilege_escalation=False,
            read_only_root_filesystem=True,
            capabilities=client.V1Capabilities(drop=["ALL"]),
            seccomp_profile=client.V1SeccompProfile(type="RuntimeDefault"),
        )
        container = client.V1Container(
            name="runner",
            image=runner_image(plan.language, self._settings),
            image_pull_policy=self._settings.k8s_runner_pull_policy,
            volume_mounts=[
                client.V1VolumeMount(name="src", mount_path="/work-src", read_only=True),
                client.V1VolumeMount(name="work", mount_path="/work"),
                client.V1VolumeMount(name="tmp", mount_path="/tmp"),  # noqa: S108
            ],
            resources=client.V1ResourceRequirements(
                limits={
                    "cpu": str(limits.cpus),
                    "memory": f"{limits.memory_mb}Mi",
                    # cap writable scratch so a submission can't fill the node disk
                    "ephemeral-storage": f"{2 * limits.memory_mb}Mi",
                },
                requests={"cpu": "100m", "memory": "128Mi"},
            ),
            security_context=security_context,
        )
        # Size-limited scratch dirs so a submission can't fill the node disk.
        def scratch() -> "client.V1EmptyDirVolumeSource":
            return client.V1EmptyDirVolumeSource(size_limit=f"{limits.memory_mb}Mi")

        pod_spec = client.V1PodSpec(
            restart_policy="Never",
            automount_service_account_token=False,
            containers=[container],
            volumes=[
                client.V1Volume(
                    name="src", config_map=client.V1ConfigMapVolumeSource(name=name)
                ),
                client.V1Volume(name="work", empty_dir=scratch()),
                client.V1Volume(name="tmp", empty_dir=scratch()),
            ],
        )
        if self._settings.k8s_gvisor_runtime_class:
            pod_spec.runtime_class_name = self._settings.k8s_gvisor_runtime_class

        self._batch.create_namespaced_job(
            namespace=self._namespace,
            body=client.V1Job(
                metadata=client.V1ObjectMeta(
                    name=name, labels={"app": "coding-learning-ai-guide", "role": "sandbox"}
                ),
                spec=client.V1JobSpec(
                    backoff_limit=0,
                    active_deadline_seconds=self._settings.k8s_active_deadline_s,
                    ttl_seconds_after_finished=300,
                    template=client.V1PodTemplateSpec(
                        metadata=client.V1ObjectMeta(
                            labels={"app": "coding-learning-ai-guide", "role": "sandbox"}
                        ),
                        spec=pod_spec,
                    ),
                ),
            ),
        )

    def _await_result(self, name: str, plan: ExecutionPlan, client_mod, watch_mod) -> SandboxResult:  # type: ignore[no-untyped-def]
        deadline = plan.limits.wall_timeout_s
        w = watch_mod.Watch()
        try:
            for event in w.stream(
                self._batch.list_namespaced_job,
                namespace=self._namespace,
                field_selector=f"metadata.name={name}",
                timeout_seconds=deadline,
            ):
                status = event["object"].status
                if status.succeeded or status.failed:
                    w.stop()
                    break
        finally:
            w.stop()

        pods = self._core.list_namespaced_pod(
            namespace=self._namespace, label_selector=f"job-name={name}"
        )
        if not pods.items:
            return SandboxResult(ok=False, error="sandbox pod never scheduled")
        pod_name = pods.items[0].metadata.name

        # The Job can report completion a beat before the container's logs are
        # readable; retry briefly on an empty read.
        raw = ""
        for _ in range(10):
            try:
                # _preload_content=False returns the raw HTTP response so the
                # body is decoded as text rather than str(bytes) ("b'...'").
                resp = self._core.read_namespaced_pod_log(
                    name=pod_name,
                    namespace=self._namespace,
                    container="runner",
                    _preload_content=False,
                )
                attempt = resp.data.decode("utf-8", errors="replace")
                if attempt:  # keep the best read; a later transient error must not wipe it
                    raw = attempt
            except client_mod.exceptions.ApiException as exc:
                log.warning("sandbox_log_read_retry", pod=pod_name, error=str(exc))
            if raw and "===CODEGUIDE_RESULT" in raw:
                break
            time.sleep(0.5)

        if not raw:
            return SandboxResult(ok=False, error="sandbox produced no logs")
        return parse_harness_output(raw)

    def _cleanup(self, name: str) -> None:
        from kubernetes import client

        opts = client.V1DeleteOptions(propagation_policy="Background")
        try:
            self._batch.delete_namespaced_job(name, self._namespace, body=opts)
        except Exception:  # never mask the run result
            log.warning("sandbox_job_cleanup_failed", name=name)
        try:
            self._core.delete_namespaced_config_map(name, self._namespace)
        except Exception:
            log.warning("sandbox_configmap_cleanup_failed", name=name)


def _short_id() -> str:
    import secrets

    return base64.b32encode(secrets.token_bytes(6)).decode().rstrip("=").lower()
