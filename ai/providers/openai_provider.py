import openai as openai_sdk
from django.conf import settings
from langchain_openai import ChatOpenAI
from openai import OpenAI

from ai.exceptions import AIServiceError
from ai.providers.base import ChatProvider, ChatResult, EmbeddingProvider
from ai.providers.utils import to_langchain_messages


def _get_api_key() -> str:
    key = getattr(settings, "OPENAI_API_KEY", "")
    if not key:
        raise AIServiceError("OPENAI_API_KEY is not configured.", status_code=500)
    return key


def _map_openai_error(exc: Exception) -> AIServiceError:
    if isinstance(exc, openai_sdk.AuthenticationError):
        return AIServiceError("OpenAI authentication failed — check OPENAI_API_KEY.", status_code=500)
    if isinstance(exc, openai_sdk.RateLimitError):
        return AIServiceError("OpenAI rate limit reached. Please try again shortly.", status_code=429)
    if isinstance(exc, openai_sdk.APITimeoutError):
        return AIServiceError("OpenAI request timed out. Please try again.", status_code=503)
    if isinstance(exc, openai_sdk.APIConnectionError):
        return AIServiceError("Could not reach OpenAI. Please try again.", status_code=503)
    if isinstance(exc, openai_sdk.APIError):
        return AIServiceError(f"OpenAI API error: {exc}", status_code=503)
    return AIServiceError(f"Unexpected OpenAI error: {exc}", status_code=503)


class OpenAIChatProvider(ChatProvider):
    def complete(
        self,
        messages: list[dict],
        temperature: float = 0.3,
        timeout: int = 30,
    ) -> ChatResult:
        model = getattr(settings, "AI_CHAT_MODEL", "gpt-4o-mini")
        llm = ChatOpenAI(
            api_key=_get_api_key(),
            model=model,
            temperature=temperature,
            timeout=timeout,
        )
        try:
            response = llm.invoke(to_langchain_messages(messages))
        except Exception as exc:
            raise _map_openai_error(exc) from exc

        tokens = getattr(response, "usage_metadata", {})
        tokens_used = tokens.get("total_tokens", 0) if isinstance(tokens, dict) else 0
        return ChatResult(content=response.content, tokens_used=tokens_used)


class OpenAIEmbeddingProvider(EmbeddingProvider):
    dimensions = 1536

    @property
    def model_name(self) -> str:
        return getattr(settings, "AI_EMBEDDING_MODEL", "text-embedding-3-small")

    def embed(self, text: str) -> list[float]:
        client = OpenAI(api_key=_get_api_key())
        try:
            response = client.embeddings.create(model=self.model_name, input=text)
        except Exception as exc:
            raise _map_openai_error(exc) from exc
        return response.data[0].embedding
