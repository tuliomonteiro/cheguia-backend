from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class ChatResult:
    content: str
    tokens_used: int = 0


class ChatProvider(ABC):
    """
    Common interface for all chat-completion providers.

    Implementors receive messages in a provider-agnostic dict format and must
    translate errors into AIServiceError so the view layer stays unaware of
    which provider is active.

    Message format:
        [{'role': 'system' | 'user' | 'assistant', 'content': str}, ...]
    """

    @abstractmethod
    def complete(
        self,
        messages: list[dict],
        temperature: float = 0.3,
        timeout: int = 30,
    ) -> ChatResult: ...


class EmbeddingProvider(ABC):
    """
    Common interface for all text-embedding providers.

    Note: switching embedding providers in production requires re-embedding
    all documents and (if dimensions differ) a database migration.
    """

    dimensions: int  # Must be set as a class attribute by each subclass

    @abstractmethod
    def embed(self, text: str) -> list[float]:
        """Return a float vector of length self.dimensions."""
        ...

    @property
    def model_name(self) -> str:
        return "unknown"
