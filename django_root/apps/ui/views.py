import hashlib
import logging
from datetime import datetime
from functools import wraps
from pathlib import Path

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render

from apps.documents.models import Chunk, Document

logger = logging.getLogger(__name__)


def analyst_required(view_func):
    """Restrict view to ANALYST or ADMIN role; redirect unauthenticated users to login."""

    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect(f"{settings.LOGIN_URL}?next={request.path}")
        if request.user.role not in ("admin", "analyst"):
            return render(request, "ui/403.html", status=403)
        return view_func(request, *args, **kwargs)

    return _wrapped


def _user_documents(user):
    """Documents visible to the given user (all for admin, own for others)."""
    if user.role == "admin":
        return Document.objects.all()
    return Document.objects.filter(created_by=user)


_EXT_TO_FILE_TYPE: dict[str, str] = {
    # PDF
    ".pdf": "pdf",
    # Markdown / reStructuredText
    ".md": "markdown",
    ".rst": "markdown",
    # XML family
    ".xml": "xml",
    ".xsd": "xml",
    ".xsl": "xml",
    ".xslt": "xml",
    ".atom": "xml",
    ".rss": "xml",
    ".rdf": "xml",
    ".svg": "xml",
    ".kml": "xml",
    ".gpx": "xml",
    ".wsdl": "xml",
    ".pom": "xml",
    # OpenAPI / structured data
    ".yaml": "openapi",
    ".yml": "openapi",
    ".json": "openapi",
    # Code
    ".py": "code",
    ".js": "code",
    ".ts": "code",
    ".java": "code",
    ".c": "code",
    ".cpp": "code",
    ".h": "code",
    ".hpp": "code",
    ".go": "code",
    ".rs": "code",
    ".rb": "code",
    ".cs": "code",
    ".php": "code",
    ".kt": "code",
    ".swift": "code",
    ".sh": "code",
    ".bash": "code",
    # Plain text
    ".txt": "text",
    ".text": "text",
    ".csv": "text",
    ".tsv": "text",
    ".html": "text",
    ".htm": "text",
    ".ini": "text",
    ".toml": "text",
    ".cfg": "text",
    ".conf": "text",
}

# Magic-byte signatures tried when extension is unknown.
# Each entry: (prefix_bytes, file_type)
_MAGIC_SIGNATURES: list[tuple[bytes, str]] = [
    (b"%PDF-", "pdf"),
    (b"<?xml", "xml"),
    (b"<feed", "xml"),  # Atom without XML declaration
    (b"<rss", "xml"),
    (b"<svg", "xml"),
    (b"<opml", "xml"),
]


def _sniff_content_type(head: bytes) -> str:
    """Return a file_type string inferred from the first bytes of content."""
    stripped = head.lstrip()
    for signature, file_type in _MAGIC_SIGNATURES:
        if stripped.startswith(signature):
            return file_type
    # Try UTF-8 text patterns
    try:
        text = stripped[:128].decode("utf-8", errors="ignore").lstrip()
    except Exception:
        return "other"
    if text.startswith("openapi:") or text.startswith("swagger:"):
        return "openapi"
    if text.startswith("{") or text.startswith("["):
        if "openapi" in text or "swagger" in text:
            return "openapi"
    return "other"


def _auto_detect_file_type(filename: str, head: bytes = b"") -> str:
    """Detect file type from extension; fall back to magic-byte sniffing for unknowns."""
    detected = _EXT_TO_FILE_TYPE.get(Path(filename).suffix.lower(), "other")
    if detected == "other" and head:
        return _sniff_content_type(head)
    return detected


# ── Dashboard ─────────────────────────────────────────────────────────────────


@login_required
def dashboard(request):
    return render(request, "ui/dashboard.html")


@login_required
def dashboard_stats(request):
    qs = _user_documents(request.user)
    stats = {
        "total": qs.count(),
        "ready": qs.filter(status=Document.Status.READY).count(),
        "processing": qs.filter(status=Document.Status.PROCESSING).count(),
        "pending": qs.filter(status=Document.Status.PENDING).count(),
        "failed": qs.filter(status=Document.Status.FAILED).count(),
    }
    total_chunks = Chunk.objects.filter(document__in=qs).count()
    embedded = Chunk.objects.filter(document__in=qs, embedding__isnull=False).count()
    stats["total_chunks"] = total_chunks
    stats["embedded_chunks"] = embedded
    stats["embed_pct"] = round(embedded / total_chunks * 100) if total_chunks else 0
    recent = qs.select_related("created_by").order_by("-created_at")[:8]
    return render(request, "ui/partials/dashboard_stats.html", {"stats": stats, "recent": recent})


@login_required
def dashboard_tasks(request):
    active_tasks = None
    try:
        from celery import current_app

        inspect = current_app.control.inspect(timeout=1.5)
        active = inspect.active() or {}
        active_tasks = [task for tasks in active.values() for task in tasks]
    except Exception:
        pass  # broker unavailable or timeout
    return render(request, "ui/partials/dashboard_tasks.html", {"active_tasks": active_tasks})


# ── Documents ─────────────────────────────────────────────────────────────────


@login_required
def document_list(request):
    qs = _user_documents(request.user).select_related("created_by")
    status_filter = request.GET.get("status", "")
    filetype_filter = request.GET.get("file_type", "")
    if status_filter:
        qs = qs.filter(status=status_filter)
    if filetype_filter:
        qs = qs.filter(file_type=filetype_filter)
    paginator = Paginator(qs, 20)
    page_obj = paginator.get_page(request.GET.get("page"))
    return render(
        request,
        "ui/documents/list.html",
        {
            "page_obj": page_obj,
            "status_filter": status_filter,
            "filetype_filter": filetype_filter,
            "status_choices": Document.Status.choices,
            "filetype_choices": Document.FileType.choices,
        },
    )


@analyst_required
def document_upload(request):
    filetype_choices = Document.FileType.choices
    chunker_choices = [
        ("paragraph", "Absätze (Standard)"),
        ("clause", "Klauseln (Verträge/RFC)"),
    ]

    if request.method == "POST":
        mode = request.POST.get("mode", "single")
        chunker = request.POST.get("chunker", "paragraph")
        file_type = request.POST.get("file_type", Document.FileType.OTHER)

        if mode == "batch":
            uploaded_files = request.FILES.getlist("files")
            if not uploaded_files:
                messages.error(request, "Bitte mindestens eine Datei auswählen.")
            else:
                from ingestion.tasks import process_document

                queued, skipped = 0, 0
                for uploaded_file in uploaded_files:
                    content = uploaded_file.read()
                    content_hash = hashlib.sha256(content).hexdigest()
                    uploaded_file.seek(0)
                    if Document.objects.filter(content_hash=content_hash).exists():
                        skipped += 1
                        continue
                    detected_type = _auto_detect_file_type(uploaded_file.name, content[:64])
                    title = Path(uploaded_file.name).stem.replace("_", " ").replace("-", " ")
                    doc = Document.objects.create(
                        title=title,
                        file=uploaded_file,
                        file_type=detected_type,
                        content_hash=content_hash,
                        metadata={"chunker": chunker} if chunker != "paragraph" else {},
                        created_by=request.user,
                    )
                    process_document.delay(doc.id)
                    queued += 1

                parts = []
                if queued:
                    parts.append(f"{queued} Dokument{'e' if queued != 1 else ''} in die Warteschlange eingereiht")
                if skipped:
                    parts.append(f"{skipped} bereits vorhanden (übersprungen)")
                messages.success(request, ". ".join(parts) + ".")
                return redirect("ui:document_list")

        else:  # single
            title = request.POST.get("title", "").strip()
            uploaded_file = request.FILES.get("file")
            if not title or not uploaded_file:
                messages.error(request, "Titel und Datei sind Pflichtfelder.")
            else:
                content = uploaded_file.read()
                content_hash = hashlib.sha256(content).hexdigest()
                uploaded_file.seek(0)
                existing = Document.objects.filter(content_hash=content_hash).first()
                if existing:
                    messages.warning(request, f'Dieses Dokument existiert bereits: „{existing.title}"')
                    return redirect("ui:document_detail", pk=existing.pk)
                doc = Document.objects.create(
                    title=title,
                    file=uploaded_file,
                    file_type=file_type,
                    content_hash=content_hash,
                    metadata={"chunker": chunker} if chunker != "paragraph" else {},
                    created_by=request.user,
                )
                from ingestion.tasks import process_document

                process_document.delay(doc.id)
                messages.success(request, f'„{doc.title}" wird verarbeitet.')
                return redirect("ui:document_detail", pk=doc.pk)

    return render(
        request,
        "ui/documents/upload.html",
        {
            "filetype_choices": filetype_choices,
            "chunker_choices": chunker_choices,
        },
    )


@login_required
def document_detail(request, pk):
    doc = get_object_or_404(_user_documents(request.user), pk=pk)
    total_chunks = doc.chunks.count()
    embedded = doc.chunks.filter(embedding__isnull=False).count()
    embedded_ids = set(doc.chunks.filter(embedding__isnull=False).values_list("id", flat=True))
    return render(
        request,
        "ui/documents/detail.html",
        {
            "doc": doc,
            "chunks": doc.chunks.order_by("position")[:50],
            "total_chunks": total_chunks,
            "embedded_chunks": embedded,
            "embedded_ids": embedded_ids,
            "embed_pct": round(embedded / total_chunks * 100) if total_chunks else 0,
        },
    )


@login_required
def document_status(request, pk):
    """HTMX partial – returns the polling status badge for a single document."""
    doc = get_object_or_404(_user_documents(request.user), pk=pk)
    return render(request, "ui/partials/document_status.html", {"doc": doc})


@analyst_required
def document_delete(request, pk):
    doc = get_object_or_404(_user_documents(request.user), pk=pk)
    if request.method == "POST":
        title = doc.title
        doc.delete()
        messages.success(request, f'„{title}" wurde gelöscht.')
        return redirect("ui:document_list")
    return render(request, "ui/documents/confirm_delete.html", {"doc": doc})


# ── Agent ─────────────────────────────────────────────────────────────────────


@login_required
def agent_query(request):
    result = None
    question = ""
    error = None
    history: list[dict] = request.session.get("query_history", [])
    if request.method == "POST":
        question = request.POST.get("question", "").strip()
        if question:
            try:
                from agents.orchestrator import run_agent

                result = run_agent(question)
            except Exception as exc:
                logger.exception("Agent query failed.")
                error = str(exc)
        if result and not error:
            answer_excerpt = (result.get("answer") or "")[:120]
            history = [
                {
                    "question": question,
                    "answer_excerpt": answer_excerpt,
                    "ts": datetime.now().strftime("%H:%M"),
                }
            ] + history[:9]
            request.session["query_history"] = history
        if request.headers.get("HX-Request"):
            return render(
                request,
                "ui/agent/query_result.html",
                {"result": result, "question": question, "error": error},
            )
    return render(
        request,
        "ui/agent/query.html",
        {"result": result, "question": question, "error": error, "query_history": history},
    )


@login_required
def agent_clear_history(request):
    """POST-only: clear the query history stored in the session."""
    if request.method == "POST":
        request.session.pop("query_history", None)
    return redirect("ui:agent_query")


# ── Search ────────────────────────────────────────────────────────────────────


@login_required
def search(request):
    q = request.GET.get("q", "").strip()
    mode = request.GET.get("mode", "hybrid")
    results = []
    error = None
    if q:
        try:
            if mode == "vector":
                from llm.client import get_embedding
                from retrieval.vector_search import search_similar_chunks

                results = search_similar_chunks(get_embedding(q), limit=15)
            elif mode == "fulltext":
                from retrieval.fulltext_search import fulltext_search

                results = fulltext_search(q, limit=15)
            else:
                from retrieval.hybrid import hybrid_search

                results = hybrid_search(q, limit=15)
            if results:
                doc_ids = {r["document_id"] for r in results}
                titles = {d.id: d.title for d in Document.objects.filter(id__in=doc_ids).only("id", "title")}
                for r in results:
                    r["document_title"] = titles.get(r["document_id"], "–")
                    r["display_score"] = round(r.get("hybrid_score", r.get("score", r.get("rank", 0))), 3)
        except Exception as exc:
            logger.exception("Search failed.")
            error = str(exc)
    ctx = {"q": q, "mode": mode, "results": results, "error": error}
    if request.headers.get("HX-Request"):
        return render(request, "ui/search/results.html", ctx)
    return render(request, "ui/search/index.html", ctx)


# ── Admin actions ──────────────────────────────────────────────────────────────


@login_required
def admin_reembed(request):
    """POST-only: queue a Celery task to generate missing embeddings (admin only)."""
    if request.user.role != "admin":
        return render(request, "ui/403.html", status=403)
    if request.method == "POST":
        from ingestion.tasks import reembed_documents

        reembed_documents.delay()
        messages.success(request, "Re-Embedding-Task wurde gestartet.")
    return redirect("ui:dashboard")
