import logging
from typing import Any

from pgvector.django import CosineDistance

logger = logging.getLogger(__name__)


def search_similar_chunks(
    query_embedding: list[float],
    limit: int = 10,
    document_ids: list[int] | None = None,
    min_score: float = 0.7,
) -> list[dict[str, Any]]:
    """Return chunks most similar to the query embedding (cosine similarity)."""
    from apps.documents.models import Chunk

    qs = Chunk.objects.exclude(embedding__isnull=True).annotate(
        distance=CosineDistance('embedding', query_embedding)
    )
    if document_ids:
        qs = qs.filter(document_id__in=document_ids)

    qs = qs.filter(distance__lte=1 - min_score).order_by('distance')[:limit]

    return [
        {
            'chunk_id': chunk.id,
            'document_id': chunk.document_id,
            'content': chunk.content,
            'chunk_type': chunk.chunk_type,
            'score': round(1 - chunk.distance, 4),
            'metadata': chunk.metadata,
        }
        for chunk in qs
    ]
