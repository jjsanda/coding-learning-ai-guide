"""Deployment metadata for the UI (which providers/backends are active)."""

from fastapi import APIRouter

from codeguide import __version__
from codeguide.config import get_settings
from codeguide.feedback.registry import resolve_provider_name
from codeguide.schemas import Meta

router = APIRouter(tags=["meta"])


@router.get("/meta", response_model=Meta)
async def meta() -> Meta:
    settings = get_settings()
    return Meta(
        version=__version__,
        execution_backend=settings.execution_backend,
        feedback_provider=resolve_provider_name(settings),
    )
