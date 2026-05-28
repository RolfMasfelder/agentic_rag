"""Shared pytest fixtures."""

import socket

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient


@pytest.fixture
def api_client() -> APIClient:
    return APIClient()


@pytest.fixture
def user(db):
    user_model = get_user_model()
    return user_model.objects.create_user(
        username="testuser",
        password="testpass123",
        email="test@example.com",
    )


@pytest.fixture
def auth_client(user) -> APIClient:
    client = APIClient()
    client.force_authenticate(user=user)
    return client


@pytest.fixture(scope="session")
def ollama_available() -> bool:
    """Return True if the configured Ollama host is reachable (TCP connect)."""
    from django.conf import settings

    url = getattr(settings, "OLLAMA_BASE_URL", "")
    if not url:
        return False
    host_port = url.replace("http://", "").replace("https://", "").split("/")[0]
    host, _, port_str = host_port.partition(":")
    port = int(port_str) if port_str else 11434
    try:
        sock = socket.create_connection((host, port), timeout=2)
        sock.close()
        return True
    except OSError:
        return False


@pytest.fixture
def require_ollama(ollama_available):
    """Skip the test when Ollama or the DB is not reachable."""
    from django.conf import settings

    # Check DB reachability (hostname 'db' only resolves inside Docker)
    try:
        db_url = settings.DATABASES["default"].get("HOST", "")
        if db_url:
            socket.getaddrinfo(db_url, settings.DATABASES["default"].get("PORT", 5432))
    except (OSError, KeyError):
        pytest.skip("DB not reachable (run inside Docker)")

    if not ollama_available:
        pytest.skip(f"Ollama not reachable at {settings.OLLAMA_BASE_URL}")
