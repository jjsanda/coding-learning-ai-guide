# ADR 0001: Hybrid deterministic analysis + LLM narration

## Status

Accepted

## Context

The two obvious designs for automated code feedback both fail students. Pure-LLM
grading — "here is the code, tell me what's wrong" — hallucinates: it invents
issues that don't exist, misses issues that do, and gives different answers on
different days, which is unacceptable for anything that resembles assessment.
Pure static analysis is trustworthy but pedagogically useless to a beginner: a
first-semester student staring at `B608: hardcoded_sql_expressions` learns
nothing from it.

## Decision

Split the responsibilities along the trust boundary:

- **Deterministic tools produce the facts.** Static analyzers (Bandit, Semgrep,
  Ruff, radon, ESLint) and the assignment's test cases decide *what* is wrong.
  Every `Finding` row carries the analyzer, rule ID, file and line — it is a
  real, reproducible observation.
- **The LLM only narrates.** The feedback provider receives the findings and
  failing tests and explains them in plain language with a guiding question.
  Every feedback item must reference a concrete finding (`finding_ref`); an
  explanation that doesn't point at a real finding is discarded.
- **The dashboard aggregates only deterministic data.** Misconception tags come
  from the YAML rule-to-tag taxonomy (`analyzers/misconceptions.py`), never
  from model output, so class-wide statistics are reproducible.

## Consequences

- Feedback is trustworthy: nothing shown to a student or counted for an
  instructor was invented by a model.
- Runs are reproducible — the same submission yields the same findings and the
  same dashboard numbers, regardless of which LLM (if any) is configured.
- We give up the LLM's breadth: it cannot surface a genuine problem the
  analyzers didn't flag. Feedback quality is bounded by analyzer and taxonomy
  coverage, so extending those is where improvement effort must go.
