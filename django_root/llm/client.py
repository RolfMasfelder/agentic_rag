import logging
from collections.abc import Iterator

import ollama
from django.conf import settings

logger = logging.getLogger(__name__)


def _client() -> ollama.Client:
    return ollama.Client(host=settings.OLLAMA_BASE_URL)


def get_embedding(text: str) -> list[float]:
    """Generate an embedding vector for text via Ollama."""
    response = _client().embeddings(model=settings.OLLAMA_EMBED_MODEL, prompt=text)
    return response["embedding"]


def chat(
    messages: list[dict[str, str]] | str,
    model: str | None = None,
) -> str:
    """Send a chat request to Ollama.

    Accepts either a list of message dicts (role/content) or a plain string prompt.
    Falls back to ``settings.OLLAMA_FALLBACK_MODEL`` when the primary model fails.
    Returns the assistant message content as a string.
    """
    if isinstance(messages, str):
        messages = [{"role": "user", "content": messages}]

    primary = model or settings.OLLAMA_CHAT_MODEL

    try:
        return _do_chat(primary, messages)
    except Exception as exc:
        fallback = getattr(settings, "OLLAMA_FALLBACK_MODEL", "")
        if fallback and fallback != primary:
            logger.warning(
                "Primary model %s failed (%s), retrying with fallback %s",
                primary,
                exc,
                fallback,
            )
            return _do_chat(fallback, messages)
        raise


def _do_chat(model: str, messages: list[dict[str, str]]) -> str:
    response = _client().chat(model=model, messages=messages)
    if isinstance(response, dict):
        return response["message"]["content"]
    return response.message.content


def chat_stream(
    messages: list[dict[str, str]] | str,
    model: str | None = None,
) -> Iterator[str]:
    """Streaming chat – yields text chunks as they arrive from Ollama.

    Falls back to ``settings.OLLAMA_FALLBACK_MODEL`` on connection errors.
    """
    if isinstance(messages, str):
        messages = [{"role": "user", "content": messages}]

    primary = model or settings.OLLAMA_CHAT_MODEL

    try:
        yield from _do_chat_stream(primary, messages)
    except Exception as exc:
        fallback = getattr(settings, "OLLAMA_FALLBACK_MODEL", "")
        if fallback and fallback != primary:
            logger.warning(
                "Streaming from %s failed (%s), retrying with fallback %s",
                primary,
                exc,
                fallback,
            )
            yield from _do_chat_stream(fallback, messages)
        else:
            raise


def _do_chat_stream(model: str, messages: list[dict[str, str]]) -> Iterator[str]:
    for chunk in _client().chat(model=model, messages=messages, stream=True):
        if isinstance(chunk, dict):
            yield chunk["message"]["content"]
        else:
            yield chunk.message.content
