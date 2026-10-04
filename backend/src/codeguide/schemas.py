"""Pydantic schemas for the public API."""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from codeguide.models import Category, Severity, SubmissionStatus

Language = Literal["python", "javascript"]


# --- auth ---------------------------------------------------------------


class JoinRequest(BaseModel):
    join_code: str = Field(min_length=4, max_length=12)
    display_name: str = Field(min_length=1, max_length=120)


class CoursePublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    title: str


class JoinResponse(BaseModel):
    student_id: str
    student_token: str
    course: CoursePublic


# --- courses ------------------------------------------------------------


class CourseCreate(BaseModel):
    title: str = Field(min_length=1, max_length=300)


class CourseOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    title: str
    join_code: str
    created_at: datetime


# --- assignments ----------------------------------------------------------


class TestCase(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    stdin: str = ""
    expected_stdout: str
    match: Literal["exact", "trimmed"] = "trimmed"
    timeout_ms: int = Field(default=5000, ge=100, le=30_000)
    visible: bool = True


class AssignmentCreate(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    description_md: str
    language: Language
    entrypoint: str = Field(min_length=1, max_length=200)
    test_cases: list[TestCase] = []
    analyzer_config: dict[str, Any] | None = None


class TestCaseStudentView(BaseModel):
    """What a student may see: expected output only for visible cases."""

    name: str
    stdin: str | None = None
    expected_stdout: str | None = None
    visible: bool


class AssignmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    course_id: str
    title: str
    description_md: str
    language: Language
    entrypoint: str
    test_cases: list[TestCaseStudentView]
    created_at: datetime


class AssignmentSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    course_id: str
    title: str
    language: Language
    created_at: datetime


# --- submissions ----------------------------------------------------------


class SubmissionFile(BaseModel):
    path: str = Field(min_length=1, max_length=200)
    content: str


class SubmissionCreate(BaseModel):
    files: list[SubmissionFile] = Field(min_length=1)


class SubmissionAccepted(BaseModel):
    submission_id: str
    status: SubmissionStatus


class TestResultOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    name: str
    passed: bool
    expected: str | None
    actual: str | None
    duration_ms: int
    timed_out: bool


class FindingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    analyzer: str
    rule_id: str
    severity: Severity
    category: Category
    file: str
    line_start: int
    line_end: int
    message: str
    snippet: str | None
    misconception_tag: str | None


class SubmissionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    assignment_id: str
    student_id: str
    status: SubmissionStatus
    error: str | None
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None
    test_results: list[TestResultOut] = []
    findings: list[FindingOut] = []


class SubmissionSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    assignment_id: str
    student_id: str
    status: SubmissionStatus
    created_at: datetime


# --- feedback -------------------------------------------------------------


class FeedbackItem(BaseModel):
    finding_ref: int | None = None
    explanation_md: str
    hint_md: str = ""
    misconception_tag: str | None = None


class FeedbackOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    submission_id: str
    provider: str
    model: str | None
    summary_md: str
    items: list[FeedbackItem]
    next_steps: list[str]
    cached: bool
    created_at: datetime


# --- insights ---------------------------------------------------------------


class MisconceptionCount(BaseModel):
    misconception_tag: str
    count: int
    affected_students: int


class AssignmentPassRate(BaseModel):
    assignment_id: str
    title: str
    submissions: int
    pass_rate: float  # fraction of submissions with all tests passing


class CategoryCount(BaseModel):
    category: Category
    count: int


class SubmissionsPerDay(BaseModel):
    day: str  # ISO date
    count: int


class CourseInsights(BaseModel):
    course_id: str
    total_submissions: int
    total_students: int
    misconceptions: list[MisconceptionCount]
    pass_rates: list[AssignmentPassRate]
    findings_by_category: list[CategoryCount]
    submissions_per_day: list[SubmissionsPerDay]


# --- meta -------------------------------------------------------------------


class Meta(BaseModel):
    version: str
    execution_backend: str
    feedback_provider: str


class InstructorCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    email: EmailStr
