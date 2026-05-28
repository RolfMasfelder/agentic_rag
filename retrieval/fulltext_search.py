from typing import Any

from django.contrib.postgres.search import SearchQuery, SearchRank, SearchVector


def fulltext_search(
    query: str,
    limit: int = 10,
    document_ids: list[int] | None = None,
) -> list[dict[str, Any]]:
    """PostgreSQL full-text search over chunk content (German language config)."""
    from apps.documents.models import Chunk

    search_query = SearchQuery(query, config="german")
    qs = (
        Chunk.objects.annotate(search_vector=SearchVector("content", config="german"))
        .annotate(rank=SearchRank("search_vector", search_query))
        .filter(search_vector=search_query)
    )

    if document_ids:
        qs = qs.filter(document_id__in=document_ids)

    return [
        {
            "chunk_id": chunk.id,
            "document_id": chunk.document_id,
            "content": chunk.content,
            "chunk_type": chunk.chunk_type,
            "rank": float(chunk.rank),
            "metadata": chunk.metadata,
        }
        for chunk in qs.order_by("-rank")[:limit]
    ]
