#!/usr/bin/env bash
# docker/build-docker.sh
#
# Vollständiger Build- und Initialisierungs-Workflow für Agentic RAG.
# Führt alle Schritte in der richtigen Reihenfolge aus:
#
#   1. .env prüfen
#   2. Container bauen  (--no-cache optional via --fresh)
#   3. DB + Redis starten und auf Healthcheck warten
#   4. Django-Migrationen ausführen
#   5. Demo-Daten laden  (seed_data, idempotent)
#   6. Web + Worker starten
#
# Verwendung:
#   cd /pfad/zu/agentic_rag        # Repo-Wurzel
#   ./docker/build-docker.sh
#   ./docker/build-docker.sh --fresh   # ohne Build-Cache
#   ./docker/build-docker.sh --no-seed # Demo-Daten überspringen
#
# Voraussetzungen:
#   - Docker >= 24 mit Compose V2 (docker compose)
#   - .env Datei im Repo-Wurzelverzeichnis (Vorlage: .env.example)

set -euo pipefail

# ── Farben ────────────────────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; CYAN='\033[0;36m'; NC='\033[0m'
info()    { echo -e "${CYAN}[INFO]${NC}  $*"; }
success() { echo -e "${GREEN}[OK]${NC}    $*"; }
warn()    { echo -e "${YELLOW}[WARN]${NC}  $*"; }
error()   { echo -e "${RED}[ERROR]${NC} $*" >&2; exit 1; }

# ── Argumente ─────────────────────────────────────────────────────────────────
FRESH=false
SEED=true
for arg in "$@"; do
  case "$arg" in
    --fresh)   FRESH=true ;;
    --no-seed) SEED=false ;;
    --help|-h)
      sed -n '/^# Verwendung/,/^#$/p' "$0" | sed 's/^# \?//'
      exit 0 ;;
    *) error "Unbekannter Parameter: $arg  (--fresh | --no-seed | --help)" ;;
  esac
done

# ── Pfade ─────────────────────────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"
COMPOSE="docker compose -f $SCRIPT_DIR/docker-compose.yml --env-file $REPO_ROOT/.env"
MANAGE="$COMPOSE exec web bash -c 'PYTHONPATH=/app/django_root DJANGO_SETTINGS_MODULE=config.settings.dev python /app/django_root/manage.py"

cd "$REPO_ROOT"

# ── 0. Voraussetzungen prüfen ─────────────────────────────────────────────────
info "Prüfe Voraussetzungen…"
command -v docker >/dev/null 2>&1 || error "docker nicht gefunden."
docker compose version >/dev/null 2>&1 || error "Docker Compose V2 nicht gefunden."

if [[ ! -f "$REPO_ROOT/.env" ]]; then
  if [[ -f "$REPO_ROOT/.env.example" ]]; then
    warn ".env fehlt – kopiere .env.example → .env"
    cp "$REPO_ROOT/.env.example" "$REPO_ROOT/.env"
    error "Bitte .env anpassen (DB_PASSWORD, DJANGO_SECRET_KEY, OLLAMA_BASE_URL) und erneut ausführen."
  else
    error ".env fehlt und kein .env.example vorhanden."
  fi
fi
success ".env gefunden."

# ── 1. Container bauen ────────────────────────────────────────────────────────
info "Baue Container…"
if $FRESH; then
  warn "--fresh: Build-Cache wird ignoriert."
  $COMPOSE build --no-cache
else
  $COMPOSE build
fi
success "Container gebaut."

# ── 2. DB + Redis starten und warten ─────────────────────────────────────────
info "Starte DB und Redis…"
$COMPOSE up -d db redis

info "Warte auf Healthchecks (DB + Redis)…"
RETRIES=30
for i in $(seq 1 $RETRIES); do
  DB_ID=$($COMPOSE ps -q db 2>/dev/null || true)
  REDIS_ID=$($COMPOSE ps -q redis 2>/dev/null || true)
  DB_HEALTH=$(docker inspect --format='{{.State.Health.Status}}' "$DB_ID" 2>/dev/null || echo "unknown")
  REDIS_HEALTH=$(docker inspect --format='{{.State.Health.Status}}' "$REDIS_ID" 2>/dev/null || echo "unknown")
  if [[ "$DB_HEALTH" == "healthy" && "$REDIS_HEALTH" == "healthy" ]]; then
    success "DB und Redis sind bereit."
    break
  fi
  if [[ $i -eq $RETRIES ]]; then
    $COMPOSE ps
    error "Timeout: DB oder Redis nicht bereit. Bitte Logs prüfen: docker compose -f docker/docker-compose.yml logs db redis"
  fi
  echo -n "."
  sleep 2
done

# ── 3. Migrationen ────────────────────────────────────────────────────────────
info "Führe Django-Migrationen aus…"
$COMPOSE run --rm \
  -e PYTHONPATH=/app/django_root \
  -e DJANGO_SETTINGS_MODULE=config.settings.dev \
  web python django_root/manage.py migrate --run-syncdb
success "Migrationen abgeschlossen."

# ── 4. Demo-Daten ─────────────────────────────────────────────────────────────
if $SEED; then
  info "Lade Demo-Daten (seed_data)…"
  $COMPOSE run --rm \
    -e PYTHONPATH=/app/django_root \
    -e DJANGO_SETTINGS_MODULE=config.settings.dev \
    web python django_root/manage.py seed_data
  success "Demo-Daten geladen."
else
  warn "--no-seed: Demo-Daten werden übersprungen."
fi

# ── 5. Alle Services starten ──────────────────────────────────────────────────
info "Starte alle Services (web, worker)…"
$COMPOSE up -d
success "Alle Container laufen."

# ── Zusammenfassung ───────────────────────────────────────────────────────────
echo ""
echo -e "${GREEN}═══════════════════════════════════════════════════${NC}"
echo -e "${GREEN}  Agentic RAG ist gestartet!${NC}"
echo -e "${GREEN}═══════════════════════════════════════════════════${NC}"
echo ""
echo -e "  Browser-UI:   ${CYAN}http://localhost:8001/ui/${NC}"
echo -e "  Django-Admin: ${CYAN}http://localhost:8001/admin/${NC}"
echo -e "  REST-API:     ${CYAN}http://localhost:8001/api/${NC}"
echo ""
if $SEED; then
  echo -e "  Demo-Benutzer:"
  echo -e "    ${CYAN}admin${NC}   / admin123    (admin + Django-Superuser)"
  echo -e "    ${CYAN}analyst${NC} / analyst123  (Dokumente hochladen & löschen)"
  echo -e "    ${CYAN}viewer${NC}  / viewer123   (nur lesen)"
  echo ""
fi
echo -e "  Logs:  docker compose -f docker/docker-compose.yml logs -f"
echo -e "  Stop:  docker compose -f docker/docker-compose.yml down"
echo ""
