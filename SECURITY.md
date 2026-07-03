# Security Policy

## Melden von Sicherheitslücken

Bitte Sicherheitslücken **nicht** über öffentliche GitHub Issues melden.
Stattdessen bitte über die [GitHub Security Advisories](../../security/advisories/new)
dieses Repositories melden, oder den Maintainer direkt kontaktieren.

Wir bemühen uns, innerhalb weniger Tage auf Meldungen zu reagieren.

## Bekannte Rahmenbedingungen

Dieses Projekt ist für den lokalen / On-Prem-Betrieb konzipiert:

- Das `seed_data`-Management-Command legt Demo-Benutzer mit fest
  hinterlegten, schwachen Passwörtern an (siehe [README.md](README.md)).
  Diese sind **ausschließlich für lokale Entwicklung und Tests** gedacht und
  dürfen niemals in einer produktiv erreichbaren oder öffentlich exponierten
  Instanz verwendet werden.
- `DJANGO_SECRET_KEY` und `DB_PASSWORD` müssen in jeder Umgebung individuell
  über `.env` gesetzt werden (siehe `.env.example`); es gibt keinen
  Hardcoded-Default.
- Für Produktionsbetrieb `DJANGO_SETTINGS_MODULE=config.settings.prod`
  verwenden (aktiviert HSTS, SSL-Redirect, Secure Cookies).
