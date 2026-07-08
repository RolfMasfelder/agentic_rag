# Copilot Instructions – agentic_rag

## Git Remotes

| Remote   | Zweck                                      |
|----------|--------------------------------------------|
| `origin` | lokaler Mirror. |
| `github` | auf Github werden CI/CD-Pipelines ausgelöst. Speziell Dependabot und CodeQL laufen auf Github. |

Pushen immer zu beiden remotes, sowohl zu `origin` als auch zu `github` pushen (`origin` zuerst).

Der Workflow im Projekt ist: Feature-Branch erstellen / branch dev nutzen → lokal entwickeln → `ruff check .` und `pytest` ausführen → Commit → Push zu beiden Remotes → PR auf Github → CI/CD-Pipeline auf Github läuft → Merge in `main`
kommt später: Deployment auf Testsystem (Staging) → manuelles Testen → Merge in `prod` → Deployment auf Produktionssystem.

Commit-Format: `<prefix>: kurze Beschreibung auf Englisch` (eine Zeile, maximal 72 Zeichen). Erlaubte Prefixe: `feat` (neue Funktion), `fix` (Bugfix), `refactor` (Umstrukturierung ohne Verhaltensänderung), `docs`, `test`, `chore`. Bei Unsicherheit `chore` verwenden.

## Projektüberblick

Hybrid Agentic RAG System – lokales KI-Analyse- und Retrieval-System.
Vollständige Spezifikation: `docs/Zusammenfassung.txt`.

## Stack

- **Python 3.13**, Django 5.1, Django REST Framework
- **PostgreSQL 17** + pgvector (Vektorsuche)
- **Redis** + Celery (Hintergrundjobs)
- **Ollama** läuft auf einem separaten Netzwerkrechner (`OLLAMA_BASE_URL` in `.env`); wenn nicht erreichbar, Nutzer informieren und keine Fallback-LLM-Aufrufe versuchen
- Docker Compose als primäre Laufzeitumgebung (UID 1234:1234 in Containern); `Dockerfile` und `docker-compose.yml` liegen in `docker/`; Aufruf: `docker compose -f docker/docker-compose.yml --env-file .env …`; Django-Code liegt in `django_root/` (PYTHONPATH=/app/django_root im Container)

## Konventionen

- Beim Generieren von Agent-Code: Agents dürfen die DB nur über Funktionen in `agents/tools/` ansprechen, niemals direkt über Django ORM oder raw SQL. Neue Tool-Funktionen als reine Python-Funktionen mit Type-Hints und Docstring in `django_root/agents/tools/<domain>.py` ablegen; keine Seiteneffekte außer DB-Zugriffen.
- Einstellungen: `django_root/config/settings/base.py` (gemeinsam), `dev.py`, `prod.py`
- `.env` wird nur geladen wenn vorhanden – CI setzt Env-Variablen direkt; bei fehlender `.env` außerhalb von CI: Nutzer warnen und auf `.env.example` als Vorlage verweisen
- Linting: `ruff` (Konfiguration in `pyproject.toml`); vor jedem Commit `ruff check .` und `pytest` ausführen. Bei nicht-null Exit-Code eines der beiden Befehle nicht committen und Nutzer informieren. Bei auto-fixbaren Ruff-Issues niemals automatisch `--fix` ausführen; stattdessen Nutzer informieren und auf Bestätigung warten.
- Tests: `pytest` + `pytest-django` (`requirements-dev.txt`). DB-unabhängige Tests bevorzugt lokal im Projekt-venv ausführen. Für DB-abhängige Tests (`test_api.py`, `test_e2e.py`) niemals Dev-Dependencies in den persistenten `web`/`worker`-Service installieren (z. B. via `docker compose exec ... pip install`) – das Prod-Image bleibt sonst dauerhaft mit Dev-Tools verunreinigt. Stattdessen einen einmaligen, danach automatisch verworfenen Container verwenden: `docker compose -f docker/docker-compose.yml --env-file .env run --rm web bash -c "pip install -q -r requirements-dev.txt && python -m pytest django_root/tests/test_api.py -v"`
- Migrations: Wenn die Datenbank leer ist oder die `vector`-Extension noch nicht existiert, zuerst `migrate documents 0001` ausführen (erstellt die `vector`-Extension); danach für neue Modelländerungen `makemigrations` und `migrate`
- Dokumentation immer in `docs/` ablegen
- Skripte immer in `scripts/` ablegen – Ausnahme: Installations- und Docker-Hilfsskripte gehören in `docker/`
