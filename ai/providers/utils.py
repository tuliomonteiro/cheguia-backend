from langchain.schema import AIMessage, HumanMessage, SystemMessage


def to_langchain_messages(messages: list[dict]) -> list:
    """Convert generic message dicts to LangChain message objects."""
    mapping = {
        "system": SystemMessage,
        "user": HumanMessage,
        "assistant": AIMessage,
    }
    return [
        mapping[msg["role"]](content=msg["content"])
        for msg in messages
        if msg["role"] in mapping
    ]
