"""Course management (instructor-only)."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from codeguide.auth import get_current_instructor, new_join_code
from codeguide.db import get_db
from codeguide.models import Course, Instructor
from codeguide.schemas import CourseCreate, CourseOut

router = APIRouter(tags=["courses"])


async def get_owned_course(
    course_id: str,
    instructor: Annotated[Instructor, Depends(get_current_instructor)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Course:
    course = await db.get(Course, course_id)
    if course is None or course.instructor_id != instructor.id:
        # 404 for both cases: do not reveal other instructors' course IDs
        raise HTTPException(404, "Course not found")
    return course


@router.post("/courses", response_model=CourseOut, status_code=201)
async def create_course(
    body: CourseCreate,
    instructor: Annotated[Instructor, Depends(get_current_instructor)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Course:
    course = Course(
        title=body.title.strip(), join_code=new_join_code(), instructor_id=instructor.id
    )
    db.add(course)
    await db.commit()
    return course


@router.get("/courses", response_model=list[CourseOut])
async def list_courses(
    instructor: Annotated[Instructor, Depends(get_current_instructor)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[Course]:
    result = await db.scalars(
        select(Course).where(Course.instructor_id == instructor.id).order_by(Course.created_at)
    )
    return list(result)


@router.get("/courses/{course_id}", response_model=CourseOut)
async def get_course(course: Annotated[Course, Depends(get_owned_course)]) -> Course:
    return course
