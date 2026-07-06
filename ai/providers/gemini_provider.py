from django.conf import settings
from langchain_google_genai import ChatGoogleGenerativeAI

from ai.exceptions import AIServiceError
from ai.providers.base import ChatProvider, ChatResult
from ai.providers.utils import to_langchain_messages


def _get_api_key() -> str:
    key = getattr(settings, "GEMINI_API_KEY", "")
    if not key:
        raise AIServiceError("GEMINI_API_KEY is not configured.", status_code=500)
    return key


def _map_gemini_error(exc: Exception) -> AIServiceError:
    """
    google-api-core exceptions are transitive deps of langchain-google-genai.
    We catch by type when available, fall back to message inspection otherwise.
    """
    try:
        from google.api_core import exceptions as gexc
        if isinstance(exc, gexc.Unauthenticated):
            return AIServiceError("Gemini authentication failed — check GEMINI_API_KEY.", status_code=500)
        if isinstance(exc, gexc.ResourceExhausted):
            return AIServiceError("Gemini rate limit reached. Please try again shortly.", status_code=429)
        if isinstance(exc, gexc.DeadlineExceeded):
            return AIServiceError("Gemini request timed out. Please try again.", status_code=503)
        if isinstance(exc, (gexc.ServiceUnavailable, gexc.Unknown)):
            return AIServiceError(f"Gemini service unavailable: {exc}", status_code=503)
    except ImportError:
        pass

    msg = str(exc).lower()
    if "api_key" in msg or "unauthenticated" in msg or "permission" in msg:
        return AIServiceError("Gemini authentication failed — check GEMINI_API_KEY.", status_code=500)
    if "quota" in msg or "rate" in msg or "429" in msg or "resource_exhausted" in msg:
        return AIServiceError("Gemini rate limit reached. Please try again shortly.", status_code=429)
    if "timeout" in msg or "deadline" in msg:
        return AIServiceError("Gemini request timed out. Please try again.", status_code=503)
    return AIServiceError(f"Gemini error: {exc}", status_code=503)


class GeminiChatProvider(ChatProvider):
    def complete(
        self,
        messages: list[dict],
        temperature: float = 0.3,
        timeout: int = 30,
    ) -> ChatResult:
        model = getattr(settings, "AI_CHAT_MODEL", "gemini-1.5-flash")
        llm = ChatGoogleGenerativeAI(
            model=model,
            google_api_key=_get_api_key(),
            temperature=temperature,
            request_timeout=timeout,
        )
        try:
            response = llm.invoke(to_langchain_messages(messages))
        except Exception as exc:
            raise _map_gemini_error(exc) from exc

        tokens = getattr(response, "usage_metadata", None)
        tokens_used = getattr(tokens, "total_token_count", 0) if tokens else 0
        return ChatResult(content=response.content, tokens_used=tokens_used)
