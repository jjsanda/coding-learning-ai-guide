"""Feedback provider selection.

``auto`` picks the first provider with credentials configured; the
deterministic template provider is always available as the final fallback,
so a deployment with no API keys still produces complete feedback.
"""

from codeguide.config import Settings
from codeguide.feedback.base import FeedbackProvider
from codeguide.feedback.llm_providers import AnthropicProvider, OllamaProvider, OpenAIProvider
from codeguide.feedback.template_provider import TemplateProvider


def _all_providers(settings: Settings) -> dict[str, FeedbackProvider]:
    return {
        "anthropic": AnthropicProvider(settings),
        "openai": OpenAIProvider(settings),
        "ollama": OllamaProvider(settings),
        "template": TemplateProvider(),
    }


def provider_chain(settings: Settings) -> list[FeedbackProvider]:
    """Providers to try in order; the template provider always terminates it."""
    providers = _all_providers(settings)
    template = providers["template"]

    if settings.feedback_provider == "template":
        return [template]
    if settings.feedback_provider != "auto":
        return [providers[settings.feedback_provider], template]

    chain = [
        provider
        for name, provider in providers.items()
        if name != "template" and provider.available()
    ]
    chain.append(template)
    return chain


def resolve_provider_name(settings: Settings) -> str:
    return provider_chain(settings)[0].name
