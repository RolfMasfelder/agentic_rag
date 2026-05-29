import hashlib
import logging
from functools import wraps

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
    if request.method == "POST":
        title = request.POST.get("title", "").strip()
        file_type = request.POST.get("file_type", Document.FileType.OTHER)
        chunker = request.POST.get("chunker", "paragraph")
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
            "filetype_choices": Document.FileType.choices,
            "chunker_choices": [
                ("paragraph", "Absätze (Standard)"),
                ("clause", "Klauseln (Verträge/RFC)"),
            ],
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
    if request.method == "POST":
        question = request.POST.get("question", "").strip()
        if question:
            try:
                from agents.orchestrator import run_agent

                result = run_agent(question)
            except Exception as exc:
                logger.exception("Agent query failed.")
                error = str(exc)
        if request.headers.get("HX-Request"):
            return render(
                request,
                "ui/agent/query_result.html",
                {"result": result, "question": question, "error": error},
            )
    return render(
        request,
        "ui/agent/query.html",
        {"result": result, "question": question, "error": error},
    )


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
