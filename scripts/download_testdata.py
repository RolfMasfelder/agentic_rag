#!/usr/bin/env python3
"""Lädt ~100 Testdateien unterschiedlichen Typs für die agentic_rag-Entwicklung herunter.

Dateien werden in data/{typ}/ gespeichert. Bereits vorhandene Dateien werden übersprungen.

Verwendung:
    python scripts/download_testdata.py
    python scripts/download_testdata.py --dry-run
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import httpx

BASE = Path(__file__).resolve().parent.parent / "data"
DELAY = 0.4  # Sekunden zwischen Anfragen (server-schonend)
TIMEOUT = 30

# (url, dateiname) pro Kategorie
FILES: dict[str, list[tuple[str, str]]] = {
    # -----------------------------------------------------------------
    # PDFs: neue RFC-Dokumente als PDF (IETF, gemeinfrei; nur 9000er haben PDF)
    # Ältere RFCs nur als .txt über IETF verfügbar → Kategorie 'rfc'
    # -----------------------------------------------------------------
    "pdf": [
        ("https://www.rfc-editor.org/rfc/rfc9110.pdf", "rfc9110-http-semantics.pdf"),
        ("https://www.rfc-editor.org/rfc/rfc9111.pdf", "rfc9111-http-caching.pdf"),
        ("https://www.rfc-editor.org/rfc/rfc9112.pdf", "rfc9112-http11.pdf"),
        ("https://www.rfc-editor.org/rfc/rfc9113.pdf", "rfc9113-http2.pdf"),
        ("https://www.rfc-editor.org/rfc/rfc9114.pdf", "rfc9114-http3.pdf"),
    ],
    # -----------------------------------------------------------------
    # RFC-Textdateien: ältere Standards (IETF, gemeinfrei)
    # -----------------------------------------------------------------
    "rfc": [
        ("https://www.rfc-editor.org/rfc/rfc2119.txt", "rfc2119-key-words.txt"),
        ("https://www.rfc-editor.org/rfc/rfc3986.txt", "rfc3986-uri.txt"),
        ("https://www.rfc-editor.org/rfc/rfc4122.txt", "rfc4122-uuid.txt"),
        ("https://www.rfc-editor.org/rfc/rfc4287.txt", "rfc4287-atom.txt"),
        ("https://www.rfc-editor.org/rfc/rfc5321.txt", "rfc5321-smtp.txt"),
        ("https://www.rfc-editor.org/rfc/rfc5322.txt", "rfc5322-email-format.txt"),
        ("https://www.rfc-editor.org/rfc/rfc6265.txt", "rfc6265-cookies.txt"),
        ("https://www.rfc-editor.org/rfc/rfc6266.txt", "rfc6266-content-disposition.txt"),
        ("https://www.rfc-editor.org/rfc/rfc6455.txt", "rfc6455-websocket.txt"),
        ("https://www.rfc-editor.org/rfc/rfc6749.txt", "rfc6749-oauth2.txt"),
        ("https://www.rfc-editor.org/rfc/rfc6750.txt", "rfc6750-bearer-token.txt"),
        ("https://www.rfc-editor.org/rfc/rfc6902.txt", "rfc6902-json-patch.txt"),
        ("https://www.rfc-editor.org/rfc/rfc7230.txt", "rfc7230-http11-syntax.txt"),
        ("https://www.rfc-editor.org/rfc/rfc7231.txt", "rfc7231-http-semantics.txt"),
        ("https://www.rfc-editor.org/rfc/rfc7232.txt", "rfc7232-conditional-requests.txt"),
        ("https://www.rfc-editor.org/rfc/rfc7234.txt", "rfc7234-http-caching.txt"),
        ("https://www.rfc-editor.org/rfc/rfc7235.txt", "rfc7235-http-auth.txt"),
        ("https://www.rfc-editor.org/rfc/rfc7396.txt", "rfc7396-json-merge-patch.txt"),
        ("https://www.rfc-editor.org/rfc/rfc7519.txt", "rfc7519-jwt.txt"),
        ("https://www.rfc-editor.org/rfc/rfc7521.txt", "rfc7521-jwt-assertions.txt"),
        ("https://www.rfc-editor.org/rfc/rfc7591.txt", "rfc7591-oauth2-registration.txt"),
        ("https://www.rfc-editor.org/rfc/rfc7662.txt", "rfc7662-oauth2-introspection.txt"),
        ("https://www.rfc-editor.org/rfc/rfc7807.txt", "rfc7807-problem-details.txt"),
        ("https://www.rfc-editor.org/rfc/rfc8259.txt", "rfc8259-json.txt"),
        ("https://www.rfc-editor.org/rfc/rfc8446.txt", "rfc8446-tls13.txt"),
    ],
    # -----------------------------------------------------------------
    # Markdown / reStructuredText: GitHub-READMEs (MIT/BSD/Apache)
    # -----------------------------------------------------------------
    "markdown": [
        ("https://raw.githubusercontent.com/django/django/main/README.rst", "django.rst"),
        ("https://raw.githubusercontent.com/pallets/flask/main/README.md", "flask.md"),
        ("https://raw.githubusercontent.com/tiangolo/fastapi/master/README.md", "fastapi.md"),
        ("https://raw.githubusercontent.com/celery/celery/main/README.rst", "celery.rst"),
        ("https://raw.githubusercontent.com/redis/redis-py/master/README.md", "redis-py.md"),
        ("https://raw.githubusercontent.com/pgvector/pgvector/master/README.md", "pgvector.md"),
        ("https://raw.githubusercontent.com/pgvector/pgvector-python/master/README.md", "pgvector-python.md"),
        ("https://raw.githubusercontent.com/sqlalchemy/sqlalchemy/main/README.rst", "sqlalchemy.rst"),
        ("https://raw.githubusercontent.com/pydantic/pydantic/main/README.md", "pydantic.md"),
        ("https://raw.githubusercontent.com/encode/httpx/master/README.md", "httpx.md"),
        ("https://raw.githubusercontent.com/psf/requests/main/README.md", "requests.md"),
        ("https://raw.githubusercontent.com/pytest-dev/pytest/main/README.rst", "pytest.rst"),
        ("https://raw.githubusercontent.com/astral-sh/ruff/main/README.md", "ruff.md"),
        ("https://raw.githubusercontent.com/python/mypy/master/README.md", "mypy.md"),
        ("https://raw.githubusercontent.com/python-poetry/poetry/main/README.md", "poetry.md"),
        ("https://raw.githubusercontent.com/encode/django-rest-framework/master/README.md", "django-rest-framework.md"),
        ("https://raw.githubusercontent.com/carltongibson/django-filter/main/README.rst", "django-filter.rst"),
        ("https://raw.githubusercontent.com/encode/starlette/master/README.md", "starlette.md"),
        ("https://raw.githubusercontent.com/Textualize/rich/master/README.md", "rich.md"),
        ("https://raw.githubusercontent.com/ollama/ollama/main/README.md", "ollama.md"),
        ("https://raw.githubusercontent.com/numpy/numpy/main/README.md", "numpy.md"),
        ("https://raw.githubusercontent.com/pandas-dev/pandas/main/README.md", "pandas.md"),
        ("https://raw.githubusercontent.com/scikit-learn/scikit-learn/main/README.rst", "scikit-learn.rst"),
        ("https://raw.githubusercontent.com/huggingface/transformers/main/README.md", "transformers.md"),
        ("https://raw.githubusercontent.com/langchain-ai/langchain/master/README.md", "langchain.md"),
    ],
    # -----------------------------------------------------------------
    # OpenAPI-Spezifikationen (OAI Apache 2.0, Stripe CC-BY)
    # -----------------------------------------------------------------
    "openapi": [
        (
            "https://raw.githubusercontent.com/OAI/OpenAPI-Specification/3.0.3/examples/v3.0/petstore.yaml",
            "oai-petstore-v30.yaml",
        ),  # noqa: E501
        (
            "https://raw.githubusercontent.com/OAI/OpenAPI-Specification/3.0.3/examples/v3.0/api-with-examples.yaml",
            "oai-api-with-examples.yaml",
        ),  # noqa: E501
        (
            "https://raw.githubusercontent.com/OAI/OpenAPI-Specification/3.0.3/examples/v3.0/callback-example.yaml",
            "oai-callback-example.yaml",
        ),  # noqa: E501
        (
            "https://raw.githubusercontent.com/OAI/OpenAPI-Specification/3.0.3/examples/v3.0/link-example.yaml",
            "oai-link-example.yaml",
        ),  # noqa: E501
        (
            "https://raw.githubusercontent.com/OAI/OpenAPI-Specification/3.0.3/examples/v3.0/uspto.yaml",
            "oai-uspto.yaml",
        ),  # noqa: E501
        (
            "https://raw.githubusercontent.com/OAI/OpenAPI-Specification/3.1.1/examples/v3.1/non-oauth-scopes.yaml",
            "oai-non-oauth-scopes.yaml",
        ),  # noqa: E501
        (
            "https://raw.githubusercontent.com/OAI/OpenAPI-Specification/3.1.0/examples/v3.1/webhook-example.yaml",
            "oai-webhook-example.yaml",
        ),  # noqa: E501
        ("https://petstore3.swagger.io/api/v3/openapi.json", "swagger-petstore3.json"),
        ("https://raw.githubusercontent.com/stripe/openapi/master/openapi/spec3.json", "stripe-spec3.json"),
        ("https://raw.githubusercontent.com/moby/moby/master/api/swagger.yaml", "docker-engine-swagger.yaml"),
    ],
    # -----------------------------------------------------------------
    # XML: Maven-Schemas, POMs, GitHub-Atom-Feeds, W3C
    # -----------------------------------------------------------------
    "xml": [
        # Maven XML-Schemas (Apache, öffentlich)
        ("https://maven.apache.org/xsd/maven-4.0.0.xsd", "maven-4.0.0.xsd"),
        ("https://maven.apache.org/xsd/settings-1.1.0.xsd", "maven-settings-1.1.0.xsd"),
        # Maven POM-Dateien bekannter Apache/OSS-Projekte (Apache 2.0)
        ("https://raw.githubusercontent.com/apache/commons-lang/master/pom.xml", "apache-commons-lang-pom.xml"),
        ("https://raw.githubusercontent.com/apache/httpcomponents-client/master/pom.xml", "apache-httpclient-pom.xml"),
        ("https://raw.githubusercontent.com/spring-projects/spring-batch/main/pom.xml", "spring-batch-pom.xml"),
        ("https://raw.githubusercontent.com/apache/maven/master/pom.xml", "apache-maven-pom.xml"),
        (
            "https://raw.githubusercontent.com/apache/commons-collections/master/pom.xml",
            "apache-commons-collections-pom.xml",
        ),  # noqa: E501
        ("https://raw.githubusercontent.com/apache/logging-log4j2/master/pom.xml", "apache-log4j2-pom.xml"),
        ("https://raw.githubusercontent.com/FasterXML/jackson-databind/master/pom.xml", "jackson-databind-pom.xml"),
        ("https://raw.githubusercontent.com/liquibase/liquibase/master/pom.xml", "liquibase-pom.xml"),
        # GitHub Atom-Feeds (öffentlich, valides XML)
        ("https://github.com/django/django/commits/main.atom", "django-commits.atom"),
        ("https://github.com/pallets/flask/commits/main.atom", "flask-commits.atom"),
        ("https://github.com/tiangolo/fastapi/commits/master.atom", "fastapi-commits.atom"),
        ("https://github.com/pgvector/pgvector/commits/master.atom", "pgvector-commits.atom"),
        ("https://github.com/celery/celery/commits/main.atom", "celery-commits.atom"),
        # W3C XML Schema (öffentlich)
        ("https://www.w3.org/2001/XMLSchema.xsd", "w3c-xmlschema.xsd"),
        # Android-Manifest (Google Samples, Apache 2.0)
        (
            "https://raw.githubusercontent.com/android/architecture-components-samples/main/GithubBrowserSample/app/src/main/AndroidManifest.xml",
            "android-github-browser-manifest.xml",
        ),  # noqa: E501
        # W3C SVG (öffentlich)
        ("https://www.w3.org/Icons/SVG/svg-logo-v.svg", "w3c-svg-logo.svg"),
        # Kubernetes-Beispiele (Apache 2.0)
        (
            "https://raw.githubusercontent.com/kubernetes/website/main/content/en/examples/controllers/nginx-deployment.yaml",
            "k8s-nginx-deployment.yaml",
        ),  # noqa: E501
        (
            "https://raw.githubusercontent.com/kubernetes/website/main/content/en/examples/service/load-balancer-example.yaml",
            "k8s-load-balancer-service.yaml",
        ),  # noqa: E501
    ],
    # -----------------------------------------------------------------
    # Text: Project Gutenberg (gemeinfrei)
    # -----------------------------------------------------------------
    "text": [
        ("https://www.gutenberg.org/cache/epub/84/pg84.txt", "frankenstein.txt"),
        ("https://www.gutenberg.org/cache/epub/1342/pg1342.txt", "pride-and-prejudice.txt"),
        ("https://www.gutenberg.org/cache/epub/11/pg11.txt", "alice-in-wonderland.txt"),
        ("https://www.gutenberg.org/cache/epub/98/pg98.txt", "tale-of-two-cities.txt"),
        ("https://www.gutenberg.org/cache/epub/2701/pg2701.txt", "moby-dick.txt"),
        ("https://www.gutenberg.org/cache/epub/1080/pg1080.txt", "modest-proposal.txt"),
        ("https://www.gutenberg.org/cache/epub/205/pg205.txt", "walden.txt"),
        ("https://www.gutenberg.org/cache/epub/1399/pg1399.txt", "anna-karenina.txt"),
        ("https://www.gutenberg.org/cache/epub/2554/pg2554.txt", "crime-and-punishment.txt"),
        ("https://www.gutenberg.org/cache/epub/174/pg174.txt", "picture-of-dorian-gray.txt"),
    ],
}


def _download_one(url: str, dest: Path, client: httpx.Client) -> bool:
    try:
        r = client.get(url, follow_redirects=True, timeout=TIMEOUT)
        r.raise_for_status()
        dest.write_bytes(r.content)
        print(f"  [ok]   {dest.name}  ({len(r.content) // 1024} KB)")
        return True
    except Exception as exc:
        print(f"  [fail] {dest.name}: {exc}", file=sys.stderr)
        return False


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dry-run", action="store_true", help="Nur anzeigen, nicht herunterladen")
    args = parser.parse_args()

    total = sum(len(v) for v in FILES.values())
    print(f"Zielverzeichnis : {BASE}")
    print(f"Geplante Dateien: {total}\n")

    ok = failed = skipped = 0

    with httpx.Client(headers={"User-Agent": "agentic_rag-testdata/1.0 (development)"}) as client:
        for subdir, items in FILES.items():
            folder = BASE / subdir
            folder.mkdir(parents=True, exist_ok=True)
            print(f"── {subdir}/ ({len(items)} Dateien)")

            for url, filename in items:
                dest = folder / filename

                if args.dry_run:
                    print(f"  [dry]  {filename}")
                    continue

                if dest.exists():
                    print(f"  [skip] {filename}")
                    skipped += 1
                    continue

                if _download_one(url, dest, client):
                    ok += 1
                else:
                    failed += 1

                time.sleep(DELAY)

    if not args.dry_run:
        print(f"\nErgebnis: {ok} heruntergeladen · {skipped} übersprungen · {failed} fehlgeschlagen")
        if failed:
            sys.exit(1)


if __name__ == "__main__":
    main()
