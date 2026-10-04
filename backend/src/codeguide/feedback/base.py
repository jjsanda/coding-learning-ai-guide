"""Feedback provider contract.

Providers turn deterministic analysis results into pedagogical feedback.
The LLM never grades: analyzers and test cases decide *what* is wrong,
the provider only explains *why it matters* and nudges the student
toward a fix. Every provider produces the same schema, and the
deterministic template provider guarantees a working fallback when no
LLM is configured or reachable.
"""

from dataclasses import dataclass
from typing import Any, Protocol

from pydantic import BaseModel, Field


@dataclass(frozen=True)
class ContextFinding:
    id: int
    analyzer: str
    rule_id: str
    severity: str
    category: str
    file: str
    line_start: int
    message: str
    snippet: str | None
    misconception_tag: str | None


@dataclass(frozen=True)
class ContextTest:
    name: str
    passed: bool
    expected: str | None
    actual: str | None
    timed_out: bool


@dataclass(frozen=True)
class FeedbackContext:
    assignment_title: str
    assignment_description: str
    language: str
    findings: list[ContextFinding]
    failing_tests: list[ContextTest]
    passed_tests: int
    total_tests: int


class FeedbackItemModel(BaseModel):
    finding_ref: int | None = Field(
        default=None, description="ID of the finding this item explains"
    )
    explanation_md: str = Field(description="Why this issue matters, addressed to the student")
    hint_md: str = Field(default="", description="One guiding question or nudge, not a solution")
    misconception_tag: str | None = None


class FeedbackModel(BaseModel):
    summary_md: str = Field(description="Short encouraging overview of the submission")
    items: list[FeedbackItemModel]
    next_steps: list[str] = Field(description="Up to three concrete next actions")


class FeedbackResult(BaseModel):
    provider: str
    model: str | None = None
    feedback: FeedbackModel


class FeedbackProvider(Protocol):
    name: str

    def available(self) -> bool:
        """Cheap static check: is this provider configured?"""
        ...

    async def generate(self, ctx: FeedbackContext) -> FeedbackResult: ...


def context_from_rows(
    assignment: Any,
    findings: list[Any],
    test_results: list[Any],
    *,
    max_findings: int = 20,
) -> FeedbackContext:
    """Build a provider context from ORM rows, capped for prompt size."""
    severity_rank = {"critical": 0, "error": 1, "warning": 2, "info": 3}
    ordered = sorted(findings, key=lambda f: (severity_rank.get(f.severity, 9), f.line_start))
    return FeedbackContext(
        assignment_title=assignment.title,
        assignment_description=assignment.description_md[:2000],
        language=assignment.language,
        findings=[
            ContextFinding(
                id=f.id,
                analyzer=f.analyzer,
                rule_id=f.rule_id,
                severity=f.severity,
                category=f.category,
                file=f.file,
                line_start=f.line_start,
                message=f.message,
                snippet=f.snippet,
                misconception_tag=f.misconception_tag,
            )
            for f in ordered[:max_findings]
        ],
        failing_tests=[
            ContextTest(
                name=t.name,
                passed=t.passed,
                expected=(t.expected or "")[:500],
                actual=(t.actual or "")[:500],
                timed_out=t.timed_out,
            )
            for t in test_results
            if not t.passed
        ][:10],
        passed_tests=sum(1 for t in test_results if t.passed),
        total_tests=len(test_results),
    )
