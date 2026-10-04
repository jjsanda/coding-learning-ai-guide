"""Misconception taxonomy: deterministic rule → concept mapping.

The instructor dashboard aggregates these tags. They come from the YAML
taxonomy, never from LLM output, so class-wide statistics are reproducible
and trustworthy.
"""

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import yaml

_TAXONOMY_PATH = Path(__file__).resolve().parents[1] / "taxonomy" / "misconceptions.yaml"


@dataclass(frozen=True)
class Misconception:
    tag: str
    title: str
    summary: str


@lru_cache
def _load() -> tuple[dict[str, Misconception], dict[str, str]]:
    with _TAXONOMY_PATH.open() as fh:
        doc = yaml.safe_load(fh)
    by_tag: dict[str, Misconception] = {}
    rule_to_tag: dict[str, str] = {}
    for entry in doc["misconceptions"]:
        misconception = Misconception(
            tag=entry["tag"], title=entry["title"], summary=entry["summary"].strip()
        )
        by_tag[misconception.tag] = misconception
        for rule in entry["rules"]:
            rule_to_tag[str(rule)] = misconception.tag
    return by_tag, rule_to_tag


def tag_for_rule(rule_id: str) -> str | None:
    return _load()[1].get(rule_id)


def misconception(tag: str) -> Misconception | None:
    return _load()[0].get(tag)


def all_misconceptions() -> list[Misconception]:
    return list(_load()[0].values())
