"""Conversation context window management."""

import logging

logger = logging.getLogger(__name__)

# Conservative default: 6 000 tokens × 4 chars/token = 24 000 chars.
# Override via Django settings: AGENT_MAX_CONTEXT_TOKENS (int).
_DEFAULT_MAX_TOKENS = 6_000
_CHARS_PER_TOKEN = 4


def _total_chars(messages: list[dict]) -> int:
    return sum(len(m.get("content", "")) for m in messages)


def trim_conversation(
    conversation: list[dict],
    max_tokens: int | None = None,
) -> list[dict]:
    """Trim *conversation* to stay within the token budget.

    Strategy:
    - Always keep the system message (index 0) and the original user query
      (index 1).
    - Drop the oldest assistant + tool-result pairs from the middle until the
      total character count is within budget.
    - Remaining messages are returned in original order.

    If trimming occurs, a synthetic ``{"role": "system", ...}`` notice is
    inserted between the kept head and tail so the LLM knows history was cut.
    """
    if max_tokens is None:
        try:
            from django.conf import settings

            max_tokens = getattr(settings, "AGENT_MAX_CONTEXT_TOKENS", _DEFAULT_MAX_TOKENS)
        except Exception:
            max_tokens = _DEFAULT_MAX_TOKENS

    max_chars = max_tokens * _CHARS_PER_TOKEN

    if _total_chars(conversation) <= max_chars:
        return conversation

    if len(conversation) <= 2:
        # Cannot trim further – return as-is and let the LLM deal with it.
        return conversation

    head = conversation[:2]  # system + first user message
    tail = list(conversation[2:])

    dropped = 0
    # Drop oldest pairs (assistant response + tool result = 2 messages) first.
    while tail and _total_chars(head + tail) > max_chars:
        remove = 2 if len(tail) >= 2 else 1
        tail = tail[remove:]
        dropped += remove

    if dropped:
        notice = {
            "role": "system",
            "content": (f"[{dropped} ältere Nachrichten wurden wegen des Kontextlimits entfernt.]"),
        }
        result = head + [notice] + tail
        logger.debug(
            "Context trimmed: dropped %d messages, total chars %d → %d",
            dropped,
            _total_chars(conversation),
            _total_chars(result),
        )
        return result

    return head + tail
