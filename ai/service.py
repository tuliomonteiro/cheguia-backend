import logging
import time

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


def _build_system_prompt(context: str) -> str:
    if not context:
        return BASE_SYSTEM_PROMPT
    return BASE_SYSTEM_PROMPT + RAG_CONTEXT_HEADER.format(context=context)


def _build_messages(user_message: str, history: list[dict], context: str) -> list[dict]:
    messages = [{"role": "system", "content": _build_system_prompt(context)}]
    for entry in history[-MAX_HISTORY_MESSAGES:]:
        if entry["role"] in ("user", "assistant"):
            messages.append({"role": entry["role"], "content": entry["content"]})
    messages.append({"role": "user", "content": user_message})
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
    Generate a chat response using whichever provider is configured via
    AI_CHAT_PROVIDER. Raises AIServiceError on provider failures.

    Returns:
        {'message': str, 'sources': list, 'tokens_used': int, 'processing_time': float}
    """
    from ai.providers import get_chat_provider

    context, sources = _try_rag(user_message)
    messages = _build_messages(user_message, history or [], context)

    provider = get_chat_provider()
    start = time.monotonic()
    result = provider.complete(messages)

    return {
        "message": result.content,
        "sources": sources,
        "tokens_used": result.tokens_used,
        "processing_time": round(time.monotonic() - start, 3),
    }
