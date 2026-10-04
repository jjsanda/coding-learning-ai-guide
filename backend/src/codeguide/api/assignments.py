"""Assignment management and student-facing assignment views."""

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from codeguide.api.courses import get_owned_course
from codeguide.auth import get_student_or_instructor
from codeguide.db import get_db
from codeguide.models import Assignment, Course, Instructor, Student
from codeguide.schemas import (
    AssignmentCreate,
    AssignmentOut,
    AssignmentSummary,
    TestCaseStudentView,
)

router = APIRouter(tags=["assignments"])


def _student_view(assignment: Assignment, *, full: bool) -> AssignmentOut:
    """Instructors see everything; students see hidden cases by name only."""
    cases = []
    for tc in assignment.test_cases:
        visible = bool(tc.get("visible", True))
        if full or visible:
            cases.append(
                TestCaseStudentView(
                    name=tc["name"],
                    stdin=tc.get("stdin", ""),
                    expected_stdout=tc.get("expected_stdout"),
                    visible=visible,
                )
            )
        else:
            cases.append(TestCaseStudentView(name=tc["name"], visible=False))
    return AssignmentOut(
        id=assignment.id,
        course_id=assignment.course_id,
        title=assignment.title,
        description_md=assignment.description_md,
        language=assignment.language,  # type: ignore[arg-type]
        entrypoint=assignment.entrypoint,
        test_cases=cases,
        created_at=assignment.created_at,
    )


async def get_visible_assignment(
    assignment_id: str,
    principal: Annotated[Student | Instructor, Depends(get_student_or_instructor)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Assignment:
    assignment = await db.get(Assignment, assignment_id)
    if assignment is None:
        raise HTTPException(404, "Assignment not found")
    if isinstance(principal, Student):
        if principal.course_id != assignment.course_id:
            raise HTTPException(404, "Assignment not found")
    else:
        course = await db.get(Course, assignment.course_id)
        if course is None or course.instructor_id != principal.id:
            raise HTTPException(404, "Assignment not found")
    return assignment


@router.post("/courses/{course_id}/assignments", response_model=AssignmentOut, status_code=201)
async def create_assignment(
    body: AssignmentCreate,
    course: Annotated[Course, Depends(get_owned_course)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AssignmentOut:
    test_cases: list[dict[str, Any]] = [tc.model_dump() for tc in body.test_cases]
    assignment = Assignment(
        course_id=course.id,
        title=body.title.strip(),
        description_md=body.description_md,
        language=body.language,
        entrypoint=body.entrypoint,
        test_cases=test_cases,
        analyzer_config=body.analyzer_config,
    )
    db.add(assignment)
    await db.commit()
    return _student_view(assignment, full=True)


@router.get("/courses/{course_id}/assignments", response_model=list[AssignmentSummary])
async def list_assignments(
    course_id: str,
    principal: Annotated[Student | Instructor, Depends(get_student_or_instructor)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[Assignment]:
    if isinstance(principal, Student):
        if principal.course_id != course_id:
            raise HTTPException(404, "Course not found")
    else:
        course = await db.get(Course, course_id)
        if course is None or course.instructor_id != principal.id:
            raise HTTPException(404, "Course not found")
    result = await db.scalars(
        select(Assignment).where(Assignment.course_id == course_id).order_by(Assignment.created_at)
    )
    return list(result)


@router.get("/assignments/{assignment_id}", response_model=AssignmentOut)
async def get_assignment(
    assignment: Annotated[Assignment, Depends(get_visible_assignment)],
    principal: Annotated[Student | Instructor, Depends(get_student_or_instructor)],
) -> AssignmentOut:
    return _student_view(assignment, full=isinstance(principal, Instructor))
