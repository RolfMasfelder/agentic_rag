from typing import Any


def filter_by_metadata(
    filters: dict[str, Any],
    limit: int = 50,
) -> list[dict[str, Any]]:
    """Filter documents by metadata key-value pairs (JSON field traversal)."""
    from apps.documents.models import Document

    qs = Document.objects.filter(status='ready')
    for key, value in filters.items():
        qs = qs.filter(**{f'metadata__{key}': value})

    return [
        {
            'document_id': doc.id,
            'title': doc.title,
            'file_type': doc.file_type,
            'metadata': doc.metadata,
        }
        for doc in qs[:limit]
    ]
