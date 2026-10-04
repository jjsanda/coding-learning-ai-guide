"""FastAPI application factory."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from codeguide import __version__
from codeguide.api.router import api_v1
from codeguide.config import get_settings
from codeguide.db import dispose_engine, get_session_factory, run_migrations
from codeguide.logging import RequestIDMiddleware, configure_logging

log = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    log.info("startup", version=__version__, execution_backend=settings.execution_backend)
    await run_migrations()

    from codeguide.execution.factory import create_backend
    from codeguide.queue import SubmissionQueue

    queue = SubmissionQueue(create_backend(settings), get_session_factory(), settings)
    await queue.start()
    app.state.submission_queue = queue

    yield

    await queue.stop()
    await dispose_engine()
    log.info("shutdown")


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(debug=settings.debug)

    app = FastAPI(
        title="coding-learning-ai-guide",
        version=__version__,
        lifespan=lifespan,
        docs_url="/api/docs",
        openapi_url="/api/openapi.json",
    )
    app.add_middleware(RequestIDMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(api_v1)

    @app.get("/healthz", include_in_schema=False)
    async def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/readyz", include_in_schema=False)
    async def readyz(response: Response) -> dict[str, str]:
        try:
            async with get_session_factory()() as session:
                await session.execute(text("SELECT 1"))
        except Exception:
            log.exception("readyz_db_check_failed")
            response.status_code = 503
            return {"status": "unavailable"}
        return {"status": "ready"}

    return app


app = create_app()
