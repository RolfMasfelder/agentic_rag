"""UI view tests (requires DB; no Ollama needed).

Run inside Docker:
    docker compose exec web python -m pytest django_root/tests/test_ui_views.py -v
"""

import hashlib

import pytest
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client

User = get_user_model()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def analyst_user(db):
    return User.objects.create_user(
        username="ui_analyst",
        password="pass1234",
        email="analyst@example.com",
        role="analyst",
    )


@pytest.fixture
def admin_user(db):
    return User.objects.create_user(
        username="ui_admin",
        password="pass1234",
        email="admin@example.com",
        role="admin",
    )


@pytest.fixture
def viewer_user(db):
    return User.objects.create_user(
        username="ui_viewer",
        password="pass1234",
        email="viewer@example.com",
        role="viewer",
    )


@pytest.fixture
def analyst_client(analyst_user) -> Client:
    c = Client()
    c.force_login(analyst_user)
    return c


@pytest.fixture
def admin_client(admin_user) -> Client:
    c = Client()
    c.force_login(admin_user)
    return c


@pytest.fixture
def viewer_client(viewer_user) -> Client:
    c = Client()
    c.force_login(viewer_user)
    return c


def _make_doc(user, title="Test Doc", content=b"test content"):
    from apps.documents.models import Document

    f = SimpleUploadedFile("test.txt", content, content_type="text/plain")
    return Document.objects.create(
        title=title,
        file=f,
        file_type=Document.FileType.TEXT,
        content_hash=hashlib.sha256(content).hexdigest(),
        status=Document.Status.READY,
        created_by=user,
    )


# ---------------------------------------------------------------------------
# Auth: unauthenticated redirect
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_dashboard_requires_login():
    c = Client()
    response = c.get("/ui/")
    assert response.status_code == 302
    assert "/ui/login/" in response["Location"]


@pytest.mark.django_db
def test_document_list_requires_login():
    c = Client()
    response = c.get("/ui/documents/")
    assert response.status_code == 302


@pytest.mark.django_db
def test_agent_query_requires_login():
    c = Client()
    response = c.get("/ui/agent/")
    assert response.status_code == 302


@pytest.mark.django_db
def test_search_requires_login():
    c = Client()
    response = c.get("/ui/search/")
    assert response.status_code == 302


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_dashboard_returns_200(analyst_client):
    response = analyst_client.get("/ui/")
    assert response.status_code == 200


@pytest.mark.django_db
def test_dashboard_stats_partial(analyst_client):
    response = analyst_client.get("/ui/partials/stats/")
    assert response.status_code == 200


@pytest.mark.django_db
def test_dashboard_tasks_partial(analyst_client):
    response = analyst_client.get("/ui/partials/tasks/")
    assert response.status_code == 200


# ---------------------------------------------------------------------------
# Document list
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_document_list_empty(analyst_client):
    response = analyst_client.get("/ui/documents/")
    assert response.status_code == 200


@pytest.mark.django_db
def test_document_list_shows_own_docs(analyst_client, analyst_user):
    _make_doc(analyst_user, title="My Doc")
    response = analyst_client.get("/ui/documents/")
    assert response.status_code == 200
    assert b"My Doc" in response.content


@pytest.mark.django_db
def test_document_list_filter_by_status(analyst_client, analyst_user):
    _make_doc(analyst_user, title="Ready Doc")
    response = analyst_client.get("/ui/documents/?status=ready")
    assert response.status_code == 200


@pytest.mark.django_db
def test_document_list_admin_sees_all(admin_client, analyst_user, admin_user):
    _make_doc(analyst_user, title="Analyst Doc")
    _make_doc(admin_user, title="Admin Doc", content=b"admin content")
    response = admin_client.get("/ui/documents/")
    assert response.status_code == 200
    assert b"Analyst Doc" in response.content
    assert b"Admin Doc" in response.content


# ---------------------------------------------------------------------------
# Document upload
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_upload_get_analyst(analyst_client):
    response = analyst_client.get("/ui/documents/upload/")
    assert response.status_code == 200


@pytest.mark.django_db
def test_upload_get_viewer_forbidden(viewer_client):
    response = viewer_client.get("/ui/documents/upload/")
    assert response.status_code == 403


@pytest.mark.django_db
def test_upload_single_creates_document(analyst_client, analyst_user):
    from unittest.mock import patch

    from ingestion.tasks import process_document

    # Patch out the Celery task so we don't need a broker.

    content = b"Hello upload test"
    f = SimpleUploadedFile("hello.txt", content, content_type="text/plain")
    with patch.object(process_document, "delay"):
        response = analyst_client.post(
            "/ui/documents/upload/",
            {
                "mode": "single",
                "title": "Upload Test",
                "file_type": "text",
                "chunker": "paragraph",
                "file": f,
            },
            follow=True,
        )
    assert response.status_code == 200
    from apps.documents.models import Document

    assert Document.objects.filter(title="Upload Test").exists()


@pytest.mark.django_db
def test_upload_single_duplicate_redirects(analyst_client, analyst_user):
    from unittest.mock import patch

    from ingestion.tasks import process_document

    content = b"Duplicate content"
    _make_doc(analyst_user, title="Existing", content=content)
    f = SimpleUploadedFile("dup.txt", content, content_type="text/plain")
    with patch.object(process_document, "delay"):
        response = analyst_client.post(
            "/ui/documents/upload/",
            {
                "mode": "single",
                "title": "Duplicate",
                "file_type": "text",
                "chunker": "paragraph",
                "file": f,
            },
            follow=True,
        )
    assert response.status_code == 200
    # Should show a warning (duplicate detected)
    messages_list = list(response.context["messages"])
    assert any("existiert bereits" in str(m) for m in messages_list)


# ---------------------------------------------------------------------------
# Document detail
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_document_detail_returns_200(analyst_client, analyst_user):
    doc = _make_doc(analyst_user)
    response = analyst_client.get(f"/ui/documents/{doc.pk}/")
    assert response.status_code == 200


@pytest.mark.django_db
def test_document_detail_not_found(analyst_client):
    response = analyst_client.get("/ui/documents/99999/")
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# Document delete
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_document_delete_get_shows_confirm(analyst_client, analyst_user):
    doc = _make_doc(analyst_user)
    response = analyst_client.get(f"/ui/documents/{doc.pk}/delete/")
    assert response.status_code == 200


@pytest.mark.django_db
def test_document_delete_post_removes_document(analyst_client, analyst_user):
    from apps.documents.models import Document

    doc = _make_doc(analyst_user)
    pk = doc.pk
    response = analyst_client.post(f"/ui/documents/{pk}/delete/", follow=True)
    assert response.status_code == 200
    assert not Document.objects.filter(pk=pk).exists()


# ---------------------------------------------------------------------------
# Agent query
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_agent_query_get(analyst_client):
    response = analyst_client.get("/ui/agent/")
    assert response.status_code == 200


@pytest.mark.django_db
def test_agent_query_post_error_handled(analyst_client):
    """POST with agent raising an exception should still return 200."""
    from unittest.mock import patch

    with patch("agents.orchestrator.run_agent", side_effect=RuntimeError("No LLM")):
        response = analyst_client.post(
            "/ui/agent/",
            {"question": "What is OAuth?"},
        )
    assert response.status_code == 200


@pytest.mark.django_db
def test_agent_query_post_htmx_returns_partial(analyst_client):
    from unittest.mock import patch

    fake_result = {"answer": "OAuth is an authorization framework.", "plan": "", "iterations": 1, "tool_calls": 0}
    with patch("agents.orchestrator.run_agent", return_value=fake_result):
        response = analyst_client.post(
            "/ui/agent/",
            {"question": "Explain OAuth"},
            HTTP_HX_REQUEST="true",
        )
    assert response.status_code == 200
    assert b"OAuth" in response.content


@pytest.mark.django_db
def test_agent_query_history_stored_in_session(analyst_client):
    from unittest.mock import patch

    fake_result = {"answer": "Some answer.", "plan": "", "iterations": 1, "tool_calls": 0}
    with patch("agents.orchestrator.run_agent", return_value=fake_result):
        analyst_client.post("/ui/agent/", {"question": "Test question"})

    # Fetch the agent page and check that history is in context
    response = analyst_client.get("/ui/agent/")
    assert response.status_code == 200
    assert b"Test question" in response.content


@pytest.mark.django_db
def test_agent_clear_history(analyst_client):
    from unittest.mock import patch

    fake_result = {"answer": "Some answer.", "plan": "", "iterations": 1, "tool_calls": 0}
    with patch("agents.orchestrator.run_agent", return_value=fake_result):
        analyst_client.post("/ui/agent/", {"question": "Question to clear"})

    analyst_client.post("/ui/agent/clear-history/")
    session = analyst_client.session
    assert session.get("query_history", []) == []


# ---------------------------------------------------------------------------
# Search
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_search_get_empty(analyst_client):
    response = analyst_client.get("/ui/search/")
    assert response.status_code == 200


@pytest.mark.django_db
def test_search_htmx_returns_partial(analyst_client):
    from unittest.mock import patch

    with patch("retrieval.hybrid.hybrid_search", return_value=[]):
        response = analyst_client.get(
            "/ui/search/?q=test&mode=hybrid",
            HTTP_HX_REQUEST="true",
        )
    assert response.status_code == 200


# ---------------------------------------------------------------------------
# Admin reembed
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_admin_reembed_requires_admin_role(analyst_client):
    response = analyst_client.post("/ui/admin/reembed/")
    assert response.status_code == 403


@pytest.mark.django_db
def test_admin_reembed_starts_task(admin_client):
    from unittest.mock import patch

    from ingestion.tasks import reembed_documents

    with patch.object(reembed_documents, "delay") as mock_delay:
        response = admin_client.post("/ui/admin/reembed/", follow=True)
    assert response.status_code == 200
    mock_delay.assert_called_once()
    messages_list = list(response.context["messages"])
    assert any("Re-Embedding" in str(m) for m in messages_list)
