# Copilot Instructions – agentic_rag

## Git Remotes

| Remote   | Zweck                                      |
|----------|--------------------------------------------|
| `origin` | Lokaler Git-Server (immer pushen); bei Fehler melden und auf Nutzeranweisung warten – nicht automatisch zu `github` pushen |
| `github` | Nur pushen, wenn der Nutzer das Wort "github" oder "GitHub" explizit im Push-Befehl nennt |

Commit-Format: `<prefix>: kurze Beschreibung` (eine Zeile). Erlaubte Prefixe: `feat` (neue Funktion), `fix` (Bugfix), `refactor` (Umstrukturierung ohne Verhaltensänderung), `docs`, `test`, `chore`. Bei Unsicherheit `chore` verwenden.

## Projektüberblick

Hybrid Agentic RAG System – lokales KI-Analyse- und Retrieval-System.
Vollständige Spezifikation: `Zusammenfassung.txt`.

## Stack

- **Python 3.13**, Django 5.1, Django REST Framework
- **PostgreSQL 17** + pgvector (Vektorsuche)
- **Redis** + Celery (Hintergrundjobs)
- **Ollama** läuft auf einem separaten Netzwerkrechner (`OLLAMA_BASE_URL` in `.env`)
- Docker Compose als primäre Laufzeitumgebung (UID 1234:1234 in Containern)

## Konventionen

- Beim Generieren von Agent-Code: Agents dürfen die DB nur über Funktionen in `agents/tools/` ansprechen, niemals direkt über Django ORM oder raw SQL
- Einstellungen: `config/settings/base.py` (gemeinsam), `dev.py`, `prod.py`
- `.env` wird nur geladen wenn vorhanden – CI setzt Env-Variablen direkt; bei fehlender `.env` außerhalb von CI: Nutzer warnen und auf `.env.example` als Vorlage verweisen
- Linting: `ruff` (Konfiguration in `pyproject.toml`); vor jedem Commit `ruff check .` und `pytest` ausführen – bei Fehlern nicht committen
- Tests: `pytest` + `pytest-django` (`requirements-dev.txt`)
- Migrations: Bei der initialen Einrichtung zuerst `migrate apps.documents 0001` ausführen (erstellt die `vector`-Extension); danach für neue Modelländerungen `makemigrations` und `migrate`
- Dokumentation immer in `docs/` ablegen
- Skripte immer in `scripts/` ablegen
