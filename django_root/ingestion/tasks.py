import logging

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3)
def process_document(self, document_id: int) -> None:
    """Full ingestion pipeline: parse → chunk → embed → index."""
    from apps.documents.models import Document

    document = None
    try:
        document = Document.objects.get(pk=document_id)
        document.status = Document.Status.PROCESSING
        document.save(update_fields=["status"])

        _parse_and_chunk(document)
        _generate_embeddings(document)

        document.status = Document.Status.READY
        document.save(update_fields=["status"])
        logger.info("Document %d processed successfully.", document_id)

    except Document.DoesNotExist:
        logger.error("Document %d not found.", document_id)
    except Exception as exc:
        logger.exception("Error processing document %d.", document_id)
        if document is not None:
            document.status = Document.Status.FAILED
            document.save(update_fields=["status"])
        raise self.retry(exc=exc, countdown=60)


def _parse_and_chunk(document) -> None:
    from apps.documents.models import Chunk
    from ingestion.chunkers.clause import ClauseChunker
    from ingestion.chunkers.paragraph import ParagraphChunker
    from ingestion.parsers.code import CodeParser
    from ingestion.parsers.markdown import MarkdownParser
    from ingestion.parsers.openapi import OpenAPIParser
    from ingestion.parsers.pdf import PDFParser
    from ingestion.parsers.text import PlainTextParser
    from ingestion.parsers.xml_parser import XMLParser

    parsers = {
        "pdf": PDFParser(),
        "markdown": MarkdownParser(),
        "xml": XMLParser(),
        "openapi": OpenAPIParser(),
        "code": CodeParser(),
        "text": PlainTextParser(),
    }

    parser = parsers.get(document.file_type)
    if parser is None:
        logger.warning("No parser available for file type %s.", document.file_type)
        return

    parsed = parser.parse(document.file.path)

    # Chunker selection:
    # • metadata["chunker"] == "clause"  → ClauseChunker (contract texts)
    # • everything else                  → ParagraphChunker
    # ParagraphChunker passes xml_block/function/class chunks through unchanged.
    chunker_key = document.metadata.get("chunker", "paragraph")
    if chunker_key == "clause":
        chunker = ClauseChunker()
    else:
        chunker = ParagraphChunker()

    final_chunks = chunker.chunk(parsed.chunks)

    Chunk.objects.filter(document=document).delete()
    Chunk.objects.bulk_create(
        [
            Chunk(
                document=document,
                content=c.content,
                chunk_type=c.chunk_type,
                position=c.position,
                page_number=c.page_number,
                metadata=c.metadata,
            )
            for c in final_chunks
        ]
    )


def _generate_embeddings(document) -> None:
    from apps.documents.models import Chunk
    from llm.client import get_embedding

    chunks = list(Chunk.objects.filter(document=document, embedding__isnull=True))
    for chunk in chunks:
        chunk.embedding = get_embedding(chunk.content)
        chunk.save(update_fields=["embedding"])
