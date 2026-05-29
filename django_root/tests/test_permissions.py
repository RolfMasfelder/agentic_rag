"""Tests for role-based permissions and object-level access control."""

import hashlib

import pytest
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

User = get_user_model()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_user(username, role, db):
    return User.objects.create_user(username=username, password="pw", role=role)


def _make_doc(user, title="Doc", content=b"content"):
    from apps.documents.models import Document

    f = SimpleUploadedFile(f"{title}.txt", content, content_type="text/plain")
    return Document.objects.create(
        title=title,
        file=f,
        file_type=Document.FileType.TEXT,
        content_hash=hashlib.sha256(content).hexdigest(),
        status=Document.Status.READY,
        created_by=user,
    )


def _client_for(user):
    c = APIClient()
    c.force_authenticate(user=user)
    return c


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def admin_user(db):
    return _make_user("admin_perm", "admin", db)


@pytest.fixture
def analyst_user(db):
    return _make_user("analyst_perm", "analyst", db)


@pytest.fixture
def analyst_user2(db):
    return _make_user("analyst_perm2", "analyst", db)


@pytest.fixture
def viewer_user(db):
    return _make_user("viewer_perm", "viewer", db)


# ---------------------------------------------------------------------------
# Role enforcement – write access
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_viewer_cannot_create_document(viewer_user):
    client = _client_for(viewer_user)
    f = SimpleUploadedFile("x.txt", b"hello", content_type="text/plain")
    response = client.post(
        "/api/documents/",
        {"title": "X", "file": f, "file_type": "text"},
        format="multipart",
    )
    assert response.status_code == 403


@pytest.mark.django_db
def test_analyst_can_create_document(analyst_user):
    client = _client_for(analyst_user)
    f = SimpleUploadedFile("y.txt", b"hello analyst", content_type="text/plain")
    response = client.post(
        "/api/documents/",
        {"title": "Y", "file": f, "file_type": "text"},
        format="multipart",
    )
    assert response.status_code == 201


@pytest.mark.django_db
def test_admin_can_create_document(admin_user):
    client = _client_for(admin_user)
    f = SimpleUploadedFile("z.txt", b"hello admin", content_type="text/plain")
    response = client.post(
        "/api/documents/",
        {"title": "Z", "file": f, "file_type": "text"},
        format="multipart",
    )
    assert response.status_code == 201


# ---------------------------------------------------------------------------
# Object-level permissions – document ownership
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_analyst_can_update_own_document(analyst_user):
    doc = _make_doc(analyst_user, title="Mine", content=b"mine")
    client = _client_for(analyst_user)
    response = client.patch(f"/api/documents/{doc.id}/", {"title": "Mine Updated"})
    assert response.status_code == 200


@pytest.mark.django_db
def test_analyst_cannot_update_other_document(analyst_user, analyst_user2):
    doc = _make_doc(analyst_user2, title="Theirs", content=b"theirs")
    client = _client_for(analyst_user)
    response = client.patch(f"/api/documents/{doc.id}/", {"title": "Stolen"})
    # 404 because queryset already excludes other users' docs
    assert response.status_code == 404


@pytest.mark.django_db
def test_analyst_cannot_delete_other_document(analyst_user, analyst_user2):
    doc = _make_doc(analyst_user2, title="OtherDoc", content=b"other")
    client = _client_for(analyst_user)
    response = client.delete(f"/api/documents/{doc.id}/")
    assert response.status_code == 404


@pytest.mark.django_db
def test_admin_can_update_any_document(admin_user, analyst_user):
    doc = _make_doc(analyst_user, title="Analyst Doc", content=b"analyst doc")
    client = _client_for(admin_user)
    response = client.patch(f"/api/documents/{doc.id}/", {"title": "Admin Updated"})
    assert response.status_code == 200


@pytest.mark.django_db
def test_admin_can_delete_any_document(admin_user, analyst_user):
    doc = _make_doc(analyst_user, title="ToDelete", content=b"to delete")
    client = _client_for(admin_user)
    response = client.delete(f"/api/documents/{doc.id}/")
    assert response.status_code == 204


# ---------------------------------------------------------------------------
# Queryset filtering – list isolation
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_user_sees_only_own_documents(analyst_user, analyst_user2):
    _make_doc(analyst_user, title="UserA", content=b"a")
    _make_doc(analyst_user2, title="UserB", content=b"b")

    client = _client_for(analyst_user)
    response = client.get("/api/documents/")
    assert response.status_code == 200
    titles = [d["title"] for d in response.data["results"]]
    assert "UserA" in titles
    assert "UserB" not in titles


@pytest.mark.django_db
def test_admin_sees_all_documents(admin_user, analyst_user, analyst_user2):
    _make_doc(analyst_user, title="DocA", content=b"docA")
    _make_doc(analyst_user2, title="DocB", content=b"docB")

    client = _client_for(admin_user)
    response = client.get("/api/documents/")
    assert response.status_code == 200
    titles = [d["title"] for d in response.data["results"]]
    assert "DocA" in titles
    assert "DocB" in titles


# ---------------------------------------------------------------------------
# Token authentication
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_token_obtain(analyst_user):
    client = APIClient()
    response = client.post(
        "/api/auth/token/",
        {"username": "analyst_perm", "password": "pw"},
    )
    assert response.status_code == 200
    assert "token" in response.data


@pytest.mark.django_db
def test_token_auth_grants_access(analyst_user):
    token = Token.objects.create(user=analyst_user)
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")
    response = client.get("/api/documents/")
    assert response.status_code == 200


@pytest.mark.django_db
def test_invalid_token_is_rejected():
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION="Token invalidtoken123")
    response = client.get("/api/documents/")
    # DRF returns 403 (not 401) when SessionAuthentication is the first
    # authenticator, because its authenticate_header() returns None.
    assert response.status_code in (401, 403)


@pytest.mark.django_db
def test_unauthenticated_is_rejected(api_client):
    response = api_client.get("/api/documents/")
    assert response.status_code in (401, 403)
