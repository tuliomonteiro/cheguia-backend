from pgvector.django import CosineDistance
from documents.models import Document

TOP_K = 5
MAX_CONTEXT_CHARS = 4000
RELEVANCE_THRESHOLD = 0.3  # cosine distance; lower = more similar


def retrieve_context(query_vector: list[float]) -> tuple[str, list[str]]:
    """
    Find the top-K most similar documents and return (context_text, sources).
    Returns ('', []) when no embedded documents exist or none are relevant enough.
    """
    docs = (
        Document.objects
        .exclude(embedding_vector=None)
        .annotate(distance=CosineDistance('embedding_vector', query_vector))
        .filter(distance__lte=RELEVANCE_THRESHOLD)
        .order_by('distance')[:TOP_K]
    )

    if not docs:
        return "", []

    parts: list[str] = []
    sources: list[str] = []
    total_chars = 0

    for doc in docs:
        remaining = MAX_CONTEXT_CHARS - total_chars
        if remaining <= 0:
            break
        excerpt = doc.content[:remaining]
        parts.append(f"### {doc.title}\n{excerpt}")
        total_chars += len(excerpt)
        if doc.source_url:
            sources.append(doc.source_url)

    return "\n\n".join(parts), sources
