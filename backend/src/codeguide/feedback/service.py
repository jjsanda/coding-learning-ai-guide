"""Feedback orchestration: provider selection, caching, graceful fallback."""

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from codeguide.config import get_settings
from codeguide.feedback.base import FeedbackResult, context_from_rows
from codeguide.feedback.cache import cache_key, get_cached, store_cached
from codeguide.feedback.registry import provider_chain
from codeguide.models import Assignment, Feedback, Finding, Submission, TestResult

log = structlog.get_logger()


async def generate_and_store_feedback(
    db: AsyncSession, submission: Submission, assignment: Assignment
) -> None:
    findings = list(
        await db.scalars(select(Finding).where(Finding.submission_id == submission.id))
    )
    test_results = list(
        await db.scalars(select(TestResult).where(TestResult.submission_id == submission.id))
    )
    ctx = context_from_rows(assignment, findings, test_results)

    settings = get_settings()
    result: FeedbackResult | None = None
    cached = False
    degraded = False

    for provider in provider_chain(settings):
        key = cache_key(provider.name, getattr(provider, "_model", None), ctx)
        hit = await get_cached(db, key)
        if hit is not None:
            result, cached = hit, True
            log.info("feedback_cache_hit", provider=provider.name)
            break
        try:
            result = await provider.generate(ctx)
        except Exception:
            log.exception("feedback_provider_failed", provider=provider.name)
            degraded = True
            continue
        await store_cached(db, key, result)
        break

    if result is None:  # pragma: no cover - template provider cannot fail
        raise RuntimeError("no feedback provider produced a result")

    # Honest attribution: the UI shows when an LLM provider failed and the
    # deterministic templates stepped in.
    provider_label = result.provider
    if degraded and result.provider == "template":
        provider_label = "template(fallback)"

    db.add(
        Feedback(
            submission_id=submission.id,
            provider=provider_label,
            model=result.model,
            summary_md=result.feedback.summary_md,
            items=[item.model_dump() for item in result.feedback.items],
            next_steps=result.feedback.next_steps,
            cached=cached,
        )
    )
    await db.commit()
    log.info("feedback_stored", provider=provider_label, cached=cached)
