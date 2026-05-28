"""Integration tests for the Document REST API (requires DB + pgvector)."""

import hashlib

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile


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
# Authentication
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_unauthenticated_returns_403(api_client):
    response = api_client.get("/api/documents/")
    assert response.status_code in (401, 403)


# ---------------------------------------------------------------------------
# Document list / retrieve
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_list_documents_empty(auth_client):
    response = auth_client.get("/api/documents/")
    assert response.status_code == 200
    # Accept both list and paginated response
    data = response.json()
    items = data if isinstance(data, list) else data.get("results", data)
    assert isinstance(items, list)


@pytest.mark.django_db
def test_list_documents_returns_created(auth_client, user):
    _make_doc(user, title="Alpha Doc")
    _make_doc(user, title="Beta Doc", content=b"different content")

    response = auth_client.get("/api/documents/")
    assert response.status_code == 200
    data = response.json()
    items = data if isinstance(data, list) else data.get("results", data)
    titles = [d["title"] for d in items]
    assert "Alpha Doc" in titles
    assert "Beta Doc" in titles


@pytest.mark.django_db
def test_retrieve_document_by_id(auth_client, user):
    doc = _make_doc(user, title="Retrieve Me")

    response = auth_client.get(f"/api/documents/{doc.pk}/")
    assert response.status_code == 200
    assert response.json()["title"] == "Retrieve Me"


@pytest.mark.django_db
def test_retrieve_nonexistent_returns_404(auth_client):
    response = auth_client.get("/api/documents/999999/")
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# Document delete
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_delete_document(auth_client, user):
    from apps.documents.models import Document

    doc = _make_doc(user)
    pk = doc.pk

    response = auth_client.delete(f"/api/documents/{pk}/")
    assert response.status_code == 204
    assert not Document.objects.filter(pk=pk).exists()


# ---------------------------------------------------------------------------
# Search endpoint (basic smoke test – no embeddings needed for metadata mode)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_search_missing_query_returns_400(auth_client):
    response = auth_client.get("/api/search/")
    assert response.status_code == 400


@pytest.mark.django_db
def test_search_metadata_mode(auth_client, user):
    import json

    _make_doc(user, title="Contract Alpha")

    response = auth_client.get(
        "/api/search/",
        {"q": "test", "mode": "metadata", "filters": json.dumps({"file_type": "text"})},
    )
    # Should return 200 (possibly empty results without embeddings)
    assert response.status_code == 200


# ---------------------------------------------------------------------------
# Agent query endpoint (sync, mocked LLM)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_agent_query_missing_query(auth_client):
    response = auth_client.post("/api/agent/query/", {}, format="json")
    assert response.status_code == 400


@pytest.mark.django_db
def test_agent_query_invalid_iterations(auth_client):
    response = auth_client.post(
        "/api/agent/query/",
        {"query": "test", "max_iterations": 99},
        format="json",
    )
    assert response.status_code == 400


@pytest.mark.django_db
def test_agent_query_sync(auth_client):
    from unittest.mock import patch

    mock_result = {
        "answer": "42 is the answer.",
        "plan": "search | answer",
        "iterations": 1,
        "conversation": [
            {"role": "system", "content": "..."},
            {"role": "user", "content": "What is the answer?"},
            {"role": "assistant", "content": "ANSWER: 42 is the answer."},
        ],
    }

    with patch("agents.orchestrator.run_agent", return_value=mock_result):
        response = auth_client.post(
            "/api/agent/query/",
            {"query": "What is the answer?"},
            format="json",
        )

    assert response.status_code == 200
    data = response.json()
    assert data["answer"] == "42 is the answer."
    assert data["plan"] == "search | answer"
    assert data["iterations"] == 1


# ---------------------------------------------------------------------------
# AgentTask async endpoint
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_agent_async_creates_task(auth_client):
    from unittest.mock import patch

    with patch("agents.tasks.run_agent_task.delay") as mock_delay:
        response = auth_client.post(
            "/api/agent/query/",
            {"query": "Async test", "async": True},
            format="json",
        )

    assert response.status_code == 202
    data = response.json()
    assert "task_id" in data
    assert data["status"] == "pending"
    mock_delay.assert_called_once()


@pytest.mark.django_db
def test_agent_task_poll(auth_client):
    from apps.agent.models import AgentTask

    task = AgentTask.objects.create(
        query="test",
        status=AgentTask.Status.DONE,
        result={"answer": "done answer", "plan": "", "iterations": 1},
    )

    response = auth_client.get(f"/api/agent/tasks/{task.pk}/")
    assert response.status_code == 200
    assert response.json()["status"] == "done"


@pytest.mark.django_db
def test_agent_task_not_found(auth_client):
    import uuid

    response = auth_client.get(f"/api/agent/tasks/{uuid.uuid4()}/")
    assert response.status_code == 404
