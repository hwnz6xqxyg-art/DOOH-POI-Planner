# DOOH POI Planner

A geo-proximity planning tool for Digital-out-of-Home (DOOH). Upload your DOOH screen
inventory, **discover Points of Interest from OpenStreetMap** — branded POS (e.g. Rossmann),
airports, gyms, universities — select them as **anchors**, set a radius, and get every screen
within range of any selected POI: deduped, mapped, counted, and exportable.

It is the successor to the **DOOH Shop Connector** (a single-file tool fixed to a Telekom shop
list). This version keeps the inventory upload, proximity matching, and export, and **replaces
the fixed shop list with on-demand OSM POI discovery** (brand search, category picker,
draw-an-area, attribute filters). Geography: **DACH (DE/AT/CH)**.

> Full specification: **[`SPEC.md`](./SPEC.md)**. Donor tool kept under
> [`reference/`](./reference/) for the reused plumbing.

## Architecture

Runs locally, single user, no auth (SPEC §12). `docker compose up` on one machine.

| Service | What |
|---|---|
| **db** | PostGIS — OSM `poi` + uploaded DOOH `screen` tables |
| **api** | FastAPI — discovery, inventory ingest, `ST_DWithin` matching, CSV export |
| **web** | Vite + TypeScript + Leaflet SPA (dark map, discovery panels, plan card) |
| **etl** | pyosmium importer: Geofabrik `.osm.pbf` → normalized `poi` table |

## Quick start

```bash
# 1. start the stack (db + api + web) on localhost
make up                      # == docker compose up -d --build

# 2. load OSM POIs — download Geofabrik extracts into ./data first, e.g.
#    https://download.geofabrik.de/europe/germany-latest.osm.pbf  -> ./data/
make etl-de                  # repeat: make etl-at / make etl-ch

# 3. open the app
open http://localhost:8080
```

Upload a DOOH inventory file (`.xlsx`/`.csv`) in the right panel (Ströer & WallDecaux/VIOOH
column layouts auto-detect; confirm the mapping). Then discover POIs on the left (brand /
category / area / attribute), click POIs to make them anchors, set the radius, and export the
screens in range.

## Development (without Docker)

```bash
# Postgres 16 + PostGIS reachable as DATABASE_URL; then:
cd api
python -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
psql "$DATABASE_URL" -f db/schema.sql
python -m etl.import_osm --pbf tests/sample.osm --country de   # tiny sample fixture
uvicorn app.main:app --reload                                  # :8000

cd ../web
npm install
npm run dev                  # :5173, proxies /api -> :8000
```

## Tests

```bash
cd api && python -m pytest -q          # taxonomy + ingest unit tests
cd web && npm run build                # typecheck + bundle
```

## Verification status

End-to-end verified against a real PostGIS instance:

- ✅ ETL imports the sample OSM fixture (nodes + way-centroid), normalizes categories.
- ✅ Discovery: brand search, category counts, bbox/polygon area, attribute filters.
- ✅ Inventory: server-side `.xlsx`/`.csv` parse, Ströer/Wall auto-detect, EU-comma coords,
  replace-by-partner accumulation.
- ✅ Matching: `ST_DWithin` union, dedupe (screen counted once), per-anchor radius override,
  coverage %.
- ✅ Export: `;`-delimited UTF-8 (BOM) CRLF CSV (German Excel) + per-partner round-trip layout.
- ✅ SPA builds and runs in a browser, wired to the live API.

## Project layout

```
SPEC.md                  # build specification
docker-compose.yml       # db + api + web (+ etl one-shot)
api/                     # FastAPI + PostGIS + pyosmium ETL
  app/                   #   routers, ingest (donor port), taxonomy, matching
  etl/import_osm.py      #   OSM .pbf -> poi
  db/schema.sql          #   PostGIS schema
  tests/                 #   unit tests + sample.osm fixture
web/                     # Vite + TS + Leaflet SPA
reference/               # donor DOOH Shop Connector (reused logic)
data/                    # drop Geofabrik .osm.pbf extracts here (gitignored)
```
