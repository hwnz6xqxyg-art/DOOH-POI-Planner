#!/usr/bin/env bash
#
# Import a real OSM extract into the local (no-Docker) database.
# Download extracts from Geofabrik, e.g.
#   https://download.geofabrik.de/europe/germany-latest.osm.pbf
#
# Usage:
#   scripts/etl-local.sh ~/Downloads/germany-latest.osm.pbf de
#   scripts/etl-local.sh ~/Downloads/austria-latest.osm.pbf at
#
set -euo pipefail
cd "$(dirname "$0")/.."
PBF="${1:?usage: scripts/etl-local.sh <file.osm.pbf> <country: de|at|ch>}"
COUNTRY="${2:?country required (de | at | ch)}"
[ -f "$PBF" ] || { echo "File not found: $PBF"; exit 1; }

cd api
[ -d .venv ] || { echo "Run scripts/run-local.sh first (sets up the venv + db)."; exit 1; }
# shellcheck disable=SC1091
. .venv/bin/activate
export DATABASE_URL="${DATABASE_URL:-postgresql://localhost:5432/dooh}"
exec python -m etl.import_osm --pbf "$PBF" --country "$COUNTRY"
