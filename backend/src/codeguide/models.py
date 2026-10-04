"""SQLAlchemy ORM models."""

import enum
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import JSON, Boolean, DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def _uuid() -> str:
    return uuid.uuid4().hex


def utcnow() -> datetime:
    return datetime.now(UTC)


class SubmissionStatus(enum.StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    ANALYZING = "analyzing"
    FEEDBACK = "feedback"
    COMPLETED = "completed"
    FAILED = "failed"


TERMINAL_STATUSES = {SubmissionStatus.COMPLETED, SubmissionStatus.FAILED}


class Severity(enum.StrEnum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class Category(enum.StrEnum):
    STYLE = "style"
    COMPLEXITY = "complexity"
    SECURITY = "security"
    BUG_RISK = "bug_risk"
    CORRECTNESS = "correctness"


class Base(DeclarativeBase):
    pass


class Instructor(Base):
    __tablename__ = "instructors"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(200))
    email: Mapped[str] = mapped_column(String(320), unique=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    courses: Mapped[list["Course"]] = relationship(back_populates="instructor")


class Course(Base):
    __tablename__ = "courses"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    title: Mapped[str] = mapped_column(String(300))
    join_code: Mapped[str] = mapped_column(String(12), unique=True, index=True)
    instructor_id: Mapped[str] = mapped_column(ForeignKey("instructors.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    instructor: Mapped[Instructor] = relationship(back_populates="courses")
    students: Mapped[list["Student"]] = relationship(
        back_populates="course", cascade="all, delete-orphan"
    )
    assignments: Mapped[list["Assignment"]] = relationship(
        back_populates="course", cascade="all, delete-orphan"
    )


class Student(Base):
    __tablename__ = "students"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    course_id: Mapped[str] = mapped_column(ForeignKey("courses.id"), index=True)
    display_name: Mapped[str] = mapped_column(String(120))
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    course: Mapped[Course] = relationship(back_populates="students")


class Assignment(Base):
    __tablename__ = "assignments"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    course_id: Mapped[str] = mapped_column(ForeignKey("courses.id"), index=True)
    title: Mapped[str] = mapped_column(String(300))
    description_md: Mapped[str] = mapped_column(Text)
    language: Mapped[str] = mapped_column(String(20))  # "python" | "javascript"
    entrypoint: Mapped[str] = mapped_column(String(200))  # e.g. "main.py"
    test_cases: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    analyzer_config: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    course: Mapped[Course] = relationship(back_populates="assignments")
    submissions: Mapped[list["Submission"]] = relationship(
        back_populates="assignment", cascade="all, delete-orphan"
    )


class Submission(Base):
    __tablename__ = "submissions"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    assignment_id: Mapped[str] = mapped_column(ForeignKey("assignments.id"), index=True)
    student_id: Mapped[str] = mapped_column(ForeignKey("students.id"), index=True)
    status: Mapped[SubmissionStatus] = mapped_column(
        Enum(SubmissionStatus, native_enum=False, length=20),
        default=SubmissionStatus.QUEUED,
        index=True,
    )
    files: Mapped[list[dict[str, str]]] = mapped_column(JSON)  # [{path, content}]
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    assignment: Mapped[Assignment] = relationship(back_populates="submissions")
    student: Mapped[Student] = relationship()
    test_results: Mapped[list["TestResult"]] = relationship(
        back_populates="submission", cascade="all, delete-orphan"
    )
    findings: Mapped[list["Finding"]] = relationship(
        back_populates="submission", cascade="all, delete-orphan"
    )
    feedback: Mapped["Feedback | None"] = relationship(
        back_populates="submission", cascade="all, delete-orphan"
    )


class TestResult(Base):
    __tablename__ = "test_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    submission_id: Mapped[str] = mapped_column(ForeignKey("submissions.id"), index=True)
    name: Mapped[str] = mapped_column(String(200))
    passed: Mapped[bool] = mapped_column(Boolean)
    expected: Mapped[str | None] = mapped_column(Text, nullable=True)
    actual: Mapped[str | None] = mapped_column(Text, nullable=True)
    duration_ms: Mapped[int] = mapped_column(Integer, default=0)
    timed_out: Mapped[bool] = mapped_column(Boolean, default=False)

    submission: Mapped[Submission] = relationship(back_populates="test_results")


class Finding(Base):
    __tablename__ = "findings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    submission_id: Mapped[str] = mapped_column(ForeignKey("submissions.id"), index=True)
    analyzer: Mapped[str] = mapped_column(String(40))
    rule_id: Mapped[str] = mapped_column(String(200))
    severity: Mapped[Severity] = mapped_column(Enum(Severity, native_enum=False, length=10))
    category: Mapped[Category] = mapped_column(
        Enum(Category, native_enum=False, length=15), index=True
    )
    file: Mapped[str] = mapped_column(String(500))
    line_start: Mapped[int] = mapped_column(Integer, default=0)
    line_end: Mapped[int] = mapped_column(Integer, default=0)
    message: Mapped[str] = mapped_column(Text)
    snippet: Mapped[str | None] = mapped_column(Text, nullable=True)
    misconception_tag: Mapped[str | None] = mapped_column(
        String(60), nullable=True, index=True
    )

    submission: Mapped[Submission] = relationship(back_populates="findings")


class Feedback(Base):
    __tablename__ = "feedback"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    submission_id: Mapped[str] = mapped_column(
        ForeignKey("submissions.id"), unique=True, index=True
    )
    provider: Mapped[str] = mapped_column(String(40))
    model: Mapped[str | None] = mapped_column(String(120), nullable=True)
    summary_md: Mapped[str] = mapped_column(Text)
    items: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    next_steps: Mapped[list[str]] = mapped_column(JSON, default=list)
    cached: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    submission: Mapped[Submission] = relationship(back_populates="feedback")


class FeedbackCache(Base):
    __tablename__ = "feedback_cache"

    cache_key: Mapped[str] = mapped_column(String(64), primary_key=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
