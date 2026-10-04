"""Content-addressed feedback cache.

Resubmitting identical code for the same assignment costs zero LLM tokens:
the key hashes the provider, model, prompt version and the full deterministic
analysis result.
"""

import hashlib
import json
from dataclasses import asdict

from sqlalchemy.ext.asyncio import AsyncSession

from codeguide.feedback.base import FeedbackContext, FeedbackResult
from codeguide.feedback.prompts import PROMPT_VERSION
from codeguide.models import FeedbackCache


def cache_key(provider: str, model: str | None, ctx: FeedbackContext) -> str:
    # Hash the *content* of the analysis, not per-submission database ids: two
    # identical resubmissions must produce the same key. Finding ids are
    # autoincrement PKs that differ between submissions, so they are excluded.
    context = asdict(ctx)
    for finding in context["findings"]:
        finding.pop("id", None)
    payload = json.dumps(
        {
            "provider": provider,
            "model": model,
            "prompt_version": PROMPT_VERSION,
            "context": context,
        },
        sort_keys=True,
    )
    return hashlib.sha256(payload.encode()).hexdigest()


async def get_cached(db: AsyncSession, key: str) -> FeedbackResult | None:
    row = await db.get(FeedbackCache, key)
    if row is None:
        return None
    return FeedbackResult.model_validate(row.payload)


async def store_cached(db: AsyncSession, key: str, result: FeedbackResult) -> None:
    if await db.get(FeedbackCache, key) is None:
        db.add(FeedbackCache(cache_key=key, payload=result.model_dump()))
