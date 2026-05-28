"""End-to-end integration tests – require PostgreSQL + a running Ollama instance.

Run inside the Docker container (where both services are reachable):

    docker compose exec web python -m pytest django_root/tests/test_e2e.py -v -m e2e

Tests are automatically skipped (at collection time) when either service is unreachable.
"""

import hashlib
import socket

import pytest
from django.conf import settings
from django.core.files.uploadedfile import SimpleUploadedFile


def _db_reachable() -> bool:
    try:
        host = settings.DATABASES["default"].get("HOST", "localhost")
        port = int(settings.DATABASES["default"].get("PORT", 5432))
        s = socket.create_connection((host, port), timeout=2)
        s.close()
        return True
    except OSError:
        return False


def _ollama_reachable() -> bool:
    url = getattr(settings, "OLLAMA_BASE_URL", "")
    if not url:
        return False
    host_port = url.replace("http://", "").replace("https://", "").split("/")[0]
    host, _, port_str = host_port.partition(":")
    port = int(port_str) if port_str else 11434
    try:
        s = socket.create_connection((host, port), timeout=2)
        s.close()
        return True
    except OSError:
        return False


pytestmark = [
    pytest.mark.e2e,
    pytest.mark.skipif(not _db_reachable(), reason="PostgreSQL not reachable (run inside Docker)"),
    pytest.mark.skipif(not _ollama_reachable(), reason="Ollama not reachable"),
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _create_document(user, title: str, raw: bytes, file_type: str, filename: str):
    """Create a Document row with a real file stored under the active MEDIA_ROOT."""
    from apps.documents.models import Document

    f = SimpleUploadedFile(filename, raw)
    return Document.objects.create(
        title=title,
        file=f,
        file_type=file_type,
        content_hash=hashlib.sha256(raw).hexdigest(),
        status=Document.Status.PENDING,
        created_by=user,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_e2e_text_ingest_and_search(user):
    """Plain-text: parse → chunk → embed → hybrid_search returns relevant chunks."""
    from apps.documents.models import Chunk, Document
    from ingestion.tasks import _generate_embeddings, _parse_and_chunk
    from retrieval.hybrid import hybrid_search

    content = (
        "The key words MUST, MUST NOT, and REQUIRED are defined in RFC 2119.\n\n"
        "MUST means that the definition is an absolute requirement of the specification.\n\n"
        "SHOULD means that there may exist valid reasons to ignore the recommendation."
    )
    raw = content.encode()

    doc = _create_document(user, "RFC 2119 Keywords", raw, Document.FileType.TEXT, "rfc2119.txt")
    _parse_and_chunk(doc)
    _generate_embeddings(doc)

    chunks = list(Chunk.objects.filter(document=doc))
    assert len(chunks) >= 2, f"Expected ≥2 chunks, got {len(chunks)}"
    assert all(c.embedding is not None for c in chunks), "All chunks must have embeddings"

    results = hybrid_search("what does MUST mean", limit=5, document_ids=[doc.pk])
    assert len(results) > 0, "hybrid_search returned no results"
    top_content = results[0]["content"]
    assert "MUST" in top_content or "requirement" in top_content.lower()


@pytest.mark.django_db
def test_e2e_markdown_ingest(user):
    """Markdown: sections produce markdown_section chunks with embeddings."""
    from apps.documents.models import Chunk, Document
    from ingestion.tasks import _generate_embeddings, _parse_and_chunk

    content = (
        "# Installation\n\nRun `pip install rich` to install the library.\n\n"
        "# Usage\n\nImport with `from rich import print` and use it directly.\n\n"
        "# Configuration\n\nSet `RICH_TRACEBACK_SHOW_LOCALS=1` to enable local variable display.\n"
    )
    raw = content.encode()

    doc = _create_document(user, "Rich Library Docs", raw, Document.FileType.MARKDOWN, "rich.md")
    _parse_and_chunk(doc)
    _generate_embeddings(doc)

    chunks = list(Chunk.objects.filter(document=doc))
    chunk_types = {c.chunk_type for c in chunks}
    assert "markdown_section" in chunk_types, f"Expected markdown_section chunks, got: {chunk_types}"
    assert all(c.embedding is not None for c in chunks), "All chunks must have embeddings"


@pytest.mark.django_db
def test_e2e_xml_ingest(user):
    """XML: child elements produce xml_block chunks with embeddings."""
    from apps.documents.models import Chunk, Document
    from ingestion.tasks import _generate_embeddings, _parse_and_chunk

    content = (
        '<?xml version="1.0"?>\n'
        "<config>\n"
        '  <database host="localhost" port="5432" name="app_db"/>\n'
        '  <cache backend="redis" timeout="300"/>\n'
        '  <logging level="INFO" format="json"/>\n'
        "</config>"
    )
    raw = content.encode()

    doc = _create_document(user, "App Config XML", raw, Document.FileType.XML, "config.xml")
    _parse_and_chunk(doc)
    _generate_embeddings(doc)

    chunks = list(Chunk.objects.filter(document=doc))
    assert len(chunks) >= 3, f"Expected ≥3 xml_block chunks, got {len(chunks)}"
    assert all(c.chunk_type == "xml_block" for c in chunks), "All chunks should be xml_block"
    assert all(c.embedding is not None for c in chunks), "All chunks must have embeddings"


@pytest.mark.django_db
def test_e2e_agent_answers_from_indexed_document(user):
    """Full pipeline: ingest a text doc, then ask the agent a question about it."""
    from agents.orchestrator import run_agent
    from apps.documents.models import Document
    from ingestion.tasks import _generate_embeddings, _parse_and_chunk

    content = (
        "Reciprocal Rank Fusion (RRF) is a method for combining ranked lists from multiple retrieval systems.\n\n"
        "It assigns each item a score of 1 / (k + rank), where k is typically set to 60.\n\n"
        "RRF requires no score normalization and works well in hybrid search pipelines."
    )
    raw = content.encode()

    doc = _create_document(user, "RRF Explainer", raw, Document.FileType.TEXT, "rrf.txt")
    _parse_and_chunk(doc)
    _generate_embeddings(doc)

    result = run_agent("What is Reciprocal Rank Fusion and how does it work?", max_iterations=4)

    assert "answer" in result
    assert len(result["answer"]) > 10
    answer_lower = result["answer"].lower()
    assert any(kw in answer_lower for kw in ["rrf", "rank", "fusion", "score", "60", "1 /"]), (
        f"Answer does not mention expected concepts: {result['answer']}"
    )
