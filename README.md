# Hybrid Agentic RAG System

Lokales KI-gestütztes Analyse- und Retrieval-System für strukturierte und unstrukturierte Dokumente.

Das System ist **kein** einfacher "Chat mit PDFs", sondern ein erweiterbares Wissens- und Analysesystem, das semantische Suche, Dokumentbeziehungen und iteratives agentisches Retrieval kombiniert – vollständig On-Prem, ohne Cloud-Abhängigkeiten.

> Die vollständige Projektbeschreibung, Architekturprinzipien und Designentscheidungen sind in [Zusammenfassung.txt](Zusammenfassung.txt) dokumentiert.

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
├── Dockerfile                         # Python 3.13-slim, läuft als UID 1234:1234
├── docker-compose.yml                 # db, redis, ollama, web, worker
├── requirements.txt
├── manage.py
├── .env.example                       # Vorlage für .env
├── Zusammenfassung.txt                # Projektbeschreibung und Architektur
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
docker compose build
docker compose up -d db redis ollama
```

### 3. LLM-Modelle laden

```bash
# Embedding-Modell
docker compose exec ollama ollama pull nomic-embed-text

# Chat-Modell
docker compose exec ollama ollama pull qwen2.5:7b
```

### 4. Datenbank initialisieren

```bash
docker compose run --rm web python manage.py makemigrations
docker compose run --rm web python manage.py migrate
docker compose run --rm web python manage.py createsuperuser
```

### 5. System starten

```bash
docker compose up
```

Erreichbar unter:
- Django-Backend: http://localhost:8000
- Django-Admin: http://localhost:8000/admin
- Ollama-API: http://localhost:11434

---

## Architekturprinzipien

- **Retrieval wichtiger als Modellgröße** – das LLM orchestriert, die Datenbank liefert Wissen
- **Kein direkter DB-Zugriff für das LLM** – ausschließlich über definierte Tools/MCP
- **Semantisches Chunking** statt tokenbasiertem Splitting
- **Hybrid Retrieval**: Vektorsimilarität + PostgreSQL-Volltext + Metadatenfilter + relationale Traversal
- **Vollständig On-Prem** – keine externen API-Aufrufe

Siehe [Zusammenfassung.txt](Zusammenfassung.txt) für die vollständige Spezifikation.
