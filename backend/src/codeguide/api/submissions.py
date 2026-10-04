"""Submission intake and retrieval."""

import re
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from codeguide.api.assignments import get_visible_assignment
from codeguide.api.courses import get_owned_course
from codeguide.auth import get_current_student, get_student_or_instructor
from codeguide.config import get_settings
from codeguide.db import get_db
from codeguide.models import Assignment, Course, Instructor, Student, Submission
from codeguide.ratelimit import RateLimiter
from codeguide.schemas import (
    FeedbackItem,
    FeedbackOut,
    SubmissionAccepted,
    SubmissionCreate,
    SubmissionOut,
    SubmissionSummary,
)

router = APIRouter(tags=["submissions"])

_SAFE_PATH = re.compile(r"^[\w\-./]+$")

rate_limiter = RateLimiter()


def _validate_files(body: SubmissionCreate, entrypoint: str) -> None:
    settings = get_settings()
    if len(body.files) > settings.max_files_per_submission:
        raise HTTPException(413, f"At most {settings.max_files_per_submission} files")
    total = sum(len(f.content.encode()) for f in body.files)
    if total > settings.max_submission_bytes:
        raise HTTPException(413, f"Submission exceeds {settings.max_submission_bytes} bytes")
    seen: set[str] = set()
    for file in body.files:
        path = file.path
        if (
            not _SAFE_PATH.match(path)
            or path.startswith("/")
            or ".." in path.split("/")
            or path == "plan.json"
        ):
            raise HTTPException(422, f"Invalid file path: {path!r}")
        if path in seen:
            raise HTTPException(422, f"Duplicate file path: {path!r}")
        seen.add(path)
    if entrypoint not in seen:
        raise HTTPException(422, f"Submission must include the entrypoint file {entrypoint!r}")


@router.post(
    "/assignments/{assignment_id}/submissions",
    response_model=SubmissionAccepted,
    status_code=202,
)
async def create_submission(
    body: SubmissionCreate,
    request: Request,
    assignment: Annotated[Assignment, Depends(get_visible_assignment)],
    student: Annotated[Student, Depends(get_current_student)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> SubmissionAccepted:
    settings = get_settings()
    if not rate_limiter.check(student.id, settings.submission_rate_limit_per_minute):
        raise HTTPException(429, "Too many submissions — wait a minute and try again")
    _validate_files(body, assignment.entrypoint)

    submission = Submission(
        assignment_id=assignment.id,
        student_id=student.id,
        files=[f.model_dump() for f in body.files],
    )
    db.add(submission)
    await db.commit()

    queue = getattr(request.app.state, "submission_queue", None)
    if queue is not None:
        await queue.enqueue(submission.id)

    return SubmissionAccepted(submission_id=submission.id, status=submission.status)


async def _load_authorized_submission(
    submission_id: str,
    principal: Student | Instructor,
    db: AsyncSession,
) -> Submission:
    submission = await db.scalar(
        select(Submission)
        .where(Submission.id == submission_id)
        .options(selectinload(Submission.test_results), selectinload(Submission.findings))
    )
    if submission is None:
        raise HTTPException(404, "Submission not found")

    if isinstance(principal, Student):
        if submission.student_id != principal.id:
            raise HTTPException(404, "Submission not found")
    else:
        assignment = await db.get(Assignment, submission.assignment_id)
        course = await db.get(Course, assignment.course_id) if assignment else None
        if course is None or course.instructor_id != principal.id:
            raise HTTPException(404, "Submission not found")
    return submission


@router.get("/courses/{course_id}/submissions", response_model=list[SubmissionSummary])
async def list_course_submissions(
    course: Annotated[Course, Depends(get_owned_course)],
    db: Annotated[AsyncSession, Depends(get_db)],
    assignment_id: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[Submission]:
    query = (
        select(Submission)
        .join(Assignment, Submission.assignment_id == Assignment.id)
        .where(Assignment.course_id == course.id)
        .order_by(Submission.created_at.desc())
        .limit(min(limit, 500))
        .offset(offset)
    )
    if assignment_id is not None:
        query = query.where(Submission.assignment_id == assignment_id)
    return list(await db.scalars(query))


@router.get("/submissions/{submission_id}", response_model=SubmissionOut)
async def get_submission(
    submission_id: str,
    principal: Annotated[Student | Instructor, Depends(get_student_or_instructor)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Submission:
    return await _load_authorized_submission(submission_id, principal, db)


@router.get("/submissions/{submission_id}/feedback", response_model=FeedbackOut)
async def get_feedback(
    submission_id: str,
    principal: Annotated[Student | Instructor, Depends(get_student_or_instructor)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> FeedbackOut:
    submission = await _load_authorized_submission(submission_id, principal, db)
    await db.refresh(submission, ["feedback"])
    if submission.feedback is None:
        raise HTTPException(404, "Feedback not available (yet)")
    fb = submission.feedback
    return FeedbackOut(
        submission_id=submission.id,
        provider=fb.provider,
        model=fb.model,
        summary_md=fb.summary_md,
        items=[FeedbackItem(**item) for item in fb.items],
        next_steps=fb.next_steps,
        cached=fb.cached,
        created_at=fb.created_at,
    )
