"""End-to-end pipeline test: queue -> Docker sandbox -> analyzers -> findings.

The Phase gate for the analysis pipeline: a deliberately vulnerable Python
submission must come out tagged with the headline security misconceptions.
"""

import asyncio
from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from codeguide.auth import hash_token
from codeguide.config import Settings
from codeguide.execution.docker_backend import DockerBackend
from codeguide.models import (
    Assignment,
    Course,
    Finding,
    Instructor,
    Student,
    Submission,
    SubmissionStatus,
)
from codeguide.queue import SubmissionQueue

pytestmark = pytest.mark.integration

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


async def test_vulnerable_submission_yields_tagged_findings(
    db_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with db_factory() as db:
        instructor = Instructor(name="I", email="i@example.edu", token_hash=hash_token("cgi_x"))
        db.add(instructor)
        await db.flush()
        course = Course(title="C", join_code="JOINCODE", instructor_id=instructor.id)
        db.add(course)
        await db.flush()
        assignment = Assignment(
            course_id=course.id,
            title="User lookup",
            description_md="d",
            language="python",
            entrypoint="main.py",
            test_cases=[],
        )
        student = Student(course_id=course.id, display_name="S", token_hash=hash_token("cgs_x"))
        db.add_all([assignment, student])
        await db.flush()
        submission = Submission(
            assignment_id=assignment.id,
            student_id=student.id,
            files=[
                {
                    "path": "main.py",
                    "content": (FIXTURES / "vulnerable_python.py.txt").read_text(),
                }
            ],
        )
        db.add(submission)
        await db.commit()
        submission_id = submission.id

    settings = Settings()
    queue = SubmissionQueue(DockerBackend(settings), db_factory, settings)
    await queue.start()
    try:
        await queue.enqueue(submission_id)
        async with db_factory() as db:
            for _ in range(120):
                await asyncio.sleep(1)
                fresh = await db.get(Submission, submission_id)
                await db.refresh(fresh)
                if fresh.status in (SubmissionStatus.COMPLETED, SubmissionStatus.FAILED):
                    break
            assert fresh.status is SubmissionStatus.COMPLETED, fresh.error

            findings = list(
                await db.scalars(select(Finding).where(Finding.submission_id == submission_id))
            )
            await db.refresh(fresh, ["feedback"])
            feedback = fresh.feedback
    finally:
        await queue.stop()

    tags = {f.misconception_tag for f in findings if f.misconception_tag}
    assert {
        "sql-injection",
        "hardcoded-secret",
        "unsafe-deserialization",
        "command-injection",
        "eval-injection",
    } <= tags

    with_snippets = [f for f in findings if f.snippet]
    assert with_snippets, "expected code snippets on findings"
    analyzers_seen = {f.analyzer for f in findings}
    assert {"ruff", "bandit", "radon", "semgrep"} <= analyzers_seen

    # Feedback must be complete even with no LLM key configured (template mode).
    assert feedback is not None
    assert feedback.summary_md
    assert feedback.items, "expected feedback items for a vulnerable submission"
    tags_in_feedback = {i.get("misconception_tag") for i in feedback.items}
    assert "sql-injection" in tags_in_feedback
