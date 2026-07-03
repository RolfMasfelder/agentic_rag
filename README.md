# Hybrid Agentic RAG System

Local AI-powered analysis and retrieval system for structured and unstructured documents.

This is **not** a simple "chat with PDFs" tool, but an extensible knowledge and analysis system combining semantic search, document relationships, and iterative agentic retrieval — fully on-prem, no cloud dependencies.

> The full project description, architecture principles, and design decisions are documented in [docs/Zusammenfassung.txt](docs/Zusammenfassung.txt).

---

## Tech Stack

| Component | Technology |
|---|---|
| Backend | Python 3.13, Django 5.2, Django REST Framework |
| Database | PostgreSQL 17 + pgvector |
| Task Queue | Celery + Redis |
| LLM runtime | Ollama (local) |
| Containerization | Docker Compose |

---

## Project Structure

```txt
agentic_rag/
│
├── docker/
│   ├── Dockerfile                         # Python 3.13-slim, runs as UID 1234:1234
│   └── docker-compose.yml                 # db, redis, web, worker
├── docs/
│   └── Zusammenfassung.txt                # Project description and architecture
├── scripts/                               # Helper scripts (e.g. download_testdata.py)
├── data/                                  # Test data, not versioned
├── requirements.txt
├── requirements-dev.txt
├── pyproject.toml                         # Ruff and pytest configuration
├── .env.example                           # Template for .env
│
└── django_root/                           # All Django code (PYTHONPATH root)
    ├── manage.py
    │
    ├── config/                            # Django project configuration
    │   ├── celery.py                      # Celery app initialization
    │   ├── urls.py                        # Root URL configuration
    │   ├── wsgi.py
    │   ├── asgi.py
    │   └── settings/
    │       ├── base.py                    # Shared settings
    │       ├── dev.py                     # Development environment
    │       └── prod.py                    # Production environment
    │
    ├── apps/                              # Django applications
    │   ├── users/                         # User management
    │   │   ├── models.py                  # Extended User (roles: admin/analyst/viewer)
    │   │   └── admin.py
    │   ├── documents/                     # Core domain logic
    │   │   ├── models.py                  # Document, Chunk, DocumentRelation, AnalysisResult
    │   │   ├── serializers.py             # DRF serializers
    │   │   ├── views.py                   # ViewSet incl. /process and /relations endpoints
    │   │   ├── urls.py
    │   │   ├── admin.py
    │   │   └── migrations/
    │   │       └── 0001_enable_pgvector.py  # CREATE EXTENSION vector
    │   └── audit/                         # Audit logging
    │       ├── models.py                  # AuditLog
    │       └── middleware.py              # Logs all POST/PUT/PATCH/DELETE requests
    │
    ├── ingestion/                         # Document processing pipeline
    │   ├── parsers/
    │   │   ├── base.py                    # Abstract base class + ParsedDocument/Chunk
    │   │   ├── pdf.py                     # PyMuPDF parser
    │   │   └── markdown.py                # Section-based Markdown parser
    │   ├── chunkers/
    │   │   ├── base.py                    # Abstract base class
    │   │   └── paragraph.py               # ParagraphChunker with configurable overlap
    │   └── tasks.py                       # Celery tasks: parse → chunk → embed
    │
    ├── retrieval/                         # Hybrid retrieval engine
    │   ├── vector_search.py               # pgvector CosineDistance
    │   ├── fulltext_search.py             # PostgreSQL full-text search (German)
    │   ├── metadata_filter.py             # JSON metadata filter
    │   └── hybrid.py                      # Weighted score fusion (vector + full-text)
    │
    ├── agents/                            # Agentic orchestration
    │   ├── orchestrator.py                # Tool-calling loop (TOOL: / ANSWER: protocol)
    │   └── tools/
    │       ├── search.py                  # search_documents, search_similar_chunks, search_by_metadata
    │       └── documents.py               # load_document, find_related_documents, summarize_document
    │
    └── llm/
        └── client.py                      # Ollama client: get_embedding(), chat()
```

---

## Getting Started

### 1. Prepare the environment

```bash
cp .env.example .env
# Edit .env: set DB_PASSWORD and DJANGO_SECRET_KEY
```

### 2. Build and start containers

```bash
./docker/build-docker.sh
```

The script runs all steps automatically in the right order:
build containers → start DB/Redis → migrations → load demo data → start all services.

```bash
./docker/build-docker.sh --fresh     # without build cache (after dependency changes)
./docker/build-docker.sh --no-seed   # skip demo data
```

**Manual steps (without the script):**

```bash
docker compose -f docker/docker-compose.yml --env-file .env build
docker compose -f docker/docker-compose.yml --env-file .env up -d db redis
docker compose -f docker/docker-compose.yml --env-file .env run --rm web python django_root/manage.py migrate
docker compose -f docker/docker-compose.yml --env-file .env run --rm web python django_root/manage.py seed_data
docker compose -f docker/docker-compose.yml --env-file .env up -d
```

Once running, the UI is available at `http://localhost:8001/ui/`. API endpoints under `http://localhost:8001/api/`.

The `seed_data` command is **idempotent** — it can be re-run after every container rebuild without creating duplicates.

#### Demo Users

| Username  | Password    | Role    | Permissions                     |
|-----------|-------------|---------|----------------------------------|
| `admin`   | `admin123`  | admin   | everything + Django admin (`/admin/`) |
| `analyst` | `analyst123`| analyst | upload & delete documents        |
| `viewer`  | `viewer123` | viewer  | read & search only               |

> **Note:** These passwords are for local development and testing only. Never use them in production.

### 3. Stop the system

```bash
docker compose -f docker/docker-compose.yml --env-file .env down
```

> **Note:** Ollama runs on a separate machine. Set `OLLAMA_BASE_URL` in `.env` accordingly.

---

## Architecture Principles

- **Retrieval matters more than model size** — the LLM orchestrates, the database provides knowledge
- **No direct DB access for the LLM** — only through defined tools/MCP
- **Semantic chunking** instead of token-based splitting
- **Hybrid retrieval**: vector similarity + PostgreSQL full-text + metadata filtering + relational traversal
- **Fully on-prem** — no external API calls

See [docs/Zusammenfassung.txt](docs/Zusammenfassung.txt) for the full specification.
