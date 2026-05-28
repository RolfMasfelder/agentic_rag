# TODO – Hybrid Agentic RAG System

Abgleich mit `Zusammenfassung.txt`. Stand: 2026-05-28.

---

## 1. Parser & Dokumentverarbeitung

- [ ] **XML/XSD-Parser** – `FileType.XML` vorhanden, Parser fehlt
- [ ] **OpenAPI-Parser** – `FileType.OPENAPI` vorhanden, Parser fehlt
- [ ] **Code-Parser** – `FileType.CODE` vorhanden, Parser fehlt (Klassen/Funktionen extrahieren)
- [ ] **Plain-Text-Parser** – `FileType.TEXT` vorhanden, Parser fehlt
- [ ] **OCR-Integration** – PaddleOCR oder Tesseract für gescannte PDFs (in `Zusammenfassung.txt` erwähnt)

## 2. Chunking

- [ ] **XML-bewusstes Chunking** – `chunk_type=xml_block` deklariert, aber nie erzeugt
- [ ] **Code-bewusstes Chunking** – `chunk_type=function/class` deklariert, Extraktion fehlt
- [ ] **Klausel-Extraktion** – `chunk_type=clause` für Verträge deklariert, nicht implementiert

## 3. REST-API – fehlende Endpunkte

- [ ] **Agent-Endpunkt** – `POST /api/agent/query/` ruft `run_agent()` auf und gibt Antwort + Quellen zurück
- [ ] **Such-Endpunkt** – `GET /api/search/` (hybrid, vector, fulltext, metadata) als REST-Endpoint
- [ ] **Analyse-Endpunkt** – CRUD für `AnalysisResult` (Modell vorhanden, keine Views)
- [ ] **Relation-Erstellung** – `DocumentRelation` kann nur gelesen, nicht per API erstellt werden
- [ ] **Batch-Import** – Mehrere Dokumente in einem Request hochladen und verarbeiten

## 4. Retrieval

- [ ] **Graph-Traversal** – Mehrstufige Beziehungssuche (Dokument → Relationen → Relationen)
- [ ] **Dokument-Ähnlichkeit** – Semantische Ähnlichkeit auf Dokumentebene (nicht nur Chunks)
- [ ] **Re-Ranking** – Ergebnisse nach einem zweiten Schritt neu sortieren (z. B. Cross-Encoder)
- [ ] **Query-Expansion** – Synonyme / verwandte Begriffe automatisch ergänzen

## 5. Agentische Architektur

- [ ] **Tool-Schema-Validierung** – Parameter-Validierung vor Ausführung (aktuell: direktes JSON-Parsing ohne Schema)
- [ ] **Context-Window-Management** – Gesprächsverlauf kürzen wenn Tokenlimit überschritten wird
- [ ] **Iterativer Retrieval-Plan** – Agent soll Suchschritte explizit planen statt nur zu loopen
- [ ] **Agent-Task via Celery** – Lang laufende Agent-Anfragen asynchron ausführen (in `Zusammenfassung.txt` erwähnt)

## 6. LLM-Client

- [ ] **Streaming** – `ollama.Client` unterstützt Streaming; für lange Antworten nutzbar
- [ ] **Prompt-Templates** – Wiederverwendbare Templates für Analyse, Zusammenfassung, Retrieval-Steuerung
- [ ] **Fallback-Modell** – AlternativersModell wenn primäres Modell nicht verfügbar

## 7. Sicherheit & Berechtigungen

- [ ] **Rollen-Enforcement** – `ADMIN/ANALYST/VIEWER`-Rollen vorhanden, aber DRF-Permissions prüfen nicht die Rolle
- [ ] **Objekt-Level-Permissions** – Nutzer soll nur eigene Dokumente sehen/bearbeiten können (oder Admin alle)
- [ ] **Token-Authentifizierung** – Für API-Clients ohne Session (DRF `TokenAuthentication` oder JWT)

## 8. Tests

- [ ] **Unit-Tests Parser** – PDF-, Markdown-Parser testen
- [ ] **Unit-Tests Chunker** – ParagraphChunker mit Edge Cases (leere Texte, sehr lange Texte)
- [ ] **Unit-Tests Retrieval** – vector_search, fulltext_search, hybrid_search mocken und testen
- [ ] **Integration-Tests API** – DocumentViewSet-Endpunkte mit Test-DB testen
- [ ] **Agent-Tests** – Orchestrator mit Mock-LLM und Mock-Tools testen

## 9. Infrastruktur & Betrieb

- [x] **Datenbankmigrationen ausführen** – `migrate documents 0001` + `migrate` erledigt
- [x] **`createsuperuser`** – Admin-Nutzer `admin` angelegt
- [x] **`.env` aus `.env.example` anlegen** – `DJANGO_SECRET_KEY`, `DB_PASSWORD`, `OLLAMA_BASE_URL` gesetzt
- [x] **Gesundheitsprüfung** – `/health/`-Endpunkt angelegt (`config/urls.py`)
- [x] **Logging-Konfiguration** – Strukturiertes Logging in `base.py`; JSON-Format für Produktion in `prod.py`

## 10. Testdaten (laut Zusammenfassung.txt)

- [ ] Beispiel-PDFs besorgen (Gesetzestexte, RFCs, Beispielverträge) → `data/`
- [ ] OpenAPI-Specs als Testdokumente → `data/`
- [ ] XML/XSD-Beispieldateien → `data/`
- [ ] Markdown-Dokumentationen (z. B. Open-Source-Projekte) → `data/`

> `data/` ist in `.gitignore` eingetragen (nur `.gitkeep` wird versioniert).
