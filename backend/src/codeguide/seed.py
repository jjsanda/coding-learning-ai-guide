"""Demo data seeding: courses, assignments and real, analyzed submissions.

Every seeded submission is run through the actual sandbox + analysis +
feedback pipeline, so the instructor dashboard shows genuine aggregated
data. Idempotent per instructor: re-seeding replaces the demo courses.
"""

import asyncio

import structlog
from sqlalchemy import select

from codeguide.auth import hash_token, new_instructor_token, new_join_code, new_student_token
from codeguide.config import get_settings
from codeguide.db import get_session_factory
from codeguide.demo_content import demo_courses
from codeguide.execution.factory import create_backend
from codeguide.models import (
    Assignment,
    Course,
    Instructor,
    Student,
    Submission,
    SubmissionStatus,
)
from codeguide.queue import SubmissionQueue

log = structlog.get_logger()

SEED_INSTRUCTOR_EMAIL = "instructor@codeguide.example"


async def _ensure_instructor(db) -> tuple[Instructor, str | None]:  # type: ignore[no-untyped-def]
    instructor = await db.scalar(
        select(Instructor).where(Instructor.email == SEED_INSTRUCTOR_EMAIL)
    )
    if instructor is not None:
        return instructor, None
    token = new_instructor_token()
    instructor = Instructor(
        name="Demo Instructor",
        email=SEED_INSTRUCTOR_EMAIL,
        token_hash=hash_token(token),
    )
    db.add(instructor)
    await db.flush()
    return instructor, token


async def run_seed() -> int:
    settings = get_settings()
    session_factory = get_session_factory()

    async with session_factory() as db:
        instructor, instructor_token = await _ensure_instructor(db)

        # Clear any previous demo courses for a clean re-seed. ORM cascade
        # deletes assignments, students, submissions, findings and feedback.
        old = list(
            await db.scalars(select(Course).where(Course.instructor_id == instructor.id))
        )
        for course in old:
            await db.delete(course)
        await db.flush()

        join_codes: dict[str, str] = {}
        submissions_to_run: list[str] = []
        student_tokens: dict[str, str] = {}

        for demo_course in demo_courses():
            course = Course(
                title=demo_course.title,
                join_code=new_join_code(),
                instructor_id=instructor.id,
            )
            db.add(course)
            await db.flush()
            join_codes[demo_course.title] = course.join_code

            students: dict[str, Student] = {}

            for demo_assignment in demo_course.assignments:
                assignment = Assignment(
                    course_id=course.id,
                    title=demo_assignment.title,
                    description_md=demo_assignment.description_md,
                    language=demo_assignment.language,
                    entrypoint=demo_assignment.entrypoint,
                    test_cases=demo_assignment.test_cases,
                )
                db.add(assignment)
                await db.flush()

                for demo_sub in demo_assignment.submissions:
                    if demo_sub.student not in students:
                        token = new_student_token()
                        student = Student(
                            course_id=course.id,
                            display_name=demo_sub.student,
                            token_hash=hash_token(token),
                        )
                        db.add(student)
                        await db.flush()
                        students[demo_sub.student] = student
                        student_tokens.setdefault(demo_sub.student, token)
                    student = students[demo_sub.student]
                    submission = Submission(
                        assignment_id=assignment.id,
                        student_id=student.id,
                        files=[
                            {"path": p, "content": c} for p, c in demo_sub.files.items()
                        ],
                    )
                    db.add(submission)
                    await db.flush()
                    submissions_to_run.append(submission.id)

        await db.commit()

    # Run every seeded submission through the real pipeline.
    queue = SubmissionQueue(create_backend(settings), session_factory, settings)
    await queue.start()
    try:
        for submission_id in submissions_to_run:
            await queue.enqueue(submission_id)
        await _wait_for_completion(session_factory, submissions_to_run)
    finally:
        await queue.stop()

    print("\nDemo data ready.\n")
    print("Course join codes (students use these at /join):")
    for title, code in join_codes.items():
        print(f"  {code}   {title}")
    if instructor_token:
        print("\nInstructor API token (shown once — sign in at /instructor):")
        print(f"  {instructor_token}")
    else:
        print(
            "\nInstructor already existed; reuse the token from the first seed, "
            "or run `create-instructor` for a new one."
        )
    print(f"\nProcessed {len(submissions_to_run)} submissions through the sandbox.")
    return 0


async def _wait_for_completion(session_factory, submission_ids: list[str]) -> None:  # type: ignore[no-untyped-def]
    remaining = set(submission_ids)
    for _ in range(600):
        await asyncio.sleep(1)
        async with session_factory() as db:
            rows = await db.execute(
                select(Submission.id, Submission.status).where(
                    Submission.id.in_(remaining)
                )
            )
            done = {
                sid
                for sid, status in rows
                if status in (SubmissionStatus.COMPLETED, SubmissionStatus.FAILED)
            }
        remaining -= done
        log.info(
            "seed_progress",
            done=len(submission_ids) - len(remaining),
            total=len(submission_ids),
        )
        if not remaining:
            return
    log.warning("seed_timeout", still_pending=len(remaining))
