"""Python analyzers: ruff (style/bug risk), bandit (security), radon (complexity),
semgrep (security, curated offline rules)."""

import typing

from codeguide.analyzers.base import NormalizedFinding, load_json_output, normalize_path
from codeguide.execution.base import Step, StepOutput
from codeguide.models import Category, Severity


class RuffAnalyzer:
    name = "ruff"
    languages = frozenset({"python"})

    def sandbox_step(self) -> Step:
        return Step(
            id=self.name,
            # E501 (line length) is noise for beginners; security is bandit's job.
            cmd=[
                "ruff",
                "check",
                "--output-format=json",
                "--select=E,W,F,B,C90",
                "--ignore=E501",
                "--no-cache",
                ".",
            ],
            timeout_s=60,
        )

    def parse(self, out: StepOutput) -> list[NormalizedFinding]:
        doc = load_json_output(self.name, out)
        if not isinstance(doc, list):
            return []
        findings = []
        for item in doc:
            code = item.get("code") or "ruff"
            findings.append(
                NormalizedFinding(
                    analyzer=self.name,
                    rule_id=code,
                    severity=self._severity(code),
                    category=self._category(code),
                    file=normalize_path(item.get("filename", "")),
                    line_start=item.get("location", {}).get("row", 0),
                    line_end=item.get("end_location", {}).get("row", 0)
                    or item.get("location", {}).get("row", 0),
                    message=item.get("message", ""),
                )
            )
        return findings

    @staticmethod
    def _category(code: str) -> Category:
        if code.startswith("C9"):
            return Category.COMPLEXITY
        if code.startswith(("F8", "B")):
            return Category.BUG_RISK
        return Category.STYLE

    @staticmethod
    def _severity(code: str) -> Severity:
        if code.startswith("F8"):  # undefined names and friends: it will crash
            return Severity.ERROR
        if code.startswith(("B", "C9")):
            return Severity.WARNING
        return Severity.INFO


class BanditAnalyzer:
    name = "bandit"
    languages = frozenset({"python"})

    _SEVERITY: typing.ClassVar[dict[str, Severity]] = {
        "LOW": Severity.WARNING,
        "MEDIUM": Severity.ERROR,
        "HIGH": Severity.CRITICAL,
    }

    def sandbox_step(self) -> Step:
        return Step(id=self.name, cmd=["bandit", "-r", ".", "-f", "json", "-q"], timeout_s=60)

    def parse(self, out: StepOutput) -> list[NormalizedFinding]:
        doc = load_json_output(self.name, out)
        if not isinstance(doc, dict):
            return []
        findings = []
        for item in doc.get("results", []):
            line = item.get("line_number", 0)
            line_range = item.get("line_range") or [line]
            findings.append(
                NormalizedFinding(
                    analyzer=self.name,
                    rule_id=item.get("test_id", "bandit"),
                    severity=self._SEVERITY.get(
                        item.get("issue_severity", "LOW"), Severity.WARNING
                    ),
                    category=Category.SECURITY,
                    file=normalize_path(item.get("filename", "")),
                    line_start=line,
                    line_end=max(line_range),
                    message=item.get("issue_text", ""),
                )
            )
        return findings


class RadonAnalyzer:
    name = "radon"
    languages = frozenset({"python"})

    # Ranks A/B are healthy; C and worse become findings.
    _SEVERITY: typing.ClassVar[dict[str, Severity]] = {
        "C": Severity.WARNING,
        "D": Severity.ERROR,
        "E": Severity.ERROR,
        "F": Severity.CRITICAL,
    }

    def sandbox_step(self) -> Step:
        return Step(id=self.name, cmd=["radon", "cc", "-j", "."], timeout_s=60)

    def parse(self, out: StepOutput) -> list[NormalizedFinding]:
        doc = load_json_output(self.name, out)
        if not isinstance(doc, dict):
            return []
        findings = []
        for path, blocks in doc.items():
            if not isinstance(blocks, list):
                continue  # radon reports per-file errors as dicts
            for block in blocks:
                rank = block.get("rank", "A")
                if rank not in self._SEVERITY:
                    continue
                name = block.get("name", "?")
                complexity = block.get("complexity", "?")
                findings.append(
                    NormalizedFinding(
                        analyzer=self.name,
                        rule_id=f"radon-cc-{rank}",
                        severity=self._SEVERITY[rank],
                        category=Category.COMPLEXITY,
                        file=normalize_path(path),
                        line_start=block.get("lineno", 0),
                        line_end=block.get("endline", 0) or block.get("lineno", 0),
                        message=(
                            f"'{name}' has cyclomatic complexity {complexity} (rank {rank}). "
                            "Deeply branching code is hard to test and to reason about — "
                            "consider splitting it into smaller functions."
                        ),
                    )
                )
        return findings


class SemgrepAnalyzer:
    """Shared by both languages; instantiated with the vendored ruleset path."""

    _SEVERITY: typing.ClassVar[dict[str, Severity]] = {
        "INFO": Severity.INFO,
        "WARNING": Severity.WARNING,
        "ERROR": Severity.ERROR,
    }

    def __init__(self, language: str, rules_path: str) -> None:
        self.name = "semgrep"
        self.languages = frozenset({language})
        self._rules_path = rules_path

    def sandbox_step(self) -> Step:
        return Step(
            id=self.name,
            cmd=[
                "semgrep",
                "scan",
                "--metrics=off",
                "--json",
                "--quiet",
                "--disable-version-check",
                f"--config={self._rules_path}",
                ".",
            ],
            timeout_s=90,
        )

    def parse(self, out: StepOutput) -> list[NormalizedFinding]:
        doc = load_json_output(self.name, out)
        if not isinstance(doc, dict):
            return []
        findings = []
        for item in doc.get("results", []):
            extra = item.get("extra", {})
            # check_id is prefixed with the rule file path; keep the rule's own id
            rule_id = item.get("check_id", "semgrep").split(".")[-1]
            findings.append(
                NormalizedFinding(
                    analyzer=self.name,
                    rule_id=rule_id,
                    severity=self._SEVERITY.get(extra.get("severity", "WARNING"), Severity.WARNING),
                    category=Category.SECURITY,
                    file=normalize_path(item.get("path", "")),
                    line_start=item.get("start", {}).get("line", 0),
                    line_end=item.get("end", {}).get("line", 0),
                    message=extra.get("message", "").strip(),
                )
            )
        return findings
