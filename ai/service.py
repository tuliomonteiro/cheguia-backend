import time
import openai
from django.conf import settings
from langchain_openai import ChatOpenAI
from langchain.schema import HumanMessage, AIMessage, SystemMessage

SYSTEM_PROMPT = (
    "Você é o Cheguia, um assistente de IA especializado em ajudar brasileiros e outros "
    "imigrantes a navegar pela burocracia paraguaia: imigração, impostos (SET/RUC), "
    "serviços públicos (ANDE, ESSAP), abertura de conta bancária e adaptação local. "
    "Forneça informações precisas e práticas. Quando disponível, cite a fonte. "
    "Responda sempre no mesmo idioma que o usuário usou (português ou espanhol)."
)

MAX_HISTORY_MESSAGES = 10
MODEL = "gpt-4o-mini"


class AIServiceError(Exception):
    """Raised for recoverable OpenAI errors; carries an HTTP status code."""
    def __init__(self, message: str, status_code: int = 503):
        super().__init__(message)
        self.status_code = status_code


def _build_messages(user_message: str, history: list[dict]) -> list:
    messages = [SystemMessage(content=SYSTEM_PROMPT)]
    for entry in history[-MAX_HISTORY_MESSAGES:]:
        if entry["role"] == "user":
            messages.append(HumanMessage(content=entry["content"]))
        elif entry["role"] == "assistant":
            messages.append(AIMessage(content=entry["content"]))
    messages.append(HumanMessage(content=user_message))
    return messages


def get_response(user_message: str, history: list[dict] | None = None) -> dict:
    """
    Call OpenAI and return {'message': str, 'sources': list, 'tokens_used': int, 'processing_time': float}.
    Raises AIServiceError on any OpenAI failure.
    """
    llm = ChatOpenAI(
        api_key=settings.OPENAI_API_KEY,
        model=MODEL,
        temperature=0.3,
        timeout=30,
    )

    messages = _build_messages(user_message, history or [])

    start = time.monotonic()
    try:
        response = llm.invoke(messages)
    except openai.AuthenticationError:
        raise AIServiceError("OpenAI authentication failed — check OPENAI_API_KEY.", status_code=500)
    except openai.RateLimitError:
        raise AIServiceError("OpenAI rate limit reached. Please try again shortly.", status_code=429)
    except openai.APITimeoutError:
        raise AIServiceError("OpenAI request timed out. Please try again.", status_code=503)
    except openai.APIConnectionError:
        raise AIServiceError("Could not reach OpenAI. Please try again.", status_code=503)
    except openai.APIError as exc:
        raise AIServiceError(f"OpenAI error: {exc}", status_code=503)

    tokens = getattr(response, "usage_metadata", {})

    return {
        "message": response.content,
        "sources": [],
        "tokens_used": tokens.get("total_tokens", 0) if isinstance(tokens, dict) else 0,
        "processing_time": round(time.monotonic() - start, 3),
    }
