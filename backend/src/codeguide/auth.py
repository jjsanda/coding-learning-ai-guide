"""Bearer-token authentication.

Two principals, both identified by a random secret shown exactly once:

* **Instructors** get a token from the ``create-instructor`` CLI command.
* **Students** get a token when they join a course with its join code.

Only SHA-256 hashes are stored. Tokens are prefixed (``cgi_`` / ``cgs_``)
so which kind of credential leaked is obvious in logs and reports.
"""

import hashlib
import secrets
import string
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from codeguide.db import get_db
from codeguide.models import Instructor, Student

# Prefixes make leaked-credential reports unambiguous; they are not secrets.
INSTRUCTOR_TOKEN_PREFIX = "cgi_"  # noqa: S105
STUDENT_TOKEN_PREFIX = "cgs_"  # noqa: S105

_bearer = HTTPBearer(auto_error=False)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def new_instructor_token() -> str:
    return INSTRUCTOR_TOKEN_PREFIX + secrets.token_urlsafe(32)


def new_student_token() -> str:
    return STUDENT_TOKEN_PREFIX + secrets.token_urlsafe(32)


def new_join_code() -> str:
    """Human-friendly 8-char course join code (no ambiguous characters)."""
    alphabet = "".join(c for c in string.ascii_uppercase + string.digits if c not in "O0I1L")
    return "".join(secrets.choice(alphabet) for _ in range(8))


def _credentials(creds: HTTPAuthorizationCredentials | None) -> str:
    if creds is None or not creds.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing bearer token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return creds.credentials


async def get_current_instructor(
    creds: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Instructor:
    token = _credentials(creds)
    instructor = await db.scalar(
        select(Instructor).where(Instructor.token_hash == hash_token(token))
    )
    if instructor is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid instructor token")
    return instructor


async def get_current_student(
    creds: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Student:
    token = _credentials(creds)
    student = await db.scalar(select(Student).where(Student.token_hash == hash_token(token)))
    if student is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid student token")
    return student


async def get_student_or_instructor(
    creds: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Student | Instructor:
    token = _credentials(creds)
    digest = hash_token(token)
    if token.startswith(INSTRUCTOR_TOKEN_PREFIX):
        instructor = await db.scalar(select(Instructor).where(Instructor.token_hash == digest))
        if instructor is not None:
            return instructor
    else:
        student = await db.scalar(select(Student).where(Student.token_hash == digest))
        if student is not None:
            return student
    raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid token")
