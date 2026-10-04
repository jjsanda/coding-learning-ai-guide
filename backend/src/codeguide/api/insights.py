"""Class-wide insights for instructors.

Everything aggregated here comes from deterministic analyzer findings and
test results — never from LLM output — so the numbers are reproducible.
"""

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import case, distinct, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from codeguide.api.courses import get_owned_course
from codeguide.db import get_db
from codeguide.models import (
    Assignment,
    Course,
    Finding,
    Student,
    Submission,
    TestResult,
)
from codeguide.schemas import (
    AssignmentPassRate,
    CategoryCount,
    CourseInsights,
    MisconceptionCount,
    SubmissionsPerDay,
)

router = APIRouter(tags=["insights"])


@router.get("/courses/{course_id}/insights", response_model=CourseInsights)
async def course_insights(
    course: Annotated[Course, Depends(get_owned_course)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> CourseInsights:
    course_submissions = (
        select(Submission.id)
        .join(Assignment, Submission.assignment_id == Assignment.id)
        .where(Assignment.course_id == course.id)
        .subquery()
    )

    misconception_rows = (
        await db.execute(
            select(
                Finding.misconception_tag,
                func.count(Finding.id),
                func.count(distinct(Submission.student_id)),
            )
            .join(Submission, Finding.submission_id == Submission.id)
            .where(
                Finding.submission_id.in_(select(course_submissions.c.id)),
                Finding.misconception_tag.is_not(None),
            )
            .group_by(Finding.misconception_tag)
            .order_by(func.count(Finding.id).desc())
        )
    ).all()

    category_rows = (
        await db.execute(
            select(Finding.category, func.count(Finding.id))
            .where(Finding.submission_id.in_(select(course_submissions.c.id)))
            .group_by(Finding.category)
            .order_by(func.count(Finding.id).desc())
        )
    ).all()

    # A submission "passes" when it has test results and none failed.
    failed_counts = (
        select(
            TestResult.submission_id.label("sid"),
            func.count(TestResult.id).label("total"),
            func.sum(case((TestResult.passed.is_(False), 1), else_=0)).label("failed"),
        )
        .group_by(TestResult.submission_id)
        .subquery()
    )
    pass_rate_rows = (
        await db.execute(
            select(
                Assignment.id,
                Assignment.title,
                func.count(Submission.id),
                func.sum(
                    case(
                        ((failed_counts.c.failed == 0) & (failed_counts.c.total > 0), 1),
                        else_=0,
                    )
                ),
            )
            .join(Submission, Submission.assignment_id == Assignment.id)
            .outerjoin(failed_counts, failed_counts.c.sid == Submission.id)
            .where(Assignment.course_id == course.id)
            .group_by(Assignment.id, Assignment.title)
            .order_by(Assignment.created_at)
        )
    ).all()

    per_day_rows = (
        await db.execute(
            select(func.date(Submission.created_at), func.count(Submission.id))
            .where(Submission.id.in_(select(course_submissions.c.id)))
            .group_by(func.date(Submission.created_at))
            .order_by(func.date(Submission.created_at))
        )
    ).all()

    total_submissions = (
        await db.scalar(
            select(func.count()).select_from(course_submissions)
        )
    ) or 0
    total_students = (
        await db.scalar(
            select(func.count(Student.id)).where(Student.course_id == course.id)
        )
    ) or 0

    return CourseInsights(
        course_id=course.id,
        total_submissions=total_submissions,
        total_students=total_students,
        misconceptions=[
            MisconceptionCount(misconception_tag=tag, count=count, affected_students=students)
            for tag, count, students in misconception_rows
        ],
        pass_rates=[
            AssignmentPassRate(
                assignment_id=aid,
                title=title,
                submissions=subs,
                pass_rate=(float(passed or 0) / subs) if subs else 0.0,
            )
            for aid, title, subs, passed in pass_rate_rows
        ],
        findings_by_category=[
            CategoryCount(category=category, count=count) for category, count in category_rows
        ],
        submissions_per_day=[
            SubmissionsPerDay(day=str(day), count=count) for day, count in per_day_rows
        ],
    )
