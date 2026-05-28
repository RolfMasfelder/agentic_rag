# Copilot Instructions – agentic_rag

## Git Remotes

| Remote   | Zweck                                      |
|----------|--------------------------------------------|
| `origin` | Bei jedem vom Nutzer ausgelösten Push-Befehl ohne explizite Remote-Angabe immer nach `origin` pushen. Niemals automatisch ohne expliziten Nutzerbefehl pushen. Bei Push-Fehler keinerlei Retry ausführen, keinen lokalen Commit zurücknehmen, und genau eine Fehlermeldung mit dem Git-Output an den Nutzer geben. |
| `github` | Nur pushen, wenn der Nutzer das Wort "github" oder "GitHub" explizit im Push-Befehl nennt. Dann sowohl zu `origin` als auch zu `github` pushen (`origin` zuerst). |

Commit-Format: `<prefix>: kurze Beschreibung auf Englisch` (eine Zeile, maximal 72 Zeichen). Erlaubte Prefixe: `feat` (neue Funktion), `fix` (Bugfix), `refactor` (Umstrukturierung ohne Verhaltensänderung), `docs`, `test`, `chore`. Bei Unsicherheit `chore` verwenden.

## Projektüberblick

Hybrid Agentic RAG System – lokales KI-Analyse- und Retrieval-System.
Vollständige Spezifikation: `docs/Zusammenfassung.txt`.

## Stack

- **Python 3.13**, Django 5.1, Django REST Framework
- **PostgreSQL 17** + pgvector (Vektorsuche)
- **Redis** + Celery (Hintergrundjobs)
- **Ollama** läuft auf einem separaten Netzwerkrechner (`OLLAMA_BASE_URL` in `.env`); wenn nicht erreichbar, Nutzer informieren und keine Fallback-LLM-Aufrufe versuchen
- Docker Compose als primäre Laufzeitumgebung (UID 1234:1234 in Containern); `Dockerfile` und `docker-compose.yml` liegen in `docker/`; Aufruf: `docker compose -f docker/docker-compose.yml …`

## Konventionen

- Beim Generieren von Agent-Code: Agents dürfen die DB nur über Funktionen in `agents/tools/` ansprechen, niemals direkt über Django ORM oder raw SQL. Neue Tool-Funktionen als reine Python-Funktionen mit Type-Hints und Docstring in `agents/tools/<domain>.py` ablegen; keine Seiteneffekte außer DB-Zugriffen.
- Einstellungen: `config/settings/base.py` (gemeinsam), `dev.py`, `prod.py`
- `.env` wird nur geladen wenn vorhanden – CI setzt Env-Variablen direkt; bei fehlender `.env` außerhalb von CI: Nutzer warnen und auf `.env.example` als Vorlage verweisen
- Linting: `ruff` (Konfiguration in `pyproject.toml`); vor jedem Commit `ruff check .` und `pytest` ausführen. Bei nicht-null Exit-Code eines der beiden Befehle nicht committen und Nutzer informieren. Bei auto-fixbaren Ruff-Issues niemals automatisch `--fix` ausführen; stattdessen Nutzer informieren und auf Bestätigung warten.
- Tests: `pytest` + `pytest-django` (`requirements-dev.txt`)
- Migrations: Wenn die Datenbank leer ist oder die `vector`-Extension noch nicht existiert, zuerst `migrate documents 0001` ausführen (erstellt die `vector`-Extension); danach für neue Modelländerungen `makemigrations` und `migrate`
- Dokumentation immer in `docs/` ablegen
- Skripte immer in `scripts/` ablegen – Ausnahme: Installations- und Docker-Hilfsskripte gehören in `docker/`
