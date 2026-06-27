import hashlib
import openai
from django.conf import settings
from openai import OpenAI

EMBEDDING_MODEL = "text-embedding-3-small"
EMBEDDING_DIM = 1536


def get_embedding(text: str) -> list[float]:
    """
    Return the embedding vector for text.
    Results are cached in EmbeddingCache to avoid redundant API calls.
    Raises AIServiceError on OpenAI failures.
    """
    from ai.models import EmbeddingCache
    from ai.service import AIServiceError

    text_hash = hashlib.sha256(text.encode()).hexdigest()

    try:
        return list(EmbeddingCache.objects.get(text_hash=text_hash).embedding_vector)
    except EmbeddingCache.DoesNotExist:
        pass

    client = OpenAI(api_key=settings.OPENAI_API_KEY)

    try:
        response = client.embeddings.create(model=EMBEDDING_MODEL, input=text)
    except openai.AuthenticationError:
        raise AIServiceError("OpenAI authentication failed — check OPENAI_API_KEY.", status_code=500)
    except openai.RateLimitError:
        raise AIServiceError("OpenAI rate limit reached. Please try again shortly.", status_code=429)
    except openai.APITimeoutError:
        raise AIServiceError("OpenAI embedding request timed out.", status_code=503)
    except openai.APIConnectionError:
        raise AIServiceError("Could not reach OpenAI.", status_code=503)

    vector = response.data[0].embedding

    EmbeddingCache.objects.create(
        text_hash=text_hash,
        embedding_vector=vector,
        model_used=EMBEDDING_MODEL,
    )

    return vector
