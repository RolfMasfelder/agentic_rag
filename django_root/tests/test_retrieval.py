"""Unit tests for retrieval functions (mocked – no DB required)."""

from unittest.mock import patch

# ---------------------------------------------------------------------------
# hybrid_search
# ---------------------------------------------------------------------------


def _vector_results():
    return [
        {
            "chunk_id": 1,
            "document_id": 10,
            "content": "vector result A",
            "chunk_type": "paragraph",
            "score": 0.9,
            "metadata": {},
        },
        {
            "chunk_id": 2,
            "document_id": 10,
            "content": "vector result B",
            "chunk_type": "paragraph",
            "score": 0.8,
            "metadata": {},
        },
    ]


def _text_results():
    return [
        {
            "chunk_id": 2,
            "document_id": 10,
            "content": "vector result B",
            "chunk_type": "paragraph",
            "rank": 1.0,
            "metadata": {},
        },
        {
            "chunk_id": 3,
            "document_id": 11,
            "content": "fulltext only result",
            "chunk_type": "paragraph",
            "rank": 0.5,
            "metadata": {},
        },
    ]


def test_hybrid_search_merges_results():
    from retrieval.hybrid import hybrid_search

    with (
        patch("retrieval.hybrid.get_embedding", return_value=[0.1] * 768),
        patch("retrieval.hybrid.search_similar_chunks", return_value=_vector_results()),
        patch("retrieval.hybrid.fulltext_search", return_value=_text_results()),
    ):
        results = hybrid_search("test query", limit=10)

    # chunk_id 2 appears in both – should be present exactly once
    ids = [r["chunk_id"] for r in results]
    assert ids.count(2) == 1
    # All three unique chunk_ids should appear
    assert set(ids) == {1, 2, 3}


def test_hybrid_search_respects_limit():
    from retrieval.hybrid import hybrid_search

    vector = [
        {"chunk_id": i, "document_id": 1, "content": f"v{i}", "chunk_type": "paragraph", "score": 0.9, "metadata": {}}
        for i in range(10)
    ]
    fulltext = [
        {
            "chunk_id": i + 10,
            "document_id": 1,
            "content": f"f{i}",
            "chunk_type": "paragraph",
            "rank": 0.5,
            "metadata": {},
        }
        for i in range(10)
    ]

    with (
        patch("retrieval.hybrid.get_embedding", return_value=[0.1] * 768),
        patch("retrieval.hybrid.search_similar_chunks", return_value=vector),
        patch("retrieval.hybrid.fulltext_search", return_value=fulltext),
    ):
        results = hybrid_search("test", limit=5)

    assert len(results) <= 5


def test_hybrid_search_empty_inputs():
    from retrieval.hybrid import hybrid_search

    with (
        patch("retrieval.hybrid.get_embedding", return_value=[0.1] * 768),
        patch("retrieval.hybrid.search_similar_chunks", return_value=[]),
        patch("retrieval.hybrid.fulltext_search", return_value=[]),
    ):
        results = hybrid_search("test query")

    assert results == []


def test_hybrid_search_chunk_in_both_has_combined_score():
    from retrieval.hybrid import hybrid_search

    vector = [
        {"chunk_id": 1, "document_id": 1, "content": "shared", "chunk_type": "paragraph", "score": 0.6, "metadata": {}},
    ]
    fulltext = [
        {"chunk_id": 1, "document_id": 1, "content": "shared", "chunk_type": "paragraph", "rank": 1.0, "metadata": {}},
    ]

    with (
        patch("retrieval.hybrid.get_embedding", return_value=[0.1] * 768),
        patch("retrieval.hybrid.search_similar_chunks", return_value=vector),
        patch("retrieval.hybrid.fulltext_search", return_value=fulltext),
    ):
        results = hybrid_search("test", limit=10, vector_weight=0.6, fulltext_weight=0.4)

    assert len(results) == 1
    # Score = 0.6*0.6 + 0.4*1.0 = 0.36 + 0.40 = 0.76
    assert abs(results[0]["hybrid_score"] - 0.76) < 0.01


# ---------------------------------------------------------------------------
# query_expansion
# ---------------------------------------------------------------------------


def test_query_expansion_returns_expanded_string():
    from retrieval.query_expansion import expand_query

    with patch("llm.client.chat", return_value="machine learning neural networks deep learning"):
        result = expand_query("ML")

    assert isinstance(result, str)
    assert len(result) > 0


def test_query_expansion_fallback_on_error():
    from retrieval.query_expansion import expand_query

    with patch("llm.client.chat", side_effect=RuntimeError("LLM down")):
        result = expand_query("original query")

    assert result == "original query"


# ---------------------------------------------------------------------------
# reranker
# ---------------------------------------------------------------------------


def test_reranker_returns_ordered_results():
    from retrieval.reranker import rerank

    candidates = [
        {"chunk_id": 1, "content": "low relevance text", "score": 0.5},
        {"chunk_id": 2, "content": "highly relevant text", "score": 0.4},
    ]
    llm_response = '[{"idx": 0, "score": 3}, {"idx": 1, "score": 9}]'

    with patch("llm.client.chat", return_value=llm_response):
        results = rerank("test query", candidates, top_k=2)

    # chunk_id 2 (idx 1, score 9) should come first after reranking
    assert results[0]["chunk_id"] == 2
    assert "rerank_score" in results[0]


def test_reranker_fallback_on_llm_error():
    from retrieval.reranker import rerank

    candidates = [
        {"chunk_id": 1, "content": "text A", "score": 0.9},
        {"chunk_id": 2, "content": "text B", "score": 0.8},
    ]

    with patch("llm.client.chat", side_effect=RuntimeError("LLM error")):
        results = rerank("query", candidates)

    # Falls back to original order
    assert [r["chunk_id"] for r in results] == [1, 2]
