"""Language → analyzers registry."""

from codeguide.analyzers.base import Analyzer
from codeguide.analyzers.javascript_tools import EslintAnalyzer
from codeguide.analyzers.python_tools import (
    BanditAnalyzer,
    RadonAnalyzer,
    RuffAnalyzer,
    SemgrepAnalyzer,
)

_REGISTRY: dict[str, list[Analyzer]] = {
    "python": [
        RuffAnalyzer(),
        BanditAnalyzer(),
        RadonAnalyzer(),
        SemgrepAnalyzer("python", "/opt/rules/python"),
    ],
    "javascript": [
        EslintAnalyzer(),
        SemgrepAnalyzer("javascript", "/opt/rules/javascript"),
    ],
}


def analyzers_for(language: str) -> list[Analyzer]:
    return _REGISTRY.get(language, [])


def supported_languages() -> list[str]:
    return sorted(_REGISTRY)
