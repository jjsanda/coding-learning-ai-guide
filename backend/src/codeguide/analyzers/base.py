"""Analyzer plugin contract.

Each analyzer contributes one command that runs *inside* the sandbox
(:meth:`Analyzer.sandbox_step`) and a parser that runs orchestrator-side,
turning the tool's raw JSON into normalized :class:`NormalizedFinding`
records. Adding a tool or a language means implementing this protocol and
registering it — see docs/adding-a-language.md.
"""

import json
from dataclasses import dataclass
from typing import Any, Protocol

import structlog

from codeguide.execution.base import Step, StepOutput
from codeguide.models import Category, Severity

log = structlog.get_logger()


@dataclass(frozen=True)
class NormalizedFinding:
    analyzer: str
    rule_id: str
    severity: Severity
    category: Category
    file: str
    line_start: int
    line_end: int
    message: str


class Analyzer(Protocol):
    name: str
    languages: frozenset[str]

    def sandbox_step(self) -> Step:
        """The command to execute inside the sandbox."""
        ...

    def parse(self, out: StepOutput) -> list[NormalizedFinding]:
        """Normalize the tool's raw output. Runs on trusted infrastructure."""
        ...


def normalize_path(path: str) -> str:
    """Map tool-reported paths ('/work/main.py', './main.py') to 'main.py'."""
    for prefix in ("/work/", "./"):
        if path.startswith(prefix):
            path = path[len(prefix) :]
    return path


def load_json_output(analyzer: str, out: StepOutput) -> Any | None:
    """Parse tool stdout as JSON; tolerate broken tools without failing the run."""
    if out.timed_out:
        log.warning("analyzer_timed_out", analyzer=analyzer)
        return None
    if not out.stdout.strip():
        if out.exit_code != 0:
            log.warning("analyzer_no_output", analyzer=analyzer, exit_code=out.exit_code)
        return None
    try:
        return json.loads(out.stdout)
    except json.JSONDecodeError:
        log.warning("analyzer_bad_json", analyzer=analyzer, exit_code=out.exit_code)
        return None
