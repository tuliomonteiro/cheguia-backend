"""
Provider registry — the only place that knows which concrete adapter to use.

To switch providers, set AI_CHAT_PROVIDER (and AI_EMBEDDING_PROVIDER) in the
environment. No other file needs to change.

Supported values:
    AI_CHAT_PROVIDER      : "openai" | "gemini"   (default: "openai")
    AI_EMBEDDING_PROVIDER : "openai"               (default: "openai")

Note: switching embedding providers requires re-embedding all documents and,
if the new provider uses different dimensions, a database migration.
"""

from ai.providers.base import ChatProvider, ChatResult, EmbeddingProvider


def get_chat_provider() -> ChatProvider:
    from django.conf import settings
    from ai.exceptions import AIServiceError

    name = getattr(settings, "AI_CHAT_PROVIDER", "openai")

    if name == "openai":
        from ai.providers.openai_provider import OpenAIChatProvider
        return OpenAIChatProvider()
    if name == "gemini":
        from ai.providers.gemini_provider import GeminiChatProvider
        return GeminiChatProvider()

    raise AIServiceError(
        f"Unknown chat provider: {name!r}. Supported: 'openai', 'gemini'.",
        status_code=500,
    )


def get_embedding_provider() -> EmbeddingProvider:
    from django.conf import settings
    from ai.exceptions import AIServiceError

    name = getattr(settings, "AI_EMBEDDING_PROVIDER", "openai")

    if name == "openai":
        from ai.providers.openai_provider import OpenAIEmbeddingProvider
        return OpenAIEmbeddingProvider()

    raise AIServiceError(
        f"Unknown embedding provider: {name!r}. "
        "Only 'openai' is currently supported. "
        "Switching providers requires re-indexing all documents.",
        status_code=500,
    )


__all__ = ["ChatProvider", "ChatResult", "EmbeddingProvider", "get_chat_provider", "get_embedding_provider"]
