import httpx

from tests.conftest import bearer


async def test_join_unknown_code_404(client: httpx.AsyncClient) -> None:
    resp = await client.post(
        "/api/v1/auth/join", json={"join_code": "NOPE1234", "display_name": "Sam"}
    )
    assert resp.status_code == 404


async def test_join_and_use_student_token(
    client: httpx.AsyncClient, instructor_token: str
) -> None:
    course = (
        await client.post(
            "/api/v1/courses", json={"title": "Intro"}, headers=bearer(instructor_token)
        )
    ).json()

    resp = await client.post(
        "/api/v1/auth/join",
        json={"join_code": course["join_code"], "display_name": "Sam"},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["student_token"].startswith("cgs_")
    assert body["course"]["id"] == course["id"]

    listing = await client.get(
        f"/api/v1/courses/{course['id']}/assignments",
        headers=bearer(body["student_token"]),
    )
    assert listing.status_code == 200
    assert listing.json() == []


async def test_join_code_is_case_insensitive(
    client: httpx.AsyncClient, instructor_token: str
) -> None:
    course = (
        await client.post(
            "/api/v1/courses", json={"title": "Intro"}, headers=bearer(instructor_token)
        )
    ).json()
    resp = await client.post(
        "/api/v1/auth/join",
        json={"join_code": course["join_code"].lower(), "display_name": "Sam"},
    )
    assert resp.status_code == 201


async def test_missing_token_401(client: httpx.AsyncClient) -> None:
    assert (await client.get("/api/v1/courses")).status_code == 401


async def test_garbage_token_401(client: httpx.AsyncClient) -> None:
    resp = await client.get("/api/v1/courses", headers=bearer("cgi_not-a-real-token"))
    assert resp.status_code == 401


async def test_meta_is_public(client: httpx.AsyncClient) -> None:
    resp = await client.get("/api/v1/meta")
    assert resp.status_code == 200
    body = resp.json()
    assert body["feedback_provider"] in {"anthropic", "openai", "ollama", "template"}
    assert body["execution_backend"] in {"docker", "kubernetes", "local"}
