"""Execution backend selection."""

from codeguide.config import Settings
from codeguide.execution.base import ExecutionBackend


def create_backend(settings: Settings) -> ExecutionBackend:
    if settings.execution_backend == "docker":
        from codeguide.execution.docker_backend import DockerBackend

        return DockerBackend(settings)
    if settings.execution_backend == "kubernetes":
        from codeguide.execution.k8s_backend import KubernetesBackend

        return KubernetesBackend(settings)
    from codeguide.execution.local_backend import LocalBackend

    return LocalBackend(settings)
