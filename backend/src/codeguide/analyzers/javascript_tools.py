"""JavaScript analyzers: eslint (style/bug risk/complexity/security)."""

from codeguide.analyzers.base import NormalizedFinding, load_json_output, normalize_path
from codeguide.execution.base import Step, StepOutput
from codeguide.models import Category, Severity

_COMPLEXITY_RULES = {"complexity", "max-depth", "max-lines-per-function"}
_SECURITY_RULES = {"no-eval", "no-implied-eval", "no-new-func"}
_BUG_RISK_RULES = {
    "no-undef",
    "no-fallthrough",
    "no-unreachable",
    "no-dupe-keys",
    "no-self-assign",
    "no-constant-condition",
    "eqeqeq",
}


class EslintAnalyzer:
    name = "eslint"
    languages = frozenset({"javascript"})

    def sandbox_step(self) -> Step:
        return Step(
            id=self.name,
            cmd=[
                "eslint",
                "--config",
                "/opt/runner/eslint.config.mjs",
                "--format",
                "json",
                "--no-error-on-unmatched-pattern",
                ".",
            ],
            timeout_s=60,
        )

    def parse(self, out: StepOutput) -> list[NormalizedFinding]:
        doc = load_json_output(self.name, out)
        if not isinstance(doc, list):
            return []
        findings = []
        for file_report in doc:
            path = normalize_path(file_report.get("filePath", ""))
            for msg in file_report.get("messages", []):
                rule_id = msg.get("ruleId") or "eslint"
                line = msg.get("line", 0) or 0
                findings.append(
                    NormalizedFinding(
                        analyzer=self.name,
                        rule_id=rule_id,
                        severity=self._severity(rule_id, msg.get("severity", 1)),
                        category=self._category(rule_id),
                        file=path,
                        line_start=line,
                        line_end=msg.get("endLine", line) or line,
                        message=msg.get("message", ""),
                    )
                )
        return findings

    @staticmethod
    def _category(rule_id: str) -> Category:
        if rule_id.startswith("security/") or rule_id in _SECURITY_RULES:
            return Category.SECURITY
        if rule_id in _COMPLEXITY_RULES:
            return Category.COMPLEXITY
        if rule_id in _BUG_RISK_RULES:
            return Category.BUG_RISK
        return Category.STYLE

    @staticmethod
    def _severity(rule_id: str, eslint_severity: int) -> Severity:
        if rule_id.startswith("security/") or rule_id in _SECURITY_RULES:
            return Severity.ERROR if eslint_severity == 2 else Severity.WARNING
        if eslint_severity == 2:
            return Severity.WARNING
        return Severity.INFO
