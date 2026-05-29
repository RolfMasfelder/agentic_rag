# Hybrid Agentic RAG System

Lokales KI-gestütztes Analyse- und Retrieval-System für strukturierte und unstrukturierte Dokumente.

Das System ist **kein** einfacher "Chat mit PDFs", sondern ein erweiterbares Wissens- und Analysesystem, das semantische Suche, Dokumentbeziehungen und iteratives agentisches Retrieval kombiniert – vollständig On-Prem, ohne Cloud-Abhängigkeiten.

> Die vollständige Projektbeschreibung, Architekturprinzipien und Designentscheidungen sind in [docs/Zusammenfassung.txt](docs/Zusammenfassung.txt) dokumentiert.

---

## Technologiestack

| Komponente | Technologie |
|---|---|
| Backend | Python 3.13, Django 5.1, Django REST Framework |
| Datenbank | PostgreSQL 16 + pgvector |
| Task Queue | Celery + Redis |
| LLM-Laufzeit | Ollama (lokal) |
| Containerisierung | Docker Compose |

---

## Projektstruktur

```
agentic_rag/
│
├── docker/
│   ├── Dockerfile                         # Python 3.13-slim, läuft als UID 1234:1234
│   └── docker-compose.yml                 # db, redis, web, worker
├── docs/
│   └── Zusammenfassung.txt                # Projektbeschreibung und Architektur
├── scripts/                               # Hilfsskripte (z. B. download_testdata.py)
├── data/                                  # Testdaten, nicht versioniert
├── requirements.txt
├── requirements-dev.txt
├── pyproject.toml                         # Ruff- und pytest-Konfiguration
├── .env.example                           # Vorlage für .env
│
└── django_root/                           # Gesamter Django-Code (PYTHONPATH-Wurzel)
    ├── manage.py
    │
    ├── config/                            # Django-Projektkonfiguration
    │   ├── celery.py                      # Celery-App-Initialisierung
    │   ├── urls.py                        # Root-URL-Konfiguration
    │   ├── wsgi.py
    │   ├── asgi.py
    │   └── settings/
    │       ├── base.py                    # Gemeinsame Einstellungen
    │       ├── dev.py                     # Entwicklungsumgebung
    │       └── prod.py                    # Produktionsumgebung
    │
    ├── apps/                              # Django-Applikationen
    │   ├── users/                         # Benutzerverwaltung
    │   │   ├── models.py                  # Erweiterter User (Rollen: admin/analyst/viewer)
    │   │   └── admin.py
    │   ├── documents/                     # Kernfachlogik
    │   │   ├── models.py                  # Document, Chunk, DocumentRelation, AnalysisResult
    │   │   ├── serializers.py             # DRF-Serializer
    │   │   ├── views.py                   # ViewSet inkl. /process- und /relations-Endpoints
    │   │   ├── urls.py
    │   │   ├── admin.py
    │   │   └── migrations/
    │   │       └── 0001_enable_pgvector.py  # CREATE EXTENSION vector
    │   └── audit/                         # Audit-Logging
    │       ├── models.py                  # AuditLog
    │       └── middleware.py              # Schreibt alle POST/PUT/PATCH/DELETE-Requests
    │
    ├── ingestion/                         # Dokumentverarbeitungs-Pipeline
    │   ├── parsers/
    │   │   ├── base.py                    # Abstrakte Basisklasse + ParsedDocument/Chunk
    │   │   ├── pdf.py                     # PyMuPDF-Parser
    │   │   └── markdown.py                # Abschnittsbasierter Markdown-Parser
    │   ├── chunkers/
    │   │   ├── base.py                    # Abstrakte Basisklasse
    │   │   └── paragraph.py               # ParagraphChunker mit konfigurierbarem Overlap
    │   └── tasks.py                       # Celery-Tasks: parse → chunk → embed
    │
    ├── retrieval/                         # Hybrid-Retrieval-Engine
    │   ├── vector_search.py               # pgvector CosineDistance
    │   ├── fulltext_search.py             # PostgreSQL Full-Text Search (Deutsch)
    │   ├── metadata_filter.py             # JSON-Metadaten-Filter
    │   └── hybrid.py                      # Gewichtete Score-Fusion (Vektor + Volltext)
    │
    ├── agents/                            # Agentische Orchestrierung
    │   ├── orchestrator.py                # Tool-Calling-Loop (TOOL: / ANSWER:-Protokoll)
    │   └── tools/
    │       ├── search.py                  # search_documents, search_similar_chunks, search_by_metadata
    │       └── documents.py               # load_document, find_related_documents, summarize_document
    │
    └── llm/
        └── client.py                      # Ollama-Client: get_embedding(), chat()
```

---

## Inbetriebnahme

### 1. Umgebung vorbereiten

```bash
cp .env.example .env
# .env anpassen: DB_PASSWORD und DJANGO_SECRET_KEY setzen
```

### 2. Container bauen und starten

```bash
./docker/build-docker.sh
```

Das Skript führt alle Schritte automatisch in der richtigen Reihenfolge aus:
Container bauen → DB/Redis starten → Migrationen → Demo-Daten laden → alle Services starten.

```bash
./docker/build-docker.sh --fresh     # ohne Build-Cache (nach Dependency-Änderungen)
./docker/build-docker.sh --no-seed   # Demo-Daten überspringen
```

<details>
<summary>Manuelle Schritte (ohne Skript)</summary>

```bash
docker compose -f docker/docker-compose.yml --env-file .env build
docker compose -f docker/docker-compose.yml --env-file .env up -d db redis
docker compose -f docker/docker-compose.yml --env-file .env run --rm web python django_root/manage.py migrate
docker compose -f docker/docker-compose.yml --env-file .env run --rm web python django_root/manage.py seed_data
docker compose -f docker/docker-compose.yml --env-file .env up -d
```

Das `seed_data`-Command ist **idempotent** – es kann nach jedem Container-Neubau erneut ausgeführt werden, ohne Duplikate zu erzeugen.

</details>

#### Demo-Benutzer

| Benutzername | Passwort    | Rolle    | Rechte                          |
|--------------|-------------|----------|---------------------------------|
| `admin`      | `admin123`  | admin    | alles + Django-Admin (`/admin/`)|
| `analyst`    | `analyst123`| analyst  | Dokumente hochladen & löschen   |
| `viewer`     | `viewer123` | viewer   | nur lesen & suchen              |

> **Hinweis:** Diese Passwörter sind ausschließlich für lokale Entwicklung und Tests gedacht.  Niemals in Produktionsumgebungen verwenden.

### 3. System stoppen

```bash
docker compose -f docker/docker-compose.yml --env-file .env down
```

> **Hinweis:** Ollama läuft auf einem separaten Rechner. `OLLAMA_BASE_URL` in `.env` entsprechend setzen.

---

## Architekturprinzipien

- **Retrieval wichtiger als Modellgröße** – das LLM orchestriert, die Datenbank liefert Wissen
- **Kein direkter DB-Zugriff für das LLM** – ausschließlich über definierte Tools/MCP
- **Semantisches Chunking** statt tokenbasiertem Splitting
- **Hybrid Retrieval**: Vektorsimilarität + PostgreSQL-Volltext + Metadatenfilter + relationale Traversal
- **Vollständig On-Prem** – keine externen API-Aufrufe

Siehe [docs/Zusammenfassung.txt](docs/Zusammenfassung.txt) für die vollständige Spezifikation.
