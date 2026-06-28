import logging
import time
import openai
from django.conf import settings
from langchain_openai import ChatOpenAI
from langchain.schema import HumanMessage, AIMessage, SystemMessage

logger = logging.getLogger(__name__)

BASE_SYSTEM_PROMPT = (
    "Você é o Cheguia, um assistente de IA especializado em ajudar brasileiros e outros "
    "imigrantes a navegar pela burocracia paraguaia: imigração, impostos (SET/RUC), "
    "serviços públicos (ANDE, ESSAP), abertura de conta bancária e adaptação local. "
    "Forneça informações precisas e práticas. Cite as fontes quando disponível. "
    "Responda sempre no mesmo idioma que o usuário usou (português ou espanhol)."
)

RAG_CONTEXT_HEADER = (
    "\n\nContexto relevante da base de conhecimento:\n"
    "---\n{context}\n---\n"
    "Use o contexto acima para fundamentar sua resposta quando pertinente."
)

MAX_HISTORY_MESSAGES = 10
MODEL = "gpt-4o-mini"


class AIServiceError(Exception):
    """Raised for recoverable OpenAI errors; carries an HTTP status code."""
    def __init__(self, message: str, status_code: int = 503):
        super().__init__(message)
        self.status_code = status_code


def _build_system_prompt(context: str) -> str:
    if not context:
        return BASE_SYSTEM_PROMPT
    return BASE_SYSTEM_PROMPT + RAG_CONTEXT_HEADER.format(context=context)


def _build_messages(user_message: str, history: list[dict], context: str) -> list:
    messages = [SystemMessage(content=_build_system_prompt(context))]
    for entry in history[-MAX_HISTORY_MESSAGES:]:
        if entry["role"] == "user":
            messages.append(HumanMessage(content=entry["content"]))
        elif entry["role"] == "assistant":
            messages.append(AIMessage(content=entry["content"]))
    messages.append(HumanMessage(content=user_message))
    return messages


def _try_rag(user_message: str) -> tuple[str, list[str]]:
    """Attempt RAG retrieval; return empty results on any failure so chat still works."""
    try:
        from ai.embeddings import get_embedding
        from ai.rag import retrieve_context
        vector = get_embedding(user_message)
        return retrieve_context(vector)
    except Exception:
        logger.exception("RAG retrieval failed; falling back to plain chat.")
        return "", []


def get_response(user_message: str, history: list[dict] | None = None) -> dict:
    """
    Call OpenAI (with RAG context when available) and return:
    {'message': str, 'sources': list, 'tokens_used': int, 'processing_time': float}
    Raises AIServiceError on any OpenAI failure.
    """
    context, sources = _try_rag(user_message)

    llm = ChatOpenAI(
        api_key=settings.OPENAI_API_KEY,
        model=MODEL,
        temperature=0.3,
        timeout=30,
    )

    messages = _build_messages(user_message, history or [], context)

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
        "sources": sources,
        "tokens_used": tokens.get("total_tokens", 0) if isinstance(tokens, dict) else 0,
        "processing_time": round(time.monotonic() - start, 3),
    }
