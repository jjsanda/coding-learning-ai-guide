# ADR 0006: Multi-provider LLM with a deterministic fallback

## Status

Accepted

## Context

Tying feedback to one LLM vendor is a bad deal for an educational tool:
institutions have different procurement realities, some classrooms want a
local model (Ollama) for privacy, and the tool must remain fully usable with
**no API key at all** — a student's feedback can't depend on someone's billing
account.

## Decision

A `FeedbackProvider` protocol with four implementations: Anthropic, OpenAI,
Ollama, and a deterministic `TemplateProvider` that builds feedback directly
from the misconception taxonomy and finding categories — no key, no network.

`provider_chain()` in `feedback/registry.py` builds an ordered list that the
**template provider always terminates**. With `CODEGUIDE_FEEDBACK_PROVIDER=auto`
(the default), the first provider with credentials configured goes first; a
named provider is tried first explicitly. If an LLM provider raises, the
service moves down the chain and ultimately degrades to templates — and the
stored feedback is attributed as `template(fallback)` so the UI honestly shows
that a model failed and the deterministic path stepped in, rather than
passing template output off as an LLM's.

## Consequences

- The tool works offline and keyless by construction: the chain cannot end
  without a result, and feedback generation cannot hard-fail a submission.
- Provider parity has a real cost: every LLM provider must support the same
  structured output (summary, per-finding items with `finding_ref`, next
  steps), which constrains which models are usable and how each adapter is
  written.
- The template provider is not a stub — it is the default experience for
  every keyless deployment and the safety net for every keyed one, so its
  explanations, hints and taxonomy coverage must be maintained as a
  first-class feature, effectively doubling the writing work for each new
  misconception.
