import json
import logging
from typing import Any

logger = logging.getLogger(__name__)

# Maximum number of candidates passed to the LLM in a single re-ranking call.
# Longer lists increase prompt size and latency.
_MAX_CANDIDATES = 20

_RERANK_PROMPT = """\
Du bewertest die Relevanz von Textabschnitten für eine Suchanfrage.

Anfrage: {query}

Abschnitte (als JSON-Liste, jeder Eintrag hat "idx" und "content"):
{candidates_json}

Antworte ausschließlich mit einem JSON-Array von Objekten der Form:
{{"idx": <Zahl>, "score": <Ganzzahl 0–10>}}
Bewerte jeden Abschnitt: 10 = sehr relevant, 0 = irrelevant.
Keine weiteren Erklärungen."""


def rerank(
    query: str,
    results: list[dict[str, Any]],
    top_k: int | None = None,
) -> list[dict[str, Any]]:
    """Re-rank *results* by relevance to *query* using the configured LLM.

    Each item in *results* must have a ``content`` key.  The function adds a
    ``rerank_score`` key (0–10) to every item and returns the list sorted by
    that score descending.

    If the LLM call fails, the original order is preserved and a warning is
    logged.  *top_k* optionally limits the returned list size.
    """
    if not results:
        return results

    candidates = results[: min(len(results), _MAX_CANDIDATES)]
    candidate_payload = [{"idx": i, "content": item.get("content", "")[:400]} for i, item in enumerate(candidates)]

    try:
        from llm.client import chat

        prompt = _RERANK_PROMPT.format(
            query=query,
            candidates_json=json.dumps(candidate_payload, ensure_ascii=False),
        )
        raw = chat(prompt)
        scores_raw: list[dict] = json.loads(raw)
        score_map: dict[int, int] = {entry["idx"]: int(entry["score"]) for entry in scores_raw}
    except Exception:
        logger.warning("Re-ranking LLM call failed; returning original order.")
        score_map = {}

    for i, item in enumerate(candidates):
        item["rerank_score"] = score_map.get(i, 0)

    # Items beyond _MAX_CANDIDATES get score -1 (pushed to the end).
    for item in results[_MAX_CANDIDATES:]:
        item["rerank_score"] = -1

    ranked = sorted(results, key=lambda x: x.get("rerank_score", 0), reverse=True)
    return ranked[:top_k] if top_k is not None else ranked
