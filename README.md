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

## Two ways to run it

**A. Standalone — no install, just double-click.** Open
**[`standalone/index.html`](./standalone/index.html)** in your browser (double-click it in
Finder). No Docker, no Postgres, no terminal. It discovers POIs live from the OpenStreetMap
**Overpass API** and does everything (upload, matching, export) in the browser. This is the
easiest path and what most people want — see **[Standalone](#standalone-double-click)** below.

**B. Full stack (PostGIS backend).** For nationwide bulk OSM data and server-side matching,
run the FastAPI + PostGIS stack via Docker or natively — see [Architecture](#architecture)
and the run sections further down.

| | Standalone (A) | Full stack (B) |
|---|---|---|
| Setup | none — open a file | Docker **or** Homebrew/Postgres |
| POI data | live Overpass, per map view | whole DACH pre-imported (Geofabrik) |
| Matching | in browser | PostGIS `ST_DWithin` |
| Best for | getting going, single campaigns | large/repeated nationwide planning |

## Standalone (double-click)

1. Open `standalone/index.html` in a browser (double-click in Finder, or drag it onto the
   browser). Needs internet for the map + OpenStreetMap queries.
2. **Upload your DOOH inventory** (right panel) — any `.xlsx`/`.csv` with ID + lat/lng
   columns; Ströer/WallDecaux layouts auto-detect, confirm the mapping.
3. **Discover POIs** (left panel): zoom the map to your target area, tick categories and/or
   add brands (e.g. *Rossmann*), then **"POIs im Kartenausschnitt suchen"**.
4. Click POIs to make them **anchors** (or "Alle als Anker"), set the radius, and the plan
   card shows screens in range + coverage. **Export CSV** for the matched screens.

It's a single self-contained file (Leaflet is inlined). Inventory persists in the browser
when possible; opened via `file://` it may be session-only, which is fine for one-off planning.

## Architecture

Runs locally, single user, no auth (SPEC §12). `docker compose up` on one machine.

| Service | What |
|---|---|
| **db** | PostGIS — OSM `poi` + uploaded DOOH `screen` tables |
| **api** | FastAPI — discovery, inventory ingest, `ST_DWithin` matching, CSV export |
| **web** | Vite + TypeScript + Leaflet SPA (dark map, discovery panels, plan card) |
| **etl** | pyosmium importer: Geofabrik `.osm.pbf` → normalized `poi` table |

## Quick start

**Prerequisite: Docker Desktop must be installed and running** (`docker --version` should
work). On macOS: `brew install --cask docker` then launch Docker Desktop, or download it from
<https://www.docker.com/products/docker-desktop>.

```bash
# 1. start the stack (db + api + web) on localhost
make up                      # == docker compose up -d --build

# 2a. quick smoke test — import the bundled 5-POI sample (no download)
make etl-sample
open http://localhost:8080   # you should see 5 POIs; search + select to match

# 2b. real data — download Geofabrik extracts into ./data first, e.g.
#     https://download.geofabrik.de/europe/germany-latest.osm.pbf  -> ./data/
make etl-de                  # repeat: make etl-at / make etl-ch
```

Upload a DOOH inventory file (`.xlsx`/`.csv`) in the right panel (Ströer & WallDecaux/VIOOH
column layouts auto-detect; confirm the mapping). Then discover POIs on the left (brand /
category / area / attribute), click POIs to make them anchors, set the radius, and export the
screens in range.

## Run without Docker (macOS) — recommended if Docker is giving you grief

One command sets up PostGIS + Python + Node via Homebrew, loads the sample POIs,
and serves the whole app (API **and** UI) on a single port:

```bash
make local            # == ./scripts/run-local.sh
open http://localhost:8000
```

It's re-runnable (skips anything already done). Requires [Homebrew](https://brew.sh);
it installs `postgis`, `python@3.11`, and `node` for you and starts PostgreSQL via
`brew services`. Stop the app with Ctrl+C (PostgreSQL keeps running as a brew service —
`brew services stop postgresql@<v>` to stop it).

Load real OSM data after the first run:

```bash
# download e.g. https://download.geofabrik.de/europe/germany-latest.osm.pbf
./scripts/etl-local.sh ~/Downloads/germany-latest.osm.pbf de    # then at / ch
```

## Development (without Docker, manual)

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

## Lizenz & Attribution

**The tool is free for commercial use.** The code is **MIT-licensed**
([`LICENSE`](./LICENSE)); every bundled library, data source, and service it relies on
is free of charge including commercial use — full license texts in
[`THIRD_PARTY_NOTICES.md`](./THIRD_PARTY_NOTICES.md), summary in the app's **"Lizenzen"**
link (top right):

| Component | License | Obligation |
|---|---|---|
| DOOH POI Planner (this code) | MIT | keep the copyright notice |
| Leaflet 1.9.4 (inlined) | BSD-2-Clause | notice retained in the file |
| Leaflet.markercluster 1.5.3 (inlined) | MIT | notice retained in the file |
| MapLibre GL JS 5.24.0 (inlined) | BSD-3-Clause | notice retained in the file |
| maplibre-gl-leaflet 0.1.3 (inlined) | ISC | notice retained in the file |
| POI data (OpenStreetMap via Overpass) | ODbL 1.0 | attribution "© OpenStreetMap contributors" — shown on the map and in the POI XLSX export |
| Basemap ("Positron" style via OpenFreeMap) | free incl. commercial, keyless | attribution "OpenFreeMap · © OpenMapTiles · © OpenStreetMap" — shown on the map |
| Raster fallback (OSM standard tiles) | ODbL data, OSMF fair-use service | attribution shown on the map; light interactive use only |

Notes for re-hosting / heavy use:

- Keep the map attribution control visible (it carries the required attributions).
- The public **Overpass API** servers and **OpenFreeMap** are donation-funded
  community infrastructure. Interactive planning use is fine (OpenFreeMap explicitly
  has no usage caps); sustained automated/bulk Overpass querying should run against a
  self-hosted instance (or the full-stack variant below, which imports Geofabrik
  extracts instead).

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
