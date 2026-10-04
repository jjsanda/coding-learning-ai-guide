"""In-process submission queue and processing pipeline.

One backend service, an ``asyncio.Queue`` and a small worker pool: statuses
live in the database, so a restart re-queues anything that was in flight.
Pipeline per submission::

    queued -> running (sandbox) -> analyzing (normalize findings)
           -> feedback (LLM or templates) -> completed | failed
"""

import asyncio
from datetime import UTC, datetime
from typing import Any

import structlog
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from codeguide.analyzers.misconceptions import tag_for_rule
from codeguide.analyzers.registry import analyzers_for
from codeguide.config import Settings
from codeguide.execution.base import ExecutionBackend, SandboxResult
from codeguide.execution.plan import build_plan
from codeguide.models import (
    TERMINAL_STATUSES,
    Assignment,
    Category,
    Feedback,
    Finding,
    Severity,
    Submission,
    SubmissionStatus,
    TestResult,
)

log = structlog.get_logger()

_SNIPPET_CONTEXT_LINES = 2


def _outputs_match(expected: str, actual: str, mode: str) -> bool:
    if mode == "exact":
        return expected == actual
    # "trimmed": ignore trailing whitespace on each line and around the output
    def norm(s: str) -> str:
        return "\n".join(line.rstrip() for line in s.strip().splitlines())

    return norm(expected) == norm(actual)


def grade_tests(
    test_cases: list[dict[str, Any]], sandbox_tests: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Compute the pass/fail verdict server-side.

    The sandbox reports only what the program *did* (exit code + captured
    stdout/stderr); the trusted expected output lives here, in the
    orchestrator, so the verdict can never be forged from inside the sandbox.
    """
    expected_by_name = {tc["name"]: tc for tc in test_cases}
    graded: list[dict[str, Any]] = []
    for run in sandbox_tests:
        case = expected_by_name.get(run.get("name", ""))
        expected = case.get("expected_stdout", "") if case else ""
        match_mode = case.get("match", "trimmed") if case else "trimmed"
        stdout = run.get("stdout", "")
        stderr = run.get("stderr", "")
        timed_out = bool(run.get("timed_out"))
        exit_code = run.get("exit_code", -1)
        passed = (
            not timed_out
            and exit_code == 0
            and case is not None
            and _outputs_match(expected, stdout, match_mode)
        )
        graded.append(
            {
                "name": run.get("name", "?"),
                "passed": passed,
                "expected": expected,
                # surface stderr in the shown output when the program errored
                "actual": stdout if exit_code == 0 else (stdout + stderr),
                "duration_ms": int(run.get("duration_ms", 0)),
                "timed_out": timed_out,
            }
        )
    return graded


def extract_snippet(
    files: list[dict[str, str]], path: str, line_start: int, line_end: int
) -> str | None:
    """±2 lines of the student's code around a finding, for feedback context."""
    content = next((f["content"] for f in files if f["path"] == path), None)
    if content is None or line_start <= 0:
        return None
    lines = content.splitlines()
    lo = max(0, line_start - 1 - _SNIPPET_CONTEXT_LINES)
    hi = min(len(lines), max(line_end, line_start) + _SNIPPET_CONTEXT_LINES)
    return "\n".join(lines[lo:hi]) or None


class SubmissionQueue:
    def __init__(
        self,
        backend: ExecutionBackend,
        session_factory: async_sessionmaker[AsyncSession],
        settings: Settings,
    ) -> None:
        self._backend = backend
        self._session_factory = session_factory
        self._settings = settings
        self._queue: asyncio.Queue[str] = asyncio.Queue()
        self._workers: list[asyncio.Task[None]] = []

    async def start(self) -> None:
        await self._requeue_interrupted()
        for index in range(self._settings.worker_concurrency):
            self._workers.append(asyncio.create_task(self._worker(index)))
        log.info("queue_started", workers=len(self._workers))

    async def stop(self) -> None:
        for task in self._workers:
            task.cancel()
        await asyncio.gather(*self._workers, return_exceptions=True)
        self._workers.clear()

    async def enqueue(self, submission_id: str) -> None:
        await self._queue.put(submission_id)

    async def _requeue_interrupted(self) -> None:
        """Re-queue submissions left in a non-terminal state by a restart."""
        async with self._session_factory() as db:
            result = await db.scalars(
                select(Submission.id).where(
                    Submission.status.not_in(list(TERMINAL_STATUSES))
                )
            )
            interrupted = list(result)
        for submission_id in interrupted:
            await self._queue.put(submission_id)
        if interrupted:
            log.info("requeued_interrupted_submissions", count=len(interrupted))

    async def _worker(self, index: int) -> None:
        while True:
            submission_id = await self._queue.get()
            structlog.contextvars.bind_contextvars(submission_id=submission_id)
            try:
                await self._process(submission_id)
            except Exception as exc:
                log.exception("submission_processing_failed")
                await self._mark_failed(submission_id, f"internal error: {type(exc).__name__}")
            finally:
                structlog.contextvars.unbind_contextvars("submission_id")
                self._queue.task_done()

    async def _clear_prior_results(self, db: AsyncSession, submission_id: str) -> None:
        for model in (Finding, TestResult, Feedback):
            await db.execute(delete(model).where(model.submission_id == submission_id))
        await db.commit()

    async def _process(self, submission_id: str) -> None:
        async with self._session_factory() as db:
            submission = await db.get(Submission, submission_id)
            if submission is None or submission.status in TERMINAL_STATUSES:
                return
            assignment = await db.get(Assignment, submission.assignment_id)
            if assignment is None:
                await self._set_status(
                    db, submission, SubmissionStatus.FAILED, error="assignment vanished"
                )
                return

            # Reprocessing must be idempotent: a submission re-queued after a
            # restart (see _requeue_interrupted) may already have partial child
            # rows from its interrupted run. Clear them so we don't duplicate
            # findings/test results or violate the one-feedback-per-submission
            # constraint.
            await self._clear_prior_results(db, submission.id)

            await self._set_status(db, submission, SubmissionStatus.RUNNING)
            submission.started_at = datetime.now(UTC)
            await db.commit()

            plan = build_plan(assignment, submission, self._settings)
            result = await self._backend.run(plan)
            log.info(
                "sandbox_finished",
                ok=result.ok,
                steps=list(result.steps),
                tests=len(result.tests),
            )

            if not result.ok:
                await self._set_status(
                    db,
                    submission,
                    SubmissionStatus.FAILED,
                    error=result.error or "sandbox failed",
                )
                return

            await self._set_status(db, submission, SubmissionStatus.ANALYZING)
            graded = grade_tests(assignment.test_cases, result.tests)
            self._store_test_results(db, submission, graded)
            self._store_findings(db, submission, assignment, result, graded)
            await db.commit()

            await self._set_status(db, submission, SubmissionStatus.FEEDBACK)
            try:
                from codeguide.feedback.service import generate_and_store_feedback

                await generate_and_store_feedback(db, submission, assignment)
            except Exception:
                log.exception("feedback_generation_failed")

            submission.completed_at = datetime.now(UTC)
            await self._set_status(db, submission, SubmissionStatus.COMPLETED)

    def _store_test_results(
        self, db: AsyncSession, submission: Submission, graded: list[dict[str, object]]
    ) -> None:
        for test in graded:
            db.add(
                TestResult(
                    submission_id=submission.id,
                    name=str(test["name"])[:200],
                    passed=bool(test["passed"]),
                    expected=test.get("expected"),
                    actual=test.get("actual"),
                    duration_ms=int(test["duration_ms"]),  # type: ignore[call-overload]
                    timed_out=bool(test["timed_out"]),
                )
            )

    def _store_findings(
        self,
        db: AsyncSession,
        submission: Submission,
        assignment: Assignment,
        result: SandboxResult,
        graded: list[dict[str, object]],
    ) -> None:
        for analyzer in analyzers_for(assignment.language):
            output = result.steps.get(analyzer.name)
            if output is None:
                continue
            for finding in analyzer.parse(output):
                db.add(
                    Finding(
                        submission_id=submission.id,
                        analyzer=finding.analyzer,
                        rule_id=finding.rule_id,
                        severity=finding.severity,
                        category=finding.category,
                        file=finding.file,
                        line_start=finding.line_start,
                        line_end=finding.line_end,
                        message=finding.message,
                        snippet=extract_snippet(
                            submission.files, finding.file, finding.line_start, finding.line_end
                        ),
                        misconception_tag=tag_for_rule(finding.rule_id),
                    )
                )

        # Failing tests become correctness findings so they reach feedback
        # and the instructor insights exactly like analyzer findings do.
        for test in graded:
            if test.get("passed"):
                continue
            name = test.get("name", "?")
            message = (
                f"Test '{name}' timed out — the program never finished."
                if test.get("timed_out")
                else f"Test '{name}' failed: the program's output did not match "
                "the expected output."
            )
            db.add(
                Finding(
                    submission_id=submission.id,
                    analyzer="tests",
                    rule_id="test-timeout" if test.get("timed_out") else "test-failure",
                    severity=Severity.ERROR,
                    category=Category.CORRECTNESS,
                    file=assignment.entrypoint,
                    line_start=0,
                    line_end=0,
                    message=message,
                    snippet=None,
                    misconception_tag="infinite-loop" if test.get("timed_out") else None,
                )
            )

    async def _set_status(
        self,
        db: AsyncSession,
        submission: Submission,
        status: SubmissionStatus,
        *,
        error: str | None = None,
    ) -> None:
        submission.status = status
        if error is not None:
            submission.error = error
            submission.completed_at = datetime.now(UTC)
        await db.commit()
        log.info("submission_status", status=status)

    async def _mark_failed(self, submission_id: str, error: str) -> None:
        try:
            async with self._session_factory() as db:
                submission = await db.get(Submission, submission_id)
                if submission is not None and submission.status not in TERMINAL_STATUSES:
                    await self._set_status(db, submission, SubmissionStatus.FAILED, error=error)
        except Exception:
            log.exception("mark_failed_failed")
