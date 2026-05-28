from collections import deque
from typing import Any


def graph_traversal(
    document_id: int,
    max_depth: int = 2,
    relation_types: list[str] | None = None,
) -> list[dict[str, Any]]:
    """Breadth-first traversal of the document relation graph.

    Starting from *document_id*, follow ``DocumentRelation`` edges in both
    directions up to *max_depth* hops.  Optionally restrict to specific
    *relation_types*.

    Returns a list of reachable documents with the shortest path length and
    the relation type of the last edge, sorted by depth then document ID.
    Duplicate document IDs are never returned twice.
    """
    from apps.documents.models import DocumentRelation

    # BFS state: (current_doc_id, depth, via_relation_type)
    queue: deque[tuple[int, int, str]] = deque([(document_id, 0, "")])
    visited: dict[int, dict[str, Any]] = {}

    while queue:
        current_id, depth, via = queue.popleft()

        if current_id in visited:
            continue
        if current_id != document_id:
            visited[current_id] = {"document_id": current_id, "depth": depth, "via": via}

        if depth >= max_depth:
            continue

        # Outgoing relations (source → target)
        qs_out = DocumentRelation.objects.filter(source_document_id=current_id).select_related("target_document")
        if relation_types:
            qs_out = qs_out.filter(relation_type__in=relation_types)

        for rel in qs_out:
            target_id = rel.target_document_id
            if target_id not in visited:
                queue.append((target_id, depth + 1, rel.relation_type))

        # Incoming relations (target → source, reversed)
        qs_in = DocumentRelation.objects.filter(target_document_id=current_id).select_related("source_document")
        if relation_types:
            qs_in = qs_in.filter(relation_type__in=relation_types)

        for rel in qs_in:
            source_id = rel.source_document_id
            if source_id not in visited and source_id != document_id:
                queue.append((source_id, depth + 1, rel.relation_type))

    # Enrich with document metadata
    from apps.documents.models import Document

    doc_map: dict[int, Document] = {
        doc.id: doc for doc in Document.objects.filter(pk__in=visited.keys()).only("id", "title", "file_type", "status")
    }

    results: list[dict[str, Any]] = []
    for doc_id, info in sorted(visited.items(), key=lambda x: (x[1]["depth"], x[0])):
        doc = doc_map.get(doc_id)
        results.append(
            {
                "document_id": doc_id,
                "title": doc.title if doc else None,
                "file_type": doc.file_type if doc else None,
                "depth": info["depth"],
                "via_relation": info["via"],
            }
        )

    return results
