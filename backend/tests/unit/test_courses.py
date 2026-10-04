import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from codeguide.auth import hash_token, new_instructor_token
from codeguide.models import Instructor
from tests.conftest import bearer


async def test_create_and_get_course(client: httpx.AsyncClient, instructor_token: str) -> None:
    created = await client.post(
        "/api/v1/courses", json={"title": "Programming 101"}, headers=bearer(instructor_token)
    )
    assert created.status_code == 201
    body = created.json()
    assert len(body["join_code"]) == 8

    fetched = await client.get(f"/api/v1/courses/{body['id']}", headers=bearer(instructor_token))
    assert fetched.status_code == 200
    assert fetched.json()["title"] == "Programming 101"

    listing = await client.get("/api/v1/courses", headers=bearer(instructor_token))
    assert [c["id"] for c in listing.json()] == [body["id"]]


async def test_course_hidden_from_other_instructor(
    client: httpx.AsyncClient, instructor_token: str, db_session: AsyncSession
) -> None:
    other_token = new_instructor_token()
    db_session.add(
        Instructor(name="Other", email="other@example.edu", token_hash=hash_token(other_token))
    )
    await db_session.commit()

    course = (
        await client.post(
            "/api/v1/courses", json={"title": "Hidden"}, headers=bearer(instructor_token)
        )
    ).json()

    resp = await client.get(f"/api/v1/courses/{course['id']}", headers=bearer(other_token))
    assert resp.status_code == 404
    assert (await client.get("/api/v1/courses", headers=bearer(other_token))).json() == []
