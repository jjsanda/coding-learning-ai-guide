"""Administrative CLI.

Usage::

    python -m codeguide.cli create-instructor --name "Ada Lovelace" --email ada@example.edu
    python -m codeguide.cli seed
"""

import argparse
import asyncio
import sys

from sqlalchemy import select

from codeguide.auth import hash_token, new_instructor_token
from codeguide.db import dispose_engine, get_session_factory, run_migrations
from codeguide.models import Instructor


async def create_instructor(name: str, email: str) -> int:
    await run_migrations()
    async with get_session_factory()() as db:
        existing = await db.scalar(select(Instructor).where(Instructor.email == email))
        if existing is not None:
            print(f"error: an instructor with email {email!r} already exists", file=sys.stderr)
            return 1
        token = new_instructor_token()
        db.add(Instructor(name=name, email=email, token_hash=hash_token(token)))
        await db.commit()
    print("Instructor created. The API token below is shown ONCE — store it now:")
    print()
    print(f"  {token}")
    print()
    print('Use it as:  curl -H "Authorization: Bearer <token>" ...')
    return 0


async def seed() -> int:
    from codeguide.seed import run_seed  # imported lazily; pulls in demo assignments

    await run_migrations()
    return await run_seed()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="codeguide", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    p_create = sub.add_parser("create-instructor", help="Create an instructor and print a token")
    p_create.add_argument("--name", required=True)
    p_create.add_argument("--email", required=True)

    sub.add_parser("seed", help="Load demo courses, assignments and submissions")

    args = parser.parse_args(argv)

    async def dispatch() -> int:
        try:
            if args.command == "create-instructor":
                return await create_instructor(args.name, args.email)
            return await seed()
        finally:
            await dispose_engine()

    return asyncio.run(dispatch())


if __name__ == "__main__":
    raise SystemExit(main())
