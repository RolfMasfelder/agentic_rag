from typing import Any

from llm.client import get_embedding
from retrieval.fulltext_search import fulltext_search
from retrieval.vector_search import search_similar_chunks


def hybrid_search(
    query: str,
    limit: int = 10,
    document_ids: list[int] | None = None,
    vector_weight: float = 0.6,
    fulltext_weight: float = 0.4,
) -> list[dict[str, Any]]:
    """
    Combine vector similarity and full-text search using Reciprocal Rank Fusion-style
    score weighting.
    """
    embedding = get_embedding(query)
    vector_results = search_similar_chunks(embedding, limit=limit * 2, document_ids=document_ids)
    text_results = fulltext_search(query, limit=limit * 2, document_ids=document_ids)

    scores: dict[int, dict[str, Any]] = {}

    for r in vector_results:
        cid = r["chunk_id"]
        scores[cid] = {**r, "hybrid_score": r["score"] * vector_weight}

    max_rank = max((r.get("rank", 0) for r in text_results), default=1.0) or 1.0
    for r in text_results:
        cid = r["chunk_id"]
        normalized = r.get("rank", 0) / max_rank
        if cid in scores:
            scores[cid]["hybrid_score"] += normalized * fulltext_weight
        else:
            scores[cid] = {**r, "hybrid_score": normalized * fulltext_weight}

    ranked = sorted(scores.values(), key=lambda x: x["hybrid_score"], reverse=True)
    return ranked[:limit]
