"""Management command: re-generate embeddings for all (or selected) READY documents.

Typical use-case: switching the embedding model requires discarding old vectors
and re-computing them with the new model.

Usage::

    # Re-embed every READY document whose chunks have no embedding yet
    python manage.py reembed_documents

    # Force re-embed even if embeddings already exist
    python manage.py reembed_documents --force

    # Re-embed a single document by primary-key
    python manage.py reembed_documents --document-id 42

    # Combine: force-re-embed a single document
    python manage.py reembed_documents --document-id 42 --force
"""

import logging

from django.core.management.base import BaseCommand, CommandError

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Re-generate embeddings for READY documents (e.g. after switching the embed model)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--document-id",
            type=int,
            metavar="ID",
            help="Only re-embed this single document (by primary key).",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            default=False,
            help=(
                "Re-embed chunks that already have an embedding. "
                "Without this flag, only chunks with a NULL embedding are processed."
            ),
        )

    def handle(self, *args, **options):
        from apps.documents.models import Chunk, Document
        from llm.client import get_embedding

        doc_id = options["document_id"]
        force = options["force"]

        qs = Document.objects.filter(status=Document.Status.READY)
        if doc_id is not None:
            qs = qs.filter(pk=doc_id)
            if not qs.exists():
                raise CommandError(f"Document with id={doc_id} not found or not in READY state.")

        documents = list(qs)
        if not documents:
            self.stdout.write(self.style.WARNING("No READY documents found."))
            return

        total_docs = len(documents)
        total_chunks = 0
        total_errors = 0

        for idx, doc in enumerate(documents, start=1):
            self.stdout.write(f"[{idx}/{total_docs}] Document {doc.pk}: {doc.title!r}")

            chunk_qs = Chunk.objects.filter(document=doc)
            if not force:
                chunk_qs = chunk_qs.filter(embedding__isnull=True)

            chunks = list(chunk_qs)
            if not chunks:
                self.stdout.write("  → no chunks to process, skipping.")
                continue

            for chunk in chunks:
                try:
                    chunk.embedding = get_embedding(chunk.content)
                    chunk.save(update_fields=["embedding"])
                    total_chunks += 1
                except Exception as exc:
                    total_errors += 1
                    logger.exception("Failed to embed chunk %d of document %d.", chunk.pk, doc.pk)
                    self.stderr.write(self.style.ERROR(f"  ✗ Chunk {chunk.pk} failed: {exc}"))

            self.stdout.write(self.style.SUCCESS(f"  → embedded {len(chunks)} chunk(s)."))

        self.stdout.write(
            self.style.SUCCESS(
                f"\nDone. {total_chunks} chunk(s) re-embedded across {total_docs} document(s). Errors: {total_errors}."
            )
        )
