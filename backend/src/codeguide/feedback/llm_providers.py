"""LLM feedback providers: Anthropic, OpenAI, Ollama.

All three produce the shared :class:`FeedbackModel` schema. Items whose
``finding_ref`` doesn't exist in the context are dropped — the model must
ground every explanation in a real, deterministic finding.
"""

import json
import os

import httpx
import structlog

from codeguide.config import Settings
from codeguide.feedback.base import FeedbackContext, FeedbackModel, FeedbackResult
from codeguide.feedback.prompts import SYSTEM_PROMPT, build_user_prompt

log = structlog.get_logger()


def drop_ungrounded_items(feedback: FeedbackModel, ctx: FeedbackContext) -> FeedbackModel:
    """Remove items referencing findings that don't exist (anti-hallucination)."""
    valid_ids = {f.id for f in ctx.findings}
    grounded = [i for i in feedback.items if i.finding_ref in valid_ids]
    if len(grounded) != len(feedback.items):
        log.warning(
            "dropped_ungrounded_feedback_items",
            dropped=len(feedback.items) - len(grounded),
        )
    return feedback.model_copy(update={"items": grounded})


class AnthropicProvider:
    name = "anthropic"

    def __init__(self, settings: Settings) -> None:
        self._model = settings.anthropic_model
        self._timeout = settings.feedback_timeout_s

    def available(self) -> bool:
        return bool(os.environ.get("ANTHROPIC_API_KEY"))

    async def generate(self, ctx: FeedbackContext) -> FeedbackResult:
        from anthropic import AsyncAnthropic

        client = AsyncAnthropic(timeout=self._timeout)
        response = await client.messages.parse(
            model=self._model,
            max_tokens=4096,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": build_user_prompt(ctx)}],
            output_format=FeedbackModel,
        )
        parsed = response.parsed_output
        if parsed is None:
            raise RuntimeError("anthropic returned no parsed output")
        return FeedbackResult(
            provider=self.name,
            model=self._model,
            feedback=drop_ungrounded_items(parsed, ctx),
        )


class OpenAIProvider:
    name = "openai"

    def __init__(self, settings: Settings) -> None:
        self._model = settings.openai_model
        self._timeout = settings.feedback_timeout_s

    def available(self) -> bool:
        return bool(os.environ.get("OPENAI_API_KEY"))

    async def generate(self, ctx: FeedbackContext) -> FeedbackResult:
        from openai import AsyncOpenAI

        client = AsyncOpenAI(timeout=self._timeout)
        response = await client.chat.completions.create(
            model=self._model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": build_user_prompt(ctx)},
            ],
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": "feedback",
                    "schema": FeedbackModel.model_json_schema(),
                },
            },
        )
        content = response.choices[0].message.content or ""
        feedback = FeedbackModel.model_validate_json(content)
        return FeedbackResult(
            provider=self.name,
            model=self._model,
            feedback=drop_ungrounded_items(feedback, ctx),
        )


class OllamaProvider:
    name = "ollama"

    def __init__(self, settings: Settings) -> None:
        self._base_url = settings.ollama_base_url
        self._model = settings.ollama_model
        self._timeout = settings.feedback_timeout_s

    def available(self) -> bool:
        return bool(self._base_url)

    async def generate(self, ctx: FeedbackContext) -> FeedbackResult:
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await client.post(
                f"{self._base_url}/api/chat",
                json={
                    "model": self._model,
                    "stream": False,
                    "format": FeedbackModel.model_json_schema(),
                    "messages": [
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": build_user_prompt(ctx)},
                    ],
                },
            )
            response.raise_for_status()
            content = response.json()["message"]["content"]

        try:
            feedback = FeedbackModel.model_validate_json(content)
        except ValueError:
            # local models occasionally wrap JSON in prose; one repair attempt
            start, end = content.find("{"), content.rfind("}")
            if start < 0 or end <= start:
                raise
            feedback = FeedbackModel.model_validate(json.loads(content[start : end + 1]))
        return FeedbackResult(
            provider=self.name,
            model=self._model,
            feedback=drop_ungrounded_items(feedback, ctx),
        )
