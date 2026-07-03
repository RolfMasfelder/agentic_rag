# Contributing

Danke für dein Interesse an diesem Projekt.

## Entwicklungsumgebung

Siehe [README.md](README.md) für die Inbetriebnahme via Docker Compose.

## Workflow

1. Fork erstellen und Feature-Branch von `dev` abzweigen.
2. Änderungen vornehmen und lokal testen:
   ```bash
   ruff check .
   ruff format --check .
   pytest
   ```
3. Pull Request gegen `dev` öffnen. Der CI-Workflow (`.github/workflows/ci.yml`)
   muss grün sein (Lint + Tests).

## Commit-Konvention

`<prefix>: kurze Beschreibung` (eine Zeile, max. 72 Zeichen).
Erlaubte Prefixe: `feat`, `fix`, `refactor`, `docs`, `test`, `chore`.

## Code-Konventionen

- Agents dürfen die Datenbank ausschließlich über Funktionen in
  `django_root/agents/tools/` ansprechen, nie direkt über das Django-ORM oder
  Raw-SQL.
- Neue Tool-Funktionen als reine Python-Funktionen mit Type-Hints und
  Docstring, ohne Seiteneffekte außer DB-Zugriffen.
- Migrations: `migrate documents 0001` muss vor allen anderen Migrationen
  laufen, da sie die `vector`-Extension anlegt.

## Fragen / Probleme

Bitte über GitHub Issues melden.
