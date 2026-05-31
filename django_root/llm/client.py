import logging
import re
from collections.abc import Iterator

import ollama
from django.conf import settings

logger = logging.getLogger(__name__)
_raw_logger = logging.getLogger("llm.raw")

# Matches <think>...</think> blocks emitted by Qwen3/3.5 thinking models.
_THINK_RE = re.compile(r"<think>.*?</think>", re.DOTALL)
# Stray closing tag when Ollama already stripped the opening tag.
_THINK_CLOSE_RE = re.compile(r"</think>", re.DOTALL)
# Chat-template tokens that some models leak into the output.
_CHAT_TOKENS_RE = re.compile(r"<\|[^|>]+\|>")


def _strip_thinking(text: str) -> str:
    """Remove <think>…</think> blocks, stray closing tags, and chat-template
    tokens emitted by Qwen3/3.5 and similar models."""
    text = _THINK_RE.sub("", text)
    text = _THINK_CLOSE_RE.sub("", text)
    text = _CHAT_TOKENS_RE.sub("", text)
    return text.strip()


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
        content = response["message"]["content"]
    else:
        content = response.message.content
    _raw_logger.debug("[model=%s] RAW OUTPUT:\n%s", model, content)
    return _strip_thinking(content)


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
    inside_think = False
    buf = ""
    for chunk in _client().chat(model=model, messages=messages, stream=True):
        if isinstance(chunk, dict):
            piece = chunk["message"]["content"]
        else:
            piece = chunk.message.content

        if not piece:
            continue

        buf += piece
        # Stream-safe stripping: buffer until we know whether we're inside a
        # <think> block.  Flush safe text to the caller as soon as possible.
        while buf:
            if inside_think:
                end = buf.find("</think>")
                if end == -1:
                    buf = ""  # discard thinking content, wait for more chunks
                    break
                buf = buf[end + len("</think>") :]
                inside_think = False
            else:
                start = buf.find("<think>")
                if start == -1:
                    yield buf
                    buf = ""
                    break
                if start > 0:
                    yield buf[:start]
                buf = buf[start + len("<think>") :]
                inside_think = True
    if buf and not inside_think:
        yield buf
