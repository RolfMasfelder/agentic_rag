from typing import Any

from llm.client import get_embedding
from retrieval.hybrid import hybrid_search
from retrieval.vector_search import search_similar_chunks as _vector_search


def search_documents(query: str, limit: int = 10) -> list[dict[str, Any]]:
    """Search for document chunks relevant to the query using hybrid retrieval."""
    return hybrid_search(query, limit=limit)


def search_similar_chunks(
    query: str,
    document_id: int | None = None,
    limit: int = 10,
) -> list[dict[str, Any]]:
    """Find chunks semantically similar to the query."""
    embedding = get_embedding(query)
    doc_ids = [document_id] if document_id else None
    return _vector_search(embedding, limit=limit, document_ids=doc_ids)


def search_by_metadata(filters: dict[str, Any], limit: int = 50) -> list[dict[str, Any]]:
    """Filter documents by metadata attributes."""
    from retrieval.metadata_filter import filter_by_metadata

    return filter_by_metadata(filters, limit=limit)
