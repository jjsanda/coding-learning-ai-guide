"""Deterministic template-based feedback.

Always available, needs no API key and no network: builds pedagogical
feedback directly from the misconception taxonomy and finding categories.
This keeps every deployment fully functional and doubles as the graceful
degradation path when an LLM provider fails mid-request.
"""

from codeguide.analyzers.misconceptions import misconception
from codeguide.feedback.base import (
    ContextFinding,
    FeedbackContext,
    FeedbackItemModel,
    FeedbackModel,
    FeedbackResult,
)
from codeguide.models import Category

_CATEGORY_EXPLANATIONS = {
    Category.STYLE: (
        "This is a style issue. Style problems don't break your program today, "
        "but they make it harder to read — and code is read far more often than "
        "it is written."
    ),
    Category.COMPLEXITY: (
        "This code is doing a lot at once. The more branches a piece of code "
        "has, the harder it is to test and to reason about, and the easier it "
        "is for a bug to hide in it."
    ),
    Category.SECURITY: (
        "This is a security issue. Code like this can be abused by someone "
        "feeding your program unexpected input — which is exactly what "
        "attackers do."
    ),
    Category.BUG_RISK: (
        "This pattern is a common source of bugs. It may work in the happy "
        "case, but it tends to fail in surprising ways."
    ),
    Category.CORRECTNESS: (
        "The program's output doesn't match what the assignment expects, so "
        "there is a logic problem to track down."
    ),
}

_MISCONCEPTION_HINTS = {
    "sql-injection": (
        "How could you pass the user's value to the database as data rather than as "
        "part of the query text?"
    ),
    "hardcoded-secret": (
        "If this secret leaked, how would you change it everywhere without editing the "
        "source code?"
    ),
    "unsafe-deserialization": "Where did this data come from, and can you fully trust it?",
    "eval-injection": "Could you parse this value explicitly instead of running it as code?",
    "command-injection": "How could you run this program without handing the input to a shell?",
    "xss": "What happens if the user's text contains HTML tags?",
    "excessive-complexity": (
        "Could you name each separate job this function does, and give each one its own "
        "small function?"
    ),
    "mutable-default-argument": (
        "What happens to this default value the second time the function is called?"
    ),
    "infinite-loop": "What has to change inside the loop for it to eventually stop?",
}

_CATEGORY_HINTS = {
    Category.STYLE: "How would this read to a classmate seeing it for the first time?",
    Category.COMPLEXITY: (
        "Could you name each separate job this function does, and give each one "
        "its own small function?"
    ),
    Category.SECURITY: (
        "What could a user type here to make the program do something you did not intend?"
    ),
    Category.BUG_RISK: (
        "Can you construct an input where this line behaves differently than you expect?"
    ),
    Category.CORRECTNESS: (
        "Try running your program by hand on the failing test's input — where does your "
        "result first differ from the expected output?"
    ),
}


def _item_for(finding: ContextFinding) -> FeedbackItemModel:
    m = misconception(finding.misconception_tag) if finding.misconception_tag else None
    location = f"`{finding.file}`"
    if finding.line_start:
        location += f" (line {finding.line_start})"

    category = Category(finding.category)
    if m is not None:
        explanation = f"**{m.title}** — in {location}: {m.summary}"
        hint = _MISCONCEPTION_HINTS.get(finding.misconception_tag or "") or _CATEGORY_HINTS.get(
            category, ""
        )
    else:
        explanation = (
            f"In {location}: {finding.message} "
            f"{_CATEGORY_EXPLANATIONS.get(category, '')}"
        )
        hint = _CATEGORY_HINTS.get(category, "")

    return FeedbackItemModel(
        finding_ref=finding.id,
        explanation_md=explanation.strip(),
        hint_md=hint,
        misconception_tag=finding.misconception_tag,
    )


def _summary(ctx: FeedbackContext) -> str:
    parts = []
    if ctx.total_tests:
        parts.append(f"Your submission passed **{ctx.passed_tests} of {ctx.total_tests}** tests.")
    if not ctx.findings:
        parts.append("The analyzers found nothing to flag — nicely done. ")
    else:
        categories = sorted({f.category for f in ctx.findings})
        parts.append(
            f"The analysis flagged **{len(ctx.findings)}** thing(s) worth a look "
            f"({', '.join(categories)}). Each item below explains why it matters "
            "and gives you a question to guide the fix — the fixing itself is "
            "yours to do."
        )
    return " ".join(parts)


def _next_steps(ctx: FeedbackContext) -> list[str]:
    steps = []
    if ctx.failing_tests:
        first = ctx.failing_tests[0]
        steps.append(
            f"Reproduce the failing test '{first.name}' by hand: feed your program the same "
            "input and follow the code line by line."
        )
    security = [f for f in ctx.findings if f.category == Category.SECURITY]
    if security:
        steps.append(
            "Start with the security findings — they are the most important habit to build early."
        )
    if ctx.findings and not steps:
        steps.append("Work through the findings top to bottom; they are ordered by severity.")
    steps.append("Resubmit when you're ready — you can submit as often as you like.")
    return steps[:3]


class TemplateProvider:
    name = "template"

    def available(self) -> bool:
        return True

    async def generate(self, ctx: FeedbackContext) -> FeedbackResult:
        seen_tags: set[str] = set()
        items: list[FeedbackItemModel] = []
        for finding in ctx.findings:
            # one item per misconception: repeating the same lesson dilutes it
            if finding.misconception_tag:
                if finding.misconception_tag in seen_tags:
                    continue
                seen_tags.add(finding.misconception_tag)
            items.append(_item_for(finding))

        return FeedbackResult(
            provider=self.name,
            model=None,
            feedback=FeedbackModel(
                summary_md=_summary(ctx),
                items=items,
                next_steps=_next_steps(ctx),
            ),
        )
