import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from codeguide.models import (
    Category,
    Finding,
    Severity,
    Student,
    Submission,
    SubmissionStatus,
    TestResult,
)
from tests.conftest import bearer


async def _seed_course(
    client: httpx.AsyncClient, instructor_token: str, db_session: AsyncSession
) -> str:
    course = (
        await client.post(
            "/api/v1/courses", json={"title": "Intro"}, headers=bearer(instructor_token)
        )
    ).json()
    assignment = (
        await client.post(
            f"/api/v1/courses/{course['id']}/assignments",
            json={
                "title": "FizzBuzz",
                "description_md": "d",
                "language": "python",
                "entrypoint": "main.py",
            },
            headers=bearer(instructor_token),
        )
    ).json()

    students = [
        Student(course_id=course["id"], display_name=f"S{i}", token_hash=f"h{i}")
        for i in range(2)
    ]
    db_session.add_all(students)
    await db_session.flush()

    for i, student in enumerate(students):
        submission = Submission(
            assignment_id=assignment["id"],
            student_id=student.id,
            status=SubmissionStatus.COMPLETED,
            files=[{"path": "main.py", "content": "print(1)"}],
        )
        db_session.add(submission)
        await db_session.flush()
        db_session.add(
            Finding(
                submission_id=submission.id,
                analyzer="bandit",
                rule_id="B608",
                severity=Severity.ERROR,
                category=Category.SECURITY,
                file="main.py",
                line_start=1,
                line_end=1,
                message="sql injection",
                misconception_tag="sql-injection",
            )
        )
        db_session.add(
            TestResult(
                submission_id=submission.id,
                name="t1",
                passed=(i == 0),  # first student passes, second fails
                expected="1",
                actual="1" if i == 0 else "2",
            )
        )
    await db_session.commit()
    return course["id"]


async def test_course_insights_aggregation(
    client: httpx.AsyncClient, instructor_token: str, db_session: AsyncSession
) -> None:
    course_id = await _seed_course(client, instructor_token, db_session)

    resp = await client.get(
        f"/api/v1/courses/{course_id}/insights", headers=bearer(instructor_token)
    )
    assert resp.status_code == 200
    body = resp.json()

    assert body["total_submissions"] == 2
    assert body["total_students"] == 2

    assert body["misconceptions"] == [
        {"misconception_tag": "sql-injection", "count": 2, "affected_students": 2}
    ]

    (pass_rate,) = body["pass_rates"]
    assert pass_rate["submissions"] == 2
    assert pass_rate["pass_rate"] == 0.5

    assert {c["category"]: c["count"] for c in body["findings_by_category"]} == {"security": 2}
    assert sum(d["count"] for d in body["submissions_per_day"]) == 2


async def test_insights_requires_course_ownership(
    client: httpx.AsyncClient, instructor_token: str, db_session: AsyncSession
) -> None:
    course_id = await _seed_course(client, instructor_token, db_session)
    resp = await client.get(f"/api/v1/courses/{course_id}/insights")
    assert resp.status_code == 401
