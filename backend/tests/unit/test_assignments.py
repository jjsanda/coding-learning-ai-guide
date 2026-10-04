import httpx

from tests.conftest import bearer

ASSIGNMENT = {
    "title": "FizzBuzz",
    "description_md": "Classic FizzBuzz.",
    "language": "python",
    "entrypoint": "main.py",
    "test_cases": [
        {"name": "one", "stdin": "1\n", "expected_stdout": "1\n", "visible": True},
        {"name": "secret", "stdin": "15\n", "expected_stdout": "FizzBuzz\n", "visible": False},
    ],
}


async def _setup(client: httpx.AsyncClient, instructor_token: str) -> tuple[dict, dict, str]:
    course = (
        await client.post(
            "/api/v1/courses", json={"title": "Intro"}, headers=bearer(instructor_token)
        )
    ).json()
    assignment = (
        await client.post(
            f"/api/v1/courses/{course['id']}/assignments",
            json=ASSIGNMENT,
            headers=bearer(instructor_token),
        )
    ).json()
    student_token = (
        await client.post(
            "/api/v1/auth/join",
            json={"join_code": course["join_code"], "display_name": "Sam"},
        )
    ).json()["student_token"]
    return course, assignment, student_token


async def test_instructor_sees_hidden_expected_output(
    client: httpx.AsyncClient, instructor_token: str
) -> None:
    _, assignment, _ = await _setup(client, instructor_token)
    resp = await client.get(
        f"/api/v1/assignments/{assignment['id']}", headers=bearer(instructor_token)
    )
    cases = {c["name"]: c for c in resp.json()["test_cases"]}
    assert cases["secret"]["expected_stdout"] == "FizzBuzz\n"


async def test_student_cannot_see_hidden_expected_output(
    client: httpx.AsyncClient, instructor_token: str
) -> None:
    _, assignment, student_token = await _setup(client, instructor_token)
    resp = await client.get(
        f"/api/v1/assignments/{assignment['id']}", headers=bearer(student_token)
    )
    assert resp.status_code == 200
    cases = {c["name"]: c for c in resp.json()["test_cases"]}
    assert cases["one"]["expected_stdout"] == "1\n"
    assert cases["secret"]["expected_stdout"] is None
    assert cases["secret"]["stdin"] is None


async def test_student_of_other_course_gets_404(
    client: httpx.AsyncClient, instructor_token: str
) -> None:
    _, assignment, _ = await _setup(client, instructor_token)
    other_course = (
        await client.post(
            "/api/v1/courses", json={"title": "Other"}, headers=bearer(instructor_token)
        )
    ).json()
    outsider_token = (
        await client.post(
            "/api/v1/auth/join",
            json={"join_code": other_course["join_code"], "display_name": "Eve"},
        )
    ).json()["student_token"]

    resp = await client.get(
        f"/api/v1/assignments/{assignment['id']}", headers=bearer(outsider_token)
    )
    assert resp.status_code == 404


async def test_invalid_language_rejected(
    client: httpx.AsyncClient, instructor_token: str
) -> None:
    course = (
        await client.post(
            "/api/v1/courses", json={"title": "Intro"}, headers=bearer(instructor_token)
        )
    ).json()
    bad = dict(ASSIGNMENT, language="cobol")
    resp = await client.post(
        f"/api/v1/courses/{course['id']}/assignments",
        json=bad,
        headers=bearer(instructor_token),
    )
    assert resp.status_code == 422
