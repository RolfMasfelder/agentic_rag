from typing import Any


def _document_embedding(document_id: int) -> list[float] | None:
    """Compute a document-level embedding by averaging its chunk embeddings."""
    from apps.documents.models import Chunk

    chunks = list(
        Chunk.objects.filter(document_id=document_id)
        .exclude(embedding__isnull=True)
        .values_list("embedding", flat=True)
    )
    if not chunks:
        return None

    dim = len(chunks[0])
    avg = [0.0] * dim
    for emb in chunks:
        for i, v in enumerate(emb):
            avg[i] += v
    n = len(chunks)
    return [v / n for v in avg]


def find_similar_documents(
    document_id: int,
    limit: int = 5,
    min_score: float = 0.5,
) -> list[dict[str, Any]]:
    """Find documents semantically similar to *document_id*.

    Computes a document embedding by averaging all chunk embeddings, then
    searches all other documents' chunks via cosine similarity.  Results are
    grouped by document and the maximum per-chunk score is used as the
    document score.

    Returns a list of ``{document_id, title, file_type, score}`` dicts sorted
    by descending score.
    """
    from pgvector.django import CosineDistance

    from apps.documents.models import Chunk, Document

    doc_emb = _document_embedding(document_id)
    if doc_emb is None:
        return []

    qs = (
        Chunk.objects.exclude(embedding__isnull=True)
        .exclude(document_id=document_id)
        .annotate(distance=CosineDistance("embedding", doc_emb))
        .filter(distance__lte=1 - min_score)
        .order_by("distance")
        .values("document_id", "distance")
    )

    # Keep best (lowest distance) score per document.
    best: dict[int, float] = {}
    for row in qs:
        did = row["document_id"]
        score = round(1 - row["distance"], 4)
        if did not in best or score > best[did]:
            best[did] = score

    # Sort and take top `limit`.
    ranked = sorted(best.items(), key=lambda x: x[1], reverse=True)[:limit]

    doc_map = {
        doc.id: doc for doc in Document.objects.filter(pk__in=[d for d, _ in ranked]).only("id", "title", "file_type")
    }

    return [
        {
            "document_id": doc_id,
            "title": doc_map[doc_id].title if doc_id in doc_map else None,
            "file_type": doc_map[doc_id].file_type if doc_id in doc_map else None,
            "score": score,
        }
        for doc_id, score in ranked
    ]
