"""Queue behaviour tests using a stub execution backend (no Docker needed)."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from codeguide.config import Settings
from codeguide.execution.base import ExecutionPlan, SandboxResult, StepOutput
from codeguide.models import (
    Assignment,
    Course,
    Feedback,
    Finding,
    Instructor,
    Student,
    Submission,
    SubmissionStatus,
    TestResult,
)
from codeguide.queue import SubmissionQueue


class StubBackend:
    """Returns one bandit finding and one passing test, deterministically."""

    async def run(self, plan: ExecutionPlan) -> SandboxResult:
        return SandboxResult(
            ok=True,
            steps={
                "bandit": StepOutput(
                    exit_code=1,
                    stdout=(
                        '{"results": [{"test_id": "B608", "issue_severity": "MEDIUM",'
                        ' "issue_text": "sql", "filename": "main.py", "line_number": 1,'
                        ' "line_range": [1]}]}'
                    ),
                    stderr="",
                    duration_ms=1,
                    timed_out=False,
                )
            },
            tests=[
                {
                    "name": "t",
                    "exit_code": 0,
                    "stdout": "1",
                    "stderr": "",
                    "duration_ms": 1,
                    "timed_out": False,
                }
            ],
        )


async def _make_submission(db: AsyncSession) -> str:
    instructor = Instructor(name="I", email="i@e.edu", token_hash="h")
    db.add(instructor)
    await db.flush()
    course = Course(title="C", join_code="JOINCODE", instructor_id=instructor.id)
    db.add(course)
    await db.flush()
    assignment = Assignment(
        course_id=course.id,
        title="A",
        description_md="d",
        language="python",
        entrypoint="main.py",
        test_cases=[{"name": "t", "stdin": "", "expected_stdout": "1", "match": "trimmed"}],
    )
    student = Student(course_id=course.id, display_name="S", token_hash="s")
    db.add_all([assignment, student])
    await db.flush()
    submission = Submission(
        assignment_id=assignment.id,
        student_id=student.id,
        files=[{"path": "main.py", "content": "print(1)"}],
    )
    db.add(submission)
    await db.commit()
    return submission.id


async def test_reprocessing_is_idempotent(
    db_factory: async_sessionmaker[AsyncSession],
) -> None:
    """A submission processed twice (as happens when re-queued after a restart)
    must not accumulate duplicate findings/test results or a second feedback
    row, and must still finish COMPLETED — not FAILED."""
    async with db_factory() as db:
        submission_id = await _make_submission(db)

    settings = Settings(feedback_provider="template")
    queue = SubmissionQueue(StubBackend(), db_factory, settings)

    await queue._process(submission_id)
    await queue._process(submission_id)  # simulate a re-queue after restart

    async with db_factory() as db:
        submission = await db.get(Submission, submission_id)
        assert submission.status is SubmissionStatus.COMPLETED

        findings = list(
            await db.scalars(select(Finding).where(Finding.submission_id == submission_id))
        )
        tests = list(
            await db.scalars(select(TestResult).where(TestResult.submission_id == submission_id))
        )
        feedback = list(
            await db.scalars(select(Feedback).where(Feedback.submission_id == submission_id))
        )

    # exactly one run's worth of rows, not two
    assert len(tests) == 1
    assert len(feedback) == 1
    # bandit finding is present exactly once (no duplication)
    assert sum(1 for f in findings if f.rule_id == "B608") == 1
