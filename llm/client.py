import logging
from typing import Any

import ollama
from django.conf import settings

logger = logging.getLogger(__name__)


def _client() -> ollama.Client:
    return ollama.Client(host=settings.OLLAMA_BASE_URL)


def get_embedding(text: str) -> list[float]:
    """Generate an embedding vector for text via Ollama."""
    response = _client().embeddings(model=settings.OLLAMA_EMBED_MODEL, prompt=text)
    return response['embedding']


def chat(
    messages: list[dict[str, str]] | str,
    model: str | None = None,
) -> str:
    """
    Send a chat request to Ollama.

    Accepts either a list of message dicts (role/content) or a plain string prompt.
    Returns the assistant message content as a string.
    """
    if isinstance(messages, str):
        messages = [{'role': 'user', 'content': messages}]

    response = _client().chat(
        model=model or settings.OLLAMA_CHAT_MODEL,
        messages=messages,
    )
    # Support both dict and Pydantic-style response objects
    if isinstance(response, dict):
        return response['message']['content']
    return response.message.content
