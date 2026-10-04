"""Parser tests against captured real analyzer output (tests/fixtures/).

Fixtures were produced by running the deliberately vulnerable submissions in
``tests/fixtures/vulnerable_*.txt`` through the actual runner images.
"""

import json
from pathlib import Path

import pytest

from codeguide.analyzers.base import NormalizedFinding
from codeguide.analyzers.misconceptions import all_misconceptions, tag_for_rule
from codeguide.analyzers.registry import analyzers_for, supported_languages
from codeguide.execution.base import StepOutput
from codeguide.models import Category, Severity

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


def load_output(language: str, analyzer: str) -> StepOutput:
    doc = json.loads((FIXTURES / f"{language}_{analyzer}.json").read_text())
    return StepOutput(**doc)


def parse(language: str, analyzer_name: str) -> list[NormalizedFinding]:
    analyzer = next(a for a in analyzers_for(language) if a.name == analyzer_name)
    return analyzer.parse(load_output(language, analyzer_name))


def rules(findings: list[NormalizedFinding]) -> set[str]:
    return {f.rule_id for f in findings}


# --- python ------------------------------------------------------------------


def test_ruff_finds_style_bugrisk_and_complexity() -> None:
    findings = parse("python", "ruff")
    assert {"F401", "C901", "B006", "F821"} <= rules(findings)
    by_rule = {f.rule_id: f for f in findings}
    assert by_rule["F821"].severity is Severity.ERROR
    assert by_rule["F821"].category is Category.BUG_RISK
    assert by_rule["C901"].category is Category.COMPLEXITY
    assert by_rule["F401"].category is Category.STYLE
    assert all(f.file == "main.py" for f in findings)
    assert all(f.line_start > 0 for f in findings)


def test_bandit_finds_the_headline_vulnerabilities() -> None:
    findings = parse("python", "bandit")
    assert {"B105", "B301", "B608", "B602", "B307"} <= rules(findings)
    assert all(f.category is Category.SECURITY for f in findings)
    by_rule = {f.rule_id: f for f in findings}
    assert by_rule["B602"].severity is Severity.CRITICAL  # shell=True subprocess


def test_radon_flags_complex_function() -> None:
    findings = parse("python", "radon")
    assert findings, "expected at least one complexity finding"
    assert all(f.category is Category.COMPLEXITY for f in findings)
    assert findings[0].rule_id.startswith("radon-cc-")
    assert "cyclomatic complexity" in findings[0].message


def test_semgrep_python_rules_fire() -> None:
    findings = parse("python", "semgrep")
    assert {
        "py-hardcoded-password",
        "py-unsafe-pickle",
        "py-sqli-fstring",
        "py-subprocess-shell",
        "py-eval-input",
    } <= rules(findings)
    assert all(f.category is Category.SECURITY for f in findings)


# --- javascript --------------------------------------------------------------


def test_eslint_finds_security_complexity_and_bugs() -> None:
    findings = parse("javascript", "eslint")
    assert {"no-eval", "no-undef", "eqeqeq", "complexity"} <= rules(findings)
    by_rule = {f.rule_id: f for f in findings}
    assert by_rule["no-eval"].category is Category.SECURITY
    assert by_rule["no-undef"].category is Category.BUG_RISK
    assert by_rule["complexity"].category is Category.COMPLEXITY


def test_semgrep_javascript_rules_fire() -> None:
    findings = parse("javascript", "semgrep")
    assert {
        "js-hardcoded-secret",
        "js-sqli-template",
        "js-child-process-injection",
        "js-eval",
    } <= rules(findings)


# --- robustness ---------------------------------------------------------------


@pytest.mark.parametrize("language", supported_languages())
def test_parsers_tolerate_garbage_output(language: str) -> None:
    garbage = StepOutput(
        exit_code=2, stdout="not json {", stderr="boom", duration_ms=1, timed_out=False
    )
    empty = StepOutput(exit_code=0, stdout="", stderr="", duration_ms=1, timed_out=False)
    timeout = StepOutput(exit_code=-1, stdout="", stderr="", duration_ms=1, timed_out=True)
    for analyzer in analyzers_for(language):
        for output in (garbage, empty, timeout):
            assert analyzer.parse(output) == []


# --- taxonomy -----------------------------------------------------------------


def test_headline_misconception_tags() -> None:
    assert tag_for_rule("B608") == "sql-injection"
    assert tag_for_rule("py-sqli-fstring") == "sql-injection"
    assert tag_for_rule("B105") == "hardcoded-secret"
    assert tag_for_rule("B301") == "unsafe-deserialization"
    assert tag_for_rule("js-eval") == "eval-injection"
    assert tag_for_rule("radon-cc-D") == "excessive-complexity"
    assert tag_for_rule("B006") == "mutable-default-argument"
    assert tag_for_rule("E999-nonexistent") is None


def test_taxonomy_is_well_formed() -> None:
    misconceptions = all_misconceptions()
    tags = [m.tag for m in misconceptions]
    assert len(tags) == len(set(tags)), "duplicate tags"
    for m in misconceptions:
        assert m.title and m.summary
