# TODO – Hybrid Agentic RAG System

Abgleich mit `Zusammenfassung.txt`. Stand: 2026-05-29.

---

## 1. Parser & Dokumentverarbeitung

- [x] **XML/XSD-Parser** – `ingestion/parsers/xml_parser.py`; jedes Kind-Element wird ein `xml_block`-Chunk
- [x] **OpenAPI-Parser** – `ingestion/parsers/openapi.py`; pro Operation + Schema-Objekt je ein Chunk
- [x] **Code-Parser** – `ingestion/parsers/code.py`; Python via `ast` (Klassen/Funktionen); andere Sprachen als Absätze
- [x] **Plain-Text-Parser** – `ingestion/parsers/text.py`; Leerzeilen als Absatz-Trenner
- [x] **OCR-Integration** – Tesseract-Fallback in `PDFParser` (pytesseract + Pillow); greift bei < 20 Zeichen selektierbarem Text pro Seite

## 2. Chunking

- [x] **XML-bewusstes Chunking** – `XMLParser` erzeugt `xml_block`-Chunks; `ParagraphChunker` lässt sie unverändert durch
- [x] **Code-bewusstes Chunking** – `CodeParser` erzeugt `function`/`class`-Chunks; `ParagraphChunker` lässt sie unverändert durch
- [x] **Klausel-Extraktion** – `ClauseChunker` (`chunkers/clause.py`) erkennt nummerierte Klauseln, §-Marker, Article/Section-Header; aktivierbar via `document.metadata["chunker"] = "clause"`

## 3. REST-API – fehlende Endpunkte

- [x] **Agent-Endpunkt** – `POST /api/agent/query/` → `run_agent()`, gibt `answer`, `iterations`, `sources` zurück
- [x] **Such-Endpunkt** – `GET /api/search/?q=...&mode=hybrid|vector|fulltext|metadata` in `retrieval/views.py`
- [x] **Analyse-Endpunkt** – `AnalysisResultViewSet` CRUD unter `/api/documents/analysis/`
- [x] **Relation-Erstellung** – `DocumentRelationViewSet` unter `/api/documents/relations/` (GET/POST/DELETE)
- [x] **Batch-Import** – `POST /api/documents/batch_import/` (Mehrere Dateien, Duplikat-Erkennung, 207 bei Teilfehlern)

## 4. Retrieval

- [x] **Graph-Traversal** – `retrieval/graph.py`; BFS über `DocumentRelation` (beide Richtungen), bis `max_depth` Hops; als Agent-Tool `graph_traversal` registriert
- [x] **Dokument-Ähnlichkeit** – `retrieval/document_similarity.py`; Durchschnitt aller Chunk-Embeddings → Dokument-Vektor → pgvector-Suche; als Agent-Tool `find_similar_documents` registriert
- [x] **Re-Ranking** – `retrieval/reranker.py`; LLM bewertet jeden Treffer 0–10, sortiert neu; nutzt vorhandenen Ollama-Client, kein Cross-Encoder nötig
- [x] **Query-Expansion** – `retrieval/query_expansion.py`; LLM ergänzt Synonyme/Fachbegriffe; optional per `expand=True` in `search_documents`-Tool nutzbar

## 5. Agentische Architektur ✅

- [x] **Tool-Schema-Validierung** – Parameter-Validierung vor Ausführung (`agents/schema.py`)
- [x] **Context-Window-Management** – Gesprächsverlauf kürzen wenn Tokenlimit überschritten wird (`agents/context.py`)
- [x] **Iterativer Retrieval-Plan** – Agent plant Suchschritte explizit (PLAN:-Phase im Orchestrator)
- [x] **Agent-Task via Celery** – Asynchrone Agent-Ausführung über `apps/agent/` + `agents/tasks.py`

## 6. LLM-Client ✅

- [x] **Streaming** – `chat_stream()` in `llm/client.py`; `run_agent_stream()` + SSE-Endpunkt `POST /api/agent/stream/`
- [x] **Prompt-Templates** – `llm/prompts.py`: summarize, analyze, retrieval_augmented, extract_keywords, compare_documents
- [x] **Fallback-Modell** – `chat()` / `chat_stream()` retries with `OLLAMA_FALLBACK_MODEL` on failure

## 7. Sicherheit & Berechtigungen

- [x] **Rollen-Enforcement** – `IsAnalystOrAbove`-Permission in `apps/users/permissions.py`; VIEWER darf nur lesen, ANALYST/ADMIN dürfen schreiben
- [x] **Objekt-Level-Permissions** – `IsOwnerOrAdmin` für `DocumentViewSet`; `get_queryset()` filtert alle drei ViewSets auf eigene Dokumente (nicht-ADMIN sieht/bearbeitet nur eigene); `perform_create` prüft Eigentümerschaft für Relations und AnalysisResults
- [x] **Token-Authentifizierung** – `rest_framework.authtoken` + `TokenAuthentication` in DRF-Settings; Token-Endpunkt `POST /api/auth/token/`

## 8. Tests ✅

- [x] **Unit-Tests Parser** – PDF-, Markdown-Parser testen
- [x] **Unit-Tests Chunker** – ParagraphChunker mit Edge Cases (leere Texte, sehr lange Texte)
- [x] **Unit-Tests Retrieval** – vector_search, fulltext_search, hybrid_search mocken und testen
- [x] **Integration-Tests API** – DocumentViewSet-Endpunkte mit Test-DB testen
- [x] **Agent-Tests** – Orchestrator mit Mock-LLM und Mock-Tools testen

## 9. Infrastruktur & Betrieb

- [x] **Datenbankmigrationen ausführen** – `migrate documents 0001` + `migrate` erledigt
- [x] **`createsuperuser`** – Admin-Nutzer `admin` angelegt
- [x] **`.env` aus `.env.example` anlegen** – `DJANGO_SECRET_KEY`, `DB_PASSWORD`, `OLLAMA_BASE_URL` gesetzt
- [x] **Gesundheitsprüfung** – `/health/`-Endpunkt angelegt (`config/urls.py`)
- [x] **Logging-Konfiguration** – Strukturiertes Logging in `base.py`; JSON-Format für Produktion in `prod.py`

## 10. Testdaten (laut Zusammenfassung.txt)

- [x] Beispiel-PDFs besorgen (Gesetzestexte, RFCs, Beispielverträge) → `data/`
- [x] OpenAPI-Specs als Testdokumente → `data/`
- [x] XML/XSD-Beispieldateien → `data/`
- [x] Markdown-Dokumentationen (z. B. Open-Source-Projekte) → `data/`

> `data/` ist in `.gitignore` eingetragen (nur `.gitkeep` wird versioniert).

---

## 11. Browser-UI (Django + HTMX + Tailwind CSS v4 + Alpine.js)

Stack: Django 5.2 Templates · HTMX 2.x · Alpine.js 3.x · Tailwind CSS v4 (CDN, kein Build-Step)

### 11.1 Grundgerüst

- [x] **`apps/ui`-App anlegen** – `apps/ui/` mit Views, URLs, Templates; in `INSTALLED_APPS` eingetragen
- [x] **Base-Template** – `templates/ui/base.html`; CDN-Links für Tailwind, HTMX, Alpine; Nav-Bar mit Login-Status und Rollen-Badge
- [x] **URL-Routing** – `apps/ui/urls.py`; in `config/urls.py` eingebunden (Prefix `/ui/`)
- [x] **Login / Logout** – Django-Auth-Views; `/ui/login/`, `/ui/logout/`; Login-Template auf Basis von `base.html`
- [x] **Session-basierte Auth für UI** – Django-Session-Authentication; Rollen-Decorator `analyst_required` für schreibende Views

### 11.2 Dashboard

- [x] **Dashboard-View** – `GET /ui/` → Übersicht: Anzahl Dokumente gesamt / READY / PROCESSING / FAILED / PENDING
- [x] **Embedding-Status-Widget** – Anteil Chunks mit Embedding, Prozentanzeige (Fortschrittsbalken)
- [x] **Aktive Celery-Tasks** – HTMX-Auto-Refresh alle 5 s; zeigt laufende `process_document`-Tasks (via Celery `inspect`)
- [x] **Letzten Ingestions-Log** – Letzte 8 verarbeiteten Dokumente mit Status und Zeitstempel

### 11.3 Dokument-Verwaltung

- [x] **Dokumentliste** – `GET /ui/documents/`; Tabelle mit Filter (Datei-Typ, Status), Pagination (20 pro Seite)
- [x] **Upload-Formular (Einzeldatei)** – Datei-Typ-Auswahl, Chunker-Auswahl; `POST` löst Celery-Task aus; Duplikat-Erkennung per SHA-256
- [x] **Batch-Upload** – Tab „Batch": Multi-Select oder Verzeichnis (`webkitdirectory`); Titel + Typ automatisch aus Dateinamen erkannt; Duplikate werden übersprungen
- [x] **Upload-Fortschritt** – HTMX-Polling nach Upload: Status PROCESSING → READY/FAILED mit Badge-Aktualisierung
- [x] **Dokument-Detailseite** – Chunk-Liste (erste 50), Embedding-Status pro Chunk, Embedding-Abdeckungs-Fortschrittsbalken, Metadaten
- [x] **Dokument löschen** – `POST /ui/documents/<pk>/delete/` mit Bestätigungs-Template; Rollen-Schutz (analyst/admin)
- [x] **Fehleranzeige bei FAILED** – `Document.error_message`-Feld; rote Warnbox in Detailansicht + gekürzte Fehlermeldung in der Liste

### 11.4 Agent-Query-Interface

- [x] **Query-Formular** – Freitext-Eingabe + Absenden-Button; HTMX-POST an `/api/agent/query/`
- [x] **Antwort-Anzeige** – Answer-Text, Plan-Schritte, Tool-Calls als aufklappbare Akkordeons (Alpine.js)
- [x] **Streaming-Antwort** – SSE-Verbindung zu `/api/agent/stream/`; Chunks werden live in die Seite gestreamt
- [ ] **Query-Historie** – Letzte Anfragen der Session in der Sidebar anzeigen

### 11.5 Suche

- [x] **Suchmaske** – Freitext + Modus-Auswahl (hybrid / vector / fulltext / metadata); HTMX-GET an `/api/search/`
- [x] **Ergebnisliste** – Chunk-Text, Score, Dokument-Titel, Treffer-Highlight

### 11.6 Abschluss

- [ ] **`reembed_documents`-Trigger** – Admin-only Button im Dashboard startet Management-Command via Celery-Task
- [x] **Fehler-Seiten** – 403-Template vorhanden (`templates/ui/403.html`); 404/500 noch offen
- [ ] **Tests** – View-Tests für Dashboard, Upload, Query (mit Login-Fixture; kein Selenium nötig)
