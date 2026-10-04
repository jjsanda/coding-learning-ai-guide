from types import SimpleNamespace

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from codeguide.config import Settings
from codeguide.feedback.base import (
    ContextFinding,
    FeedbackContext,
    FeedbackItemModel,
    FeedbackModel,
    FeedbackResult,
    context_from_rows,
)
from codeguide.feedback.cache import cache_key, get_cached, store_cached
from codeguide.feedback.llm_providers import drop_ungrounded_items
from codeguide.feedback.registry import provider_chain, resolve_provider_name
from codeguide.feedback.template_provider import TemplateProvider


def make_context(**overrides) -> FeedbackContext:
    defaults = dict(
        assignment_title="User lookup",
        assignment_description="Query users from a database.",
        language="python",
        findings=[
            ContextFinding(
                id=1,
                analyzer="bandit",
                rule_id="B608",
                severity="error",
                category="security",
                file="main.py",
                line_start=12,
                message="Possible SQL injection",
                snippet="cur.execute(f\"SELECT ... '{name}'\")",
                misconception_tag="sql-injection",
            ),
            ContextFinding(
                id=2,
                analyzer="ruff",
                rule_id="F401",
                severity="info",
                category="style",
                file="main.py",
                line_start=2,
                message="`os` imported but unused",
                snippet=None,
                misconception_tag=None,
            ),
        ],
        failing_tests=[],
        passed_tests=2,
        total_tests=3,
    )
    defaults.update(overrides)
    return FeedbackContext(**defaults)


# --- template provider -------------------------------------------------------


async def test_template_provider_produces_complete_feedback() -> None:
    result = await TemplateProvider().generate(make_context())
    fb = result.feedback
    assert result.provider == "template"
    assert "2 of 3" in fb.summary_md
    assert len(fb.items) == 2
    sql_item = next(i for i in fb.items if i.misconception_tag == "sql-injection")
    assert "SQL" in sql_item.explanation_md or "sql" in sql_item.explanation_md
    assert sql_item.hint_md.endswith("?")  # guiding question, not a solution
    assert fb.next_steps


async def test_template_provider_deduplicates_misconceptions() -> None:
    finding = make_context().findings[0]
    dup = ContextFinding(**{**finding.__dict__, "id": 99, "analyzer": "semgrep"})
    ctx = make_context(findings=[finding, dup])
    result = await TemplateProvider().generate(ctx)
    assert len(result.feedback.items) == 1


async def test_template_provider_handles_clean_submission() -> None:
    ctx = make_context(findings=[], passed_tests=3, total_tests=3)
    result = await TemplateProvider().generate(ctx)
    assert result.feedback.items == []
    assert "nothing to flag" in result.feedback.summary_md


# --- provider selection -------------------------------------------------------


def test_auto_resolves_to_template_without_keys(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    settings = Settings(feedback_provider="auto", ollama_base_url=None)
    assert resolve_provider_name(settings) == "template"
    assert [p.name for p in provider_chain(settings)] == ["template"]


def test_auto_prefers_anthropic_when_key_present(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    settings = Settings(feedback_provider="auto", ollama_base_url=None)
    chain = [p.name for p in provider_chain(settings)]
    assert chain == ["anthropic", "template"]


def test_pinned_provider_still_falls_back_to_template() -> None:
    settings = Settings(feedback_provider="openai")
    assert [p.name for p in provider_chain(settings)] == ["openai", "template"]


# --- grounding ----------------------------------------------------------------


def test_ungrounded_items_are_dropped() -> None:
    ctx = make_context()
    feedback = FeedbackModel(
        summary_md="s",
        items=[
            FeedbackItemModel(finding_ref=1, explanation_md="grounded"),
            FeedbackItemModel(finding_ref=424242, explanation_md="hallucinated"),
            FeedbackItemModel(finding_ref=None, explanation_md="unreferenced"),
        ],
        next_steps=[],
    )
    cleaned = drop_ungrounded_items(feedback, ctx)
    assert [i.explanation_md for i in cleaned.items] == ["grounded"]


# --- cache ---------------------------------------------------------------------


def test_cache_key_is_stable_and_sensitive() -> None:
    ctx = make_context()
    key1 = cache_key("template", None, ctx)
    key2 = cache_key("template", None, make_context())
    assert key1 == key2
    assert cache_key("anthropic", "claude-opus-4-8", ctx) != key1
    changed = make_context(passed_tests=0)
    assert cache_key("template", None, changed) != key1


def test_cache_key_ignores_per_submission_finding_ids() -> None:
    # Identical code resubmitted gets fresh finding ids; the key must not change,
    # or the cache never hits (see the feedback cache regression).
    base = make_context().findings
    ctx_a = make_context(findings=[ContextFinding(**{**f.__dict__, "id": f.id}) for f in base])
    ctx_b = make_context(
        findings=[ContextFinding(**{**f.__dict__, "id": f.id + 1000}) for f in base]
    )
    assert cache_key("anthropic", "m", ctx_a) == cache_key("anthropic", "m", ctx_b)
    # but a change in finding *content* still busts the cache
    changed = make_context(
        findings=[ContextFinding(**{**base[0].__dict__, "message": "different"})]
    )
    assert cache_key("anthropic", "m", changed) != cache_key("anthropic", "m", ctx_a)


async def test_cache_roundtrip(db_session: AsyncSession) -> None:
    ctx = make_context()
    key = cache_key("template", None, ctx)
    assert await get_cached(db_session, key) is None

    result = await TemplateProvider().generate(ctx)
    await store_cached(db_session, key, result)
    await db_session.commit()

    hit = await get_cached(db_session, key)
    assert isinstance(hit, FeedbackResult)
    assert hit.feedback.summary_md == result.feedback.summary_md


# --- context building -----------------------------------------------------------


def test_context_orders_by_severity_and_caps() -> None:
    assignment = SimpleNamespace(
        title="T", description_md="d", language="python", entrypoint="main.py"
    )
    findings = [
        SimpleNamespace(
            id=i,
            analyzer="ruff",
            rule_id="E1",
            severity="info" if i % 2 else "critical",
            category="style",
            file="main.py",
            line_start=i,
            message="m",
            snippet=None,
            misconception_tag=None,
        )
        for i in range(30)
    ]
    ctx = context_from_rows(assignment, findings, [])
    assert len(ctx.findings) == 20
    assert ctx.findings[0].severity == "critical"
