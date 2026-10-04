"""Builds the ExecutionPlan for a submission."""

from codeguide.analyzers.registry import analyzers_for
from codeguide.config import Settings
from codeguide.execution.base import ExecutionPlan, Limits
from codeguide.models import Assignment, Submission


def build_plan(assignment: Assignment, submission: Submission, settings: Settings) -> ExecutionPlan:
    files = {f["path"]: f["content"] for f in submission.files}
    return ExecutionPlan(
        language=assignment.language,
        entrypoint=assignment.entrypoint,
        files=files,
        test_cases=assignment.test_cases,
        steps=[analyzer.sandbox_step() for analyzer in analyzers_for(assignment.language)],
        limits=Limits(
            cpus=settings.sandbox_cpus,
            memory_mb=settings.sandbox_memory_mb,
            pids=settings.sandbox_pids_limit,
            wall_timeout_s=settings.sandbox_wall_timeout_s,
        ),
    )


def runner_image(language: str, settings: Settings) -> str:
    return {
        "python": settings.runner_image_python,
        "javascript": settings.runner_image_node,
    }[language]
