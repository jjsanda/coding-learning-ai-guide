"""Prompt construction for LLM feedback providers.

PROMPT_VERSION participates in the feedback cache key: bump it whenever the
prompts change so stale cached feedback is not served for new prompt logic.
"""

from codeguide.analyzers.misconceptions import misconception
from codeguide.feedback.base import FeedbackContext

PROMPT_VERSION = 1

SYSTEM_PROMPT = """\
You are an experienced, kind programming teaching assistant giving formative
feedback on a student's submission in an introductory course.

Ground rules:
- Formative, not summative: no grades, no scores, no pass/fail verdicts.
- NEVER provide a corrected or complete solution. Not even a fixed line.
- Every feedback item must reference one of the provided findings by its id.
  Do not invent problems that are not in the findings list.
- For each item explain WHY the issue matters in plain language a beginner
  understands, then ask ONE guiding question that leads them toward the fix.
- Where a misconception tag is provided, address the underlying concept, not
  just the symptom.
- Be encouraging and specific. Mention what the student did well in the
  summary when the findings allow it.
- Write in Markdown. Keep each item under 120 words.
"""


def build_user_prompt(ctx: FeedbackContext) -> str:
    parts = [
        "<assignment>",
        f"Title: {ctx.assignment_title}",
        f"Language: {ctx.language}",
        ctx.assignment_description,
        "</assignment>",
        "",
        f"<tests passed=\"{ctx.passed_tests}\" total=\"{ctx.total_tests}\">",
    ]
    for test in ctx.failing_tests:
        parts.append(f"  <failing_test name={test.name!r} timed_out={test.timed_out}>")
        if test.expected:
            parts.append(f"    expected: {test.expected!r}")
        if test.actual:
            parts.append(f"    actual:   {test.actual!r}")
        parts.append("  </failing_test>")
    parts.append("</tests>")
    parts.append("")
    parts.append("<findings>")
    for f in ctx.findings:
        tag_info = ""
        if f.misconception_tag:
            m = misconception(f.misconception_tag)
            title = m.title if m else f.misconception_tag
            tag_info = f' misconception="{f.misconception_tag}" concept="{title}"'
        parts.append(
            f'  <finding id="{f.id}" severity="{f.severity}" category="{f.category}"'
            f' rule="{f.rule_id}" file="{f.file}" line="{f.line_start}"{tag_info}>'
        )
        parts.append(f"    {f.message}")
        if f.snippet:
            parts.append("    <code>")
            parts.append(f.snippet)
            parts.append("    </code>")
        parts.append("  </finding>")
    parts.append("</findings>")
    parts.append("")
    parts.append(
        "Write the feedback now. Reference findings by id via finding_ref. "
        "Group duplicate findings about the same underlying issue into one item "
        "(use the most severe finding's id)."
    )
    return "\n".join(parts)
