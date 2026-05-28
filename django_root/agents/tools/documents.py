from typing import Any


def load_document(document_id: int) -> dict[str, Any]:
    """Load document metadata and chunk overview."""
    from apps.documents.models import Document

    try:
        doc = Document.objects.get(pk=document_id)
    except Document.DoesNotExist:
        return {"error": f"Document {document_id} not found"}
    return {
        "id": doc.id,
        "title": doc.title,
        "file_type": doc.file_type,
        "status": doc.status,
        "metadata": doc.metadata,
        "chunk_count": doc.chunks.count(),
    }


def find_related_documents(document_id: int) -> list[dict[str, Any]]:
    """Return documents related to the given document (outgoing relations)."""
    from apps.documents.models import DocumentRelation

    relations = DocumentRelation.objects.filter(source_document_id=document_id).select_related("target_document")
    return [
        {
            "document_id": r.target_document_id,
            "title": r.target_document.title,
            "relation_type": r.relation_type,
            "confidence": r.confidence,
        }
        for r in relations
    ]


def list_document_relations(document_id: int) -> list[dict[str, Any]]:
    """List all relations for a document (both directions)."""
    from apps.documents.models import DocumentRelation

    qs = (
        DocumentRelation.objects.filter(source_document_id=document_id)
        | DocumentRelation.objects.filter(target_document_id=document_id)
    ).select_related("source_document", "target_document")
    return [
        {
            "source_id": r.source_document_id,
            "source_title": r.source_document.title,
            "target_id": r.target_document_id,
            "target_title": r.target_document.title,
            "relation_type": r.relation_type,
            "confidence": r.confidence,
            "created_by": r.created_by,
        }
        for r in qs
    ]


def summarize_document(document_id: int) -> str:
    """Generate or retrieve a cached summary for a document."""
    from apps.documents.models import AnalysisResult, Document

    try:
        doc = Document.objects.get(pk=document_id)
    except Document.DoesNotExist:
        return f"Document {document_id} not found"

    existing = AnalysisResult.objects.filter(document=doc, result_type="summary").first()
    if existing:
        return existing.content.get("text", "")

    from llm.client import chat

    chunks = doc.chunks.order_by("position")[:10]
    context = "\n\n".join(c.content for c in chunks)
    summary = chat(f'Fasse das folgende Dokument "{doc.title}" in 3-5 Sätzen zusammen:\n\n{context}')

    AnalysisResult.objects.create(
        document=doc,
        result_type="summary",
        content={"text": summary},
    )
    return summary
