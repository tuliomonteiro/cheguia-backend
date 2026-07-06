import hashlib


def get_embedding(text: str) -> list[float]:
    """
    Return the embedding vector for text using the configured embedding provider.
    Results are cached in EmbeddingCache keyed by SHA-256 hash.
    Raises AIServiceError on provider failures.
    """
    from ai.models import EmbeddingCache
    from ai.providers import get_embedding_provider

    text_hash = hashlib.sha256(text.encode()).hexdigest()

    try:
        return list(EmbeddingCache.objects.get(text_hash=text_hash).embedding_vector)
    except EmbeddingCache.DoesNotExist:
        pass

    provider = get_embedding_provider()
    vector = provider.embed(text)

    EmbeddingCache.objects.create(
        text_hash=text_hash,
        embedding_vector=vector,
        model_used=provider.model_name,
    )

    return vector
