"""Join-code based student enrolment."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from codeguide.auth import hash_token, new_student_token
from codeguide.db import get_db
from codeguide.models import Course, Student
from codeguide.ratelimit import RateLimiter
from codeguide.schemas import CoursePublic, JoinRequest, JoinResponse

router = APIRouter(tags=["auth"])

# Per-IP limit on enrolment: a leaked join code shouldn't let one client mint
# unlimited student accounts (which would multiply the submission rate limit).
_join_limiter = RateLimiter()
_JOIN_LIMIT_PER_MINUTE = 10


@router.post("/auth/join", response_model=JoinResponse, status_code=201)
async def join_course(
    body: JoinRequest,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> JoinResponse:
    client_ip = request.client.host if request.client else "unknown"
    if not _join_limiter.check(client_ip, _JOIN_LIMIT_PER_MINUTE):
        raise HTTPException(429, "Too many join attempts — wait a minute and try again")

    course = await db.scalar(select(Course).where(Course.join_code == body.join_code.upper()))
    if course is None:
        raise HTTPException(404, "Unknown join code")

    token = new_student_token()
    student = Student(
        course_id=course.id,
        display_name=body.display_name.strip(),
        token_hash=hash_token(token),
    )
    db.add(student)
    await db.commit()

    return JoinResponse(
        student_id=student.id,
        student_token=token,
        course=CoursePublic.model_validate(course),
    )
