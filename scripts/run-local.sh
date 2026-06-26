#!/usr/bin/env bash
#
# DOOH POI Planner — run locally on macOS WITHOUT Docker.
#
# Installs PostGIS + Python 3.11 + Node via Homebrew (if missing), starts
# PostgreSQL, sets up the `dooh` database, loads the bundled sample POIs, builds
# the web app, and serves the whole thing (API + SPA) at http://localhost:8000.
#
# Re-runnable: it skips anything already done. Real OSM data: after the first
# run, use scripts/etl-local.sh <file.osm.pbf> <country>.
#
set -uo pipefail
cd "$(dirname "$0")/.."
ROOT="$(pwd)"
say() { printf "\n\033[1;35m▶ %s\033[0m\n" "$*"; }
die() { printf "\n\033[1;31m✖ %s\033[0m\n" "$*" >&2; exit 1; }

# --- 0. Homebrew ------------------------------------------------------------
command -v brew >/dev/null || die "Homebrew is required. Install it from https://brew.sh and re-run."

# --- 1. dependencies --------------------------------------------------------
say "Checking Homebrew packages (postgis · python@3.11 · node)…"
brew list postgis     >/dev/null 2>&1 || brew install postgis     || die "brew install postgis failed."
brew list python@3.11 >/dev/null 2>&1 || brew install python@3.11 || die "brew install python@3.11 failed."
brew list node        >/dev/null 2>&1 || brew install node        || die "brew install node failed."

# --- 2. PostgreSQL/PostGIS service -----------------------------------------
# Find the actual psql on disk. Prefer the PostgreSQL whose extension dir has
# postgis.control (authoritative: that's the one PostGIS is installed into),
# else any Homebrew PostgreSQL. Avoids brittle parsing of brew output.
pick_pg() {
  local cand share
  for cand in /opt/homebrew/opt/postgresql@*/bin /opt/homebrew/opt/postgresql/bin \
              /usr/local/opt/postgresql@*/bin /usr/local/opt/postgresql/bin; do
    [ -x "$cand/psql" ] || continue
    share="$("$cand/pg_config" --sharedir 2>/dev/null)"
    [ -n "$share" ] && [ -f "$share/extension/postgis.control" ] && { echo "$cand"; return 0; }
  done
  for cand in /opt/homebrew/opt/postgresql@*/bin /opt/homebrew/opt/postgresql/bin \
              /usr/local/opt/postgresql@*/bin /usr/local/opt/postgresql/bin; do
    [ -x "$cand/psql" ] && { echo "$cand"; return 0; }
  done
  return 1
}
say "Locating PostgreSQL (with PostGIS)…"
PGBIN="$(pick_pg || true)"
if [ -z "$PGBIN" ]; then
  brew install postgis || die "brew install postgis failed."   # pulls the right postgresql
  PGBIN="$(pick_pg || true)"
fi
[ -n "$PGBIN" ] && [ -x "$PGBIN/psql" ] || die "Could not find a Homebrew PostgreSQL on disk. Try: brew install postgis"
PGF="$(basename "$(dirname "$PGBIN")")"   # keg dir name, e.g. postgresql@14
echo "   → $PGF ($PGBIN)"

say "Starting $PGF…"
brew services start "$PGF" >/dev/null 2>&1 || true
for i in $(seq 1 30); do "$PGBIN/pg_isready" -q -h localhost 2>/dev/null && break; sleep 1; done
"$PGBIN/pg_isready" -q -h localhost 2>/dev/null || die "PostgreSQL did not start. Check: brew services list"

# --- 3. database ------------------------------------------------------------
say "Ensuring database 'dooh' + PostGIS extensions…"
"$PGBIN/createdb" dooh 2>/dev/null || true   # ok if it already exists
"$PGBIN/psql" -d dooh -v ON_ERROR_STOP=1 \
  -c "CREATE EXTENSION IF NOT EXISTS postgis; CREATE EXTENSION IF NOT EXISTS pg_trgm;" >/dev/null \
  || die "Could not enable PostGIS on the 'dooh' database."
export DATABASE_URL="postgresql://localhost:5432/dooh"

# --- 4. python backend ------------------------------------------------------
say "Setting up the Python backend…"
cd "$ROOT/api" || die "api/ directory missing."
PY="$(brew --prefix python@3.11 2>/dev/null)/bin/python3.11"; [ -x "$PY" ] || PY="python3"
[ -d .venv ] || "$PY" -m venv .venv || die "Could not create the Python venv with $PY."
# shellcheck disable=SC1091
. .venv/bin/activate || die "Could not activate the venv."
pip install -q --upgrade pip || true
pip install -q -r requirements.txt \
  || die "Backend deps failed. Most likely 'osmium' has no wheel for your Python; this script targets python@3.11 which normally does. Re-run after: brew install python@3.11"
"$PGBIN/psql" -d dooh -v ON_ERROR_STOP=1 -f db/schema.sql >/dev/null || die "Applying db/schema.sql failed."

# --- 5. sample data (only if the poi table is empty) ------------------------
COUNT="$("$PGBIN/psql" -d dooh -tAc 'SELECT count(*) FROM poi' 2>/dev/null || echo 0)"
if [ "${COUNT:-0}" -eq 0 ]; then
  say "Importing the bundled sample POIs (tests/sample.osm)…"
  python -m etl.import_osm --pbf tests/sample.osm --country de || die "Sample ETL import failed."
else
  say "POIs already loaded ($COUNT) — skipping sample import."
fi

# --- 6. web build -----------------------------------------------------------
say "Building the web app…"
cd "$ROOT/web" || die "web/ directory missing."
[ -d node_modules ] || npm install || die "npm install failed."
npm run build || die "npm run build failed."

# --- 7. serve API + SPA on one port ----------------------------------------
cd "$ROOT/api"
export WEB_DIR="$ROOT/web/dist"
say "Ready → open http://localhost:8000     (Ctrl+C to stop)"
exec uvicorn app.main:app --host 127.0.0.1 --port 8000
