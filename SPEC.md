# Dev Spec — DOOH POI Planner (v1)

**Owner:** Malte · **Build target:** Claude Code · **Status:** spec / pre-build · **Geography:** DACH (DE/AT/CH)

A geo-proximity planning tool for Digital-out-of-Home. It **keeps the DOOH inventory
upload + proximity matching + export** from the donor *DOOH Shop Connector*, and
**replaces the fixed shop list** with **discoverable Points of Interest from OpenStreetMap**:
any branded POS (e.g. Rossmann), transport hub (airports, stations), gym, or university
becomes a selectable **anchor**. The planner discovers POIs, selects them, sets a **radius
in metres**, and the tool returns every DOOH screen inside any selected POI's radius —
deduped, counted live, exportable. Deterministic: same inputs → same result. No scoring,
no ranking, no randomness.

> This document is the build handoff. It is modelled on the donor's own `SPEC.md`
> (see `reference/dooh-shop-connector/SPEC.md`) so the two read consistently.

---

## 0. What changes vs. the donor (read this first)

The donor (`reference/dooh-shop-connector/`) is a **single self-contained `index.html`** —
zero backend, Leaflet + IndexedDB, ~522 Telekom shops **embedded** as the anchors. We keep
its engine and swap its anchor source.

| Concern | Donor (Shop Connector) | New tool (POI Planner) |
|---|---|---|
| **Anchors** | 522 Telekom shops, embedded JSON + `build-shops.py`; optional shop-list upload | **OSM POIs discovered on demand** (brand search, category picker, draw-area, attribute filters) **+ optional manual POI upload** |
| **Anchor store** | embedded array / IndexedDB `customShops` | **PostGIS `poi` table** (DACH extract, refreshed) + `custom_poi` for uploads |
| **DOOH inventory** | IndexedDB, client-side xlsx parse, `partner\|\|screenId` | **PostGIS `screen` table**, server-side parse; same canonical record + keying + accumulation |
| **Proximity engine** | JS grid-bucketed haversine union/dedupe | **PostGIS `ST_DWithin`** (geography) union/dedupe/nearest — same output columns |
| **Architecture** | one HTML file, no server | **FastAPI + PostGIS + SPA front-end**, Docker Compose, runs locally |
| **Reused verbatim/ported** | — | column auto-detect + Ströer/Wall mappings, canonical screen record, export schema, radius model, dark Leaflet UI, "never invent coordinates" rules |

**Decision (interview):** the **full backend + PostGIS** architecture was chosen over a
lighter client-side + Overpass approach, for robust nationwide querying, rich attribute
filtering, and no public-API rate limits. It still targets **one machine, single user, no
auth** — the whole stack runs locally via `docker compose up`, bound to localhost.

---

## 1. Hard constraints / principles

- **Determinism.** Same selection + radius + inventory → same matched set, byte-for-byte export.
- **No invented data.** POIs/screens missing coordinates are listed/flagged, never placed
  at a guessed point. Rows lacking required keys are skipped with a visible count.
  (Carried verbatim from the donor.)
- **Local-first, no auth (v1).** Services bind to `localhost`; no login, no multi-tenant.
  Design data access so auth can be added later without reshaping the schema.
- **DACH only (v1).** Optimised for German tagging/brands. Schema + ETL parameterised by
  country so AT/CH (already included) and later regions need config, not code.
- **German UI text; English code/comments** (carried from the donor).
- **Faithful reuse.** Where the donor already solved a problem (xlsx ingest, column
  auto-detect, export format, radius model, dark map UX), port it — don't reinvent.

---

## 2. Architecture

```
                          ┌─────────────────────────────────────────┐
                          │  Browser SPA (Leaflet, dark theme)        │
   POI discovery  ───────▶│  • brand search  • category picker        │
   inventory upload       │  • draw-area / radius  • attribute filter │
   match + export         │  • anchor select + radius  • plan card    │
                          └───────────────┬───────────────────────────┘
                                          │ HTTP/JSON (+ multipart upload)
                          ┌───────────────▼───────────────────────────┐
                          │  FastAPI (uvicorn)                          │
                          │  /api/brands /api/categories /api/pois/...  │
                          │  /api/inventory/...  /api/match  /api/export│
                          └───────────────┬───────────────────────────┘
                                          │ SQL (asyncpg / SQLAlchemy)
                          ┌───────────────▼───────────────────────────┐
                          │  PostGIS (Postgres + PostGIS)               │
                          │  poi · custom_poi · screen · (boundary)     │
                          └───────────────▲───────────────────────────┘
                                          │ one-shot / scheduled
                          ┌───────────────┴───────────────────────────┐
                          │  ETL: DACH .osm.pbf → poi (pyosmium)        │
                          └─────────────────────────────────────────────┘
```

**Services (Docker Compose):** `db` (postgis/postgis), `api` (FastAPI), `web` (static SPA
served by the api or nginx), and an `etl` one-shot CLI (`docker compose run etl import …`).
Postgres data + a drop folder for `.osm.pbf` extracts live on named volumes.

---

## 3. Tech stack (recommended; builder has latitude where noted)

- **DB:** PostGIS (Postgres 16 + PostGIS 3.x). Non-negotiable — it is the architecture.
- **Backend:** Python 3.11+, **FastAPI** + uvicorn. DB access via **asyncpg** (raw SQL for
  the spatial queries) or SQLAlchemy 2.0 + GeoAlchemy2 (builder's choice; raw SQL is fine
  and keeps the `ST_DWithin` logic legible).
- **ETL:** **pyosmium** (`osmium` Python) for full control over tag→category normalization
  and brand extraction. `osm2pgsql` (flex/Lua) is an acceptable alternative if the builder
  prefers; pyosmium is recommended because the category mapping lives in readable Python.
- **Front-end:** **Vite + TypeScript SPA using Leaflet** — reuse the donor's dark CartoDB
  basemap, marker styles, radius slider, and plan/reach overlay card directly. **leaflet-geoman**
  (or Leaflet.draw) for polygon/area drawing. A React layer is optional; vanilla/light TS is
  closer to the donor and adequate. *Do not* require a heavy framework.
- **Excel parsing:** server-side **openpyxl** (or `python-calamine` for speed). The donor's
  in-browser `DecompressionStream` reader is no longer needed now that upload is server-side,
  but its **column auto-detect patterns and Ströer/Wall mappings must be ported** (§7).
- **Packaging:** Docker Compose. `make up` / `docker compose up` → working tool on localhost.

---

## 4. Data model (PostGIS)

All geometries `geometry(Point, 4326)`; distance tests use the `geography` cast for true
metres. GiST indexes on every geometry column.

### 4.1 `poi` — OSM-derived points of interest (the discoverable anchors)
| column | type | notes |
|---|---|---|
| `id` | text PK | OSM identity, e.g. `node/240095754` (`{osm_type}/{osm_id}`) |
| `osm_type` | text | `node` \| `way` \| `relation` |
| `name` | text | `name` tag (nullable) |
| `brand` | text | `brand` tag (nullable) — drives brand search |
| `brand_wikidata` | text | `brand:wikidata` (nullable) — clean brand identity/dedupe |
| `category` | text | normalized canonical category (§6.2), indexed |
| `subcategory` | text | finer class, e.g. `chemist`, `university`, `aerodrome` |
| `city` | text | `addr:city` (nullable) |
| `plz` | text | `addr:postcode` (nullable) |
| `country` | text | `de` \| `at` \| `ch` |
| `tags` | jsonb | full tag set (powers generic attribute filters), GIN-indexed |
| `geom` | geometry(Point,4326) | centroid for ways/relations; GiST-indexed |

Indexes: GiST(`geom`), btree(`category`), btree(`brand`), GIN(`tags`),
trigram index on `name`/`brand` for fuzzy search (`pg_trgm`).

### 4.2 `screen` — DOOH inventory (ported from the donor's canonical record)
Canonical fields are exactly the donor's: `partner, screenId, name, lat, lng, city, plz,
address, format`. **Key = `(partner, screen_id)`** (partners may reuse IDs; namespacing
prevents collisions — donor uses `partner||screenId`).
| column | type | notes |
|---|---|---|
| `partner` | text | part of PK; e.g. `Ströer`, `WallDecaux` |
| `screen_id` | text | part of PK; per-partner unique |
| `name` | text | falls back to address/id when absent (donor rule) |
| `city` `plz` `address` `format` | text | nullable |
| `geom` | geometry(Point,4326) | from `lat`/`lng`; GiST-indexed |
| PK | (`partner`,`screen_id`) | — |

Re-upload semantics (donor §4): **replace that partner's screens entirely** (delete-by-partner
then bulk insert); other partners untouched; inventory **accumulates** across uploads.

### 4.3 `custom_poi` — manually uploaded anchors (hybrid input, kept per interview)
Same shape as the relevant `poi` columns but `source='custom'`, plus an upload/session id so a
custom list can be replaced/reset like the donor's `customShops`. Uploaded via the donor's
shop-mapping flow (id/name/lat/lng + optional attrs). Rows without coordinates are kept as
**un-plottable**, never invented.

### 4.4 `boundary` *(optional, v1.5)* — OSM admin polygons for "pick an area = a city/Bundesland"
`boundary=administrative`, `admin_level` 4 (Bundesland) / 6 (Kreis) / 8 (Gemeinde), as
`geometry(MultiPolygon,4326)`. Enables area-select by administrative unit (§5.3). Not required
for v1; bbox + drawn polygon + radius cover the launch.

---

## 5. POI discovery (replaces the donor's shop list)

All four selection modes from the interview are supported and **composable** (area ∩ brand ∩
category ∩ attributes):

### 5.1 Brand / name search
- `GET /api/brands?q=ross` → distinct `brand` (+ `brand_wikidata`, count) matching `q`
  (trigram/ILIKE), so "Rossmann", "dm", "Edeka" autocomplete with location counts.
- Selecting a brand discovers all its POIs (optionally within the active area).
- Brand identity prefers `brand:wikidata` over the free-text `brand` string for dedupe.

### 5.2 Category picker
- `GET /api/categories` → the v1 taxonomy (§6.2) as a checkbox tree with counts.
- v1 top-level: **Branded retail POS**, **Transport hubs**, **Leisure & education**
  (healthcare/public deferred — see §17).

### 5.3 Area selection (geographic scope)
- **v1:** map viewport bbox · **drawn polygon** (leaflet-geoman, GeoJSON) · **radius around a
  point**. Sent to the API as GeoJSON / bbox and applied as a PostGIS `ST_Intersects` /
  `ST_DWithin` predicate.
- **v1.5:** pick a named admin area (Stadt / Bundesland) via `boundary` (§4.4).

### 5.4 Attribute filters
- Generic: `tagFilters: [{key, op, value}]` applied as `tags` jsonb predicates (e.g.
  `opening_hours` present, `operator=…`, `aerodrome:type=international`).
- The front-end surfaces the most common keys for the active category plus a free
  key/value row, so new filters need no code change.

### 5.5 Discovery API
`POST /api/pois/search` → body `{ area, brands[], categories[], tagFilters[], limit }`,
returns GeoJSON FeatureCollection (capped + paginated). Results render as selectable markers;
selecting promotes a POI to an **anchor** (the role the Telekom shops played in the donor).

---

## 6. OSM ingest / ETL

### 6.1 Source & tooling
- **Extracts:** Geofabrik `.osm.pbf` for `europe/germany`, `europe/austria`,
  `europe/switzerland`. Dropped into the volume; `etl` imports them.
- **Importer:** pyosmium handler streams nodes/ways/relations, **filters to the v1 tag set**
  (§6.2), computes a centroid for ways/relations, extracts `brand`/`brand:wikidata`, normalizes
  `category`/`subcategory`, and bulk-loads `poi`. Records an `import_meta` row (extract date,
  per-category counts) so the UI can show data freshness.
- **Freshness (interview = "recommend"):** scheduled **monthly** refresh (cron / `docker
  compose run etl import`), truncate-and-reload per country (or diff via `pyosmium-up-to-date`).
  POIs change slowly; monthly is the sane default and is documented as configurable.

### 6.2 v1 category taxonomy → OSM tag mapping
The ETL normalizes raw OSM tags into `category`/`subcategory`. Keep the full `tags` jsonb so
nothing is lost.

| category | subcategory | OSM selector (examples) |
|---|---|---|
| **branded_retail** | chemist | `shop=chemist` (Rossmann, dm) |
| | supermarket | `shop=supermarket` (Edeka, Rewe, Aldi, Lidl, Kaufland) |
| | electronics | `shop=electronics` (MediaMarkt, Saturn) |
| | clothes | `shop=clothes` (H&M, C&A …) |
| | other_branded | any `shop=*`/retail `amenity=*` carrying `brand`/`brand:wikidata` |
| **transport_hub** | airport | `aeroway=aerodrome` (flag `iata`/`aerodrome:type` for major) |
| | rail_station | `railway=station`, `railway=halt`, `public_transport=station` + `train=yes` |
| | bus_station | `amenity=bus_station` |
| **leisure_education** | gym | `leisure=fitness_centre` (+ `sport=fitness`) |
| | university | `amenity=university`, `amenity=college` |
| | school | `amenity=school` *(include; flag as high-volume)* |
| | stadium | `leisure=stadium` |
| | cinema | `amenity=cinema` |
| | mall | `shop=mall`, `shop=department_store` |

> **Branded retail is brand-first:** the category exists, but the primary UX is brand search
> (§5.1). A POI qualifies as `branded_retail/other_branded` whenever it carries a `brand` tag
> in a retail class, so brands beyond the explicit list above are still discoverable.

---

## 7. DOOH inventory upload (ported from the donor)

Reuse the donor's solved ingest, moved server-side:

- **Upload:** `POST /api/inventory/upload` (multipart `.xlsx`/`.csv`) → parse, **auto-detect
  columns**, return a preview + detected mapping. Then `POST /api/inventory/import` with the
  confirmed mapping → upsert.
- **Auto-detect:** port `SCREEN_FIELDS` regex patterns from
  `reference/dooh-shop-connector/index.html` (the `screenId/lat/lng/name/city/plz/address/format/partnerCol`
  matchers). New partners onboard with **no code change** via the confirm/remap step.
- **Verified partner mappings** (from donor §4a — bake as presets):

  | Canonical | Ströer (`stroeer_dooh_inventory`, ~6,659 rows) | WallDecaux/VIOOH (`Export`, ~1,552 rows) |
  |---|---|---|
  | partner | `publisher` (="Ströer") | `Environment` (="WallDecaux") |
  | screenId | `location id` | `Frame ID` |
  | lat/lng | `latitude`/`longitude` | `Latitude`/`Longitude` |
  | name | `location name` | *(none → fall back to address/id)* |
  | city/plz | `city`/`postcode` | `City DE`/`Postcode` |
  | address | `address/street` | `Address` |
  | format | `venue type`/`frame size` | `Channel`/`Category` |

- **Canonical stored record:** `partner, screenId, name, lat, lng, city, plz, address, format`
  (donor's lean set — no raw passthrough).
- **Validation (donor rule):** rows lacking `screenId`/`lat`/`lng` are **skipped, never
  invented**; show imported/skipped/deduped counts. EU decimal-comma coordinates handled
  (port `parseCoord`).
- **Partner management:** `GET /api/inventory/partners` (names + counts),
  `DELETE /api/inventory/partner/{partner}`, and a per-partner **visibility toggle** (hidden
  partners drop out of matching + export — donor behaviour, store the hidden set client-side).

---

## 8. Proximity / matching engine

Same semantics as the donor, executed in PostGIS:

- A screen is **in-proximity** if `ST_DWithin(screen.geom::geography, anchor.geom::geography,
  radius)` for **any** selected anchor (geometric **union**). Output is **deduped by screen**.
- **Radius model (donor §5):** global default **500 m**, range **50–5000 m**, step **50 m**,
  **global radius + optional per-anchor override**. Per-anchor overrides are passed with the
  selection (e.g. a temp/values table of `(anchor_id, geom, radius)`); matching uses each
  anchor's effective radius.
- **Per-screen output (donor export contract):** `matched_poi_ids` (all anchors that hit it),
  `nearest_poi_id`, `nearest_distance_m`, `radius_used_m`. Computed with a `LATERAL` nearest
  lookup or `DISTINCT ON` over the matched pairs.
- `POST /api/match` → body `{ anchors:[{id,radius?}] | poiQuery, globalRadius, hiddenPartners[] }`
  → `{ screens:[…], stats:{…} }`.

**Performance:** GiST + `geography` `ST_DWithin` handles thousands of anchors × ~10k+ screens
comfortably; this is exactly where PostGIS beats the donor's client-side grid index. Cap
anchor count with a clear message if a query would select an unreasonable number of POIs.

---

## 9. Outputs (all four from the interview)

1. **Filtered screen list (export)** — `POST /api/export` → **`;`-delimited, UTF-8 (BOM),
   CRLF** CSV for German Excel (port `csvCell`/BOM/CRLF from the donor). Columns (donor schema,
   shop→poi rename):
   `screen_id; partner; name; lat; lng; city; plz; address; format; matched_poi_ids;
   nearest_poi_id; nearest_distance_m; radius_used_m`.
   Deterministic order: partner, then numeric-aware screen_id.
2. **Interactive map** — POIs (anchors) + screens on the dark Leaflet basemap; in-proximity
   screens highlighted; radius circles drawn per anchor (port `drawRadii`, marker styles, the
   diff-restyle highlight).
3. **Coverage / reach stats** — **screen counts + coverage %**, *not* impressions: your
   inventory is locations/attributes only (interview). Live plan/reach overlay card shows:
   deduped in-proximity screen count, # anchors selected, **% of anchors with ≥1 screen in
   radius**, and a per-category breakdown. Reach-by-impressions is explicitly out of scope
   until inventory carries impression data (§17).
4. **Buying-format re-export** — interview = **round-trip in the uploaded schema**: in addition
   to the canonical export above, offer "export matched screens in the original column layout
   of partner X" by retaining the source header mapping per partner (store the confirmed
   mapping alongside the partner) and re-emitting matched rows in those columns.

---

## 10. Front-end UX (reuse the donor's look & flows)

- **Map shell:** port the donor's dark `:root` palette, CartoDB `dark_all` basemap
  (`preferCanvas:true`), Leaflet overrides, custom marker icons, the multi-select + live
  overlay dashboard, and the plan/reach card.
- **Left panel — Discovery (new):** brand search (autocomplete), category checkbox tree,
  area tools (draw polygon / radius / "use map view"), attribute filters. Discovered POIs list
  + "select all in area" (mirrors the donor's "select all filtered/visible").
- **Marker interactions:** click a POI to toggle it as an anchor; anchor popup carries the
  **per-anchor radius slider** (port `wireShopPopup`). Global radius slider in the toolbar.
- **Right panel — Inventory:** upload button → mapping modal (port `openMappingModal`),
  partner list with counts + visibility toggle + remove (port `renderPartners`).
- **Overlay:** live deduped in-proximity count + coverage % + export button (disabled at 0).

---

## 11. Persistence / state

- **PostGIS:** `poi` (ETL), `screen` (uploads), `custom_poi` (uploads) — the durable data.
- **Client (localStorage):** working session — selected anchor ids, global radius, per-anchor
  overrides, hidden partners, last area/filters (port the donor's `saveState`/`loadState`,
  debounced + flush on `pagehide`/`visibilitychange`).
- **No server-side user state** in v1 (single user). A future `session`/`plan` table is the
  obvious extension if saved campaigns are wanted.

---

## 12. Packaging & deployment

- **`docker-compose.yml`:** `db` (postgis/postgis, volume `pgdata`), `api` (FastAPI/uvicorn),
  `web` (static SPA), `etl` (one-shot importer). Bind published ports to `127.0.0.1` only
  (no auth ⇒ do not expose on `0.0.0.0`).
- **First run:** `docker compose up -d db` → `docker compose run etl import --pbf /data/germany-latest.osm.pbf --country de`
  (repeat AT/CH) → `docker compose up`. Document this in `README`.
- **Refresh:** documented monthly `etl import` (cron-friendly).
- **Config:** `.env` for DB creds, extract paths, default radius, Overpass/tile endpoints (in
  case a self-hosted basemap is wanted later).

---

## 13. Build phases (checkpoint at each boundary)

- **P0 — Scaffold.** Repo layout, `docker-compose.yml` (db/api/web/etl), FastAPI health check,
  empty SPA serving the dark map shell. *(Fully unblocked.)*
- **P1 — PostGIS + ETL.** Schema/migrations; pyosmium importer for the v1 tag set with category
  normalization + brand extraction; `import_meta`. Validate counts against a known city.
  *(Needs a Geofabrik extract; a small `.osm.pbf` city extract is fine for dev.)*
- **P2 — POI discovery.** `/api/brands`, `/api/categories`, `/api/pois/search`; front-end
  brand search + category picker + draw-area + attribute filters; render + select anchors.
- **P3 — Inventory ingest.** Server-side xlsx/csv parse + ported auto-detect + confirm/remap
  modal + Ströer/Wall presets; `screen` table upsert (replace-by-partner, accumulate); partner
  panel + visibility/remove; render screens.
- **P4 — Matching.** PostGIS `ST_DWithin` union/dedupe/nearest; global + per-anchor radius;
  radius circles; live deduped count + coverage % stats; map highlight.
- **P5 — Export & polish.** Canonical `;`-CSV export + per-partner round-trip export; manual
  POI upload (hybrid); session persistence; data-freshness badge; empty/error states.

---

## 14. Acceptance criteria

1. `docker compose up` (after an ETL import) serves the tool on localhost with the dark map and
   no external calls beyond basemap tiles; tile failure degrades gracefully.
2. Brand search for "Rossmann" returns its DACH POIs; a category pick (e.g. universities)
   returns the expected class; both can be constrained to a drawn area / radius.
3. POIs/screens missing coordinates are listed/flagged, never plotted at a made-up point.
4. Uploading a partner file adds its screens; re-uploading replaces **that partner only**;
   other partners survive; counts of imported/skipped/deduped are shown.
5. Selecting anchors + changing the global radius redraws circles and updates the in-proximity
   count **deterministically**; a per-anchor override affects only that anchor's catchment.
6. A screen inside multiple selected anchors' radii is counted **exactly once**.
7. Coverage stats report screen count + **% of anchors with ≥1 screen in radius** (no
   impressions claimed).
8. Export contains every in-proximity screen and nothing else; opens cleanly in German Excel
   (`;`-delimited, UTF-8 BOM, CRLF); per-partner round-trip export reproduces the source columns.
9. Matching stays responsive at ~10k+ screens × thousands of anchors (PostGIS-indexed).

## 15. Reuse-from-donor index (point the builder here)

From `reference/dooh-shop-connector/index.html` — **port, don't reinvent:**
- `SCREEN_FIELDS` auto-detect regexes + `autoDetect` + mapping modal (`openMappingModal`,
  `buildRecords`, `updateMapSummary`) → server-side importer + confirm UI.
- Canonical screen record + `partner||screenId` keying + replace-by-partner accumulation.
- `parseCoord` (EU decimal comma), "skip rows without id/lat/lng", "never invent coords".
- Export: `csvCell`, BOM+CRLF, `EXPORT_COLS`, deterministic sort → `/api/export`.
- Radius model + `radiusOf` + per-anchor popup slider + `drawRadii` + diff-restyle highlight.
- Proximity output fields (`matched_*`, `nearest_*`, `radius_used`) → PostGIS query columns.
- Dark theme/CSS, marker styles, plan/reach overlay card, `saveState`/`loadState`.
From `reference/dooh-shop-connector/SPEC.md` — the donor's design rationale, verified partner
schemas (§4a), and data-integrity decisions.

## 16. Open questions / assumptions to confirm

- **Front-end framework:** spec assumes Vite + TS + Leaflet (light). Switch to React if you
  prefer component structure — does not affect the API contract.
- **School volume:** `amenity=school` is high-count in DACH; included but flagged. Keep, or
  drop from v1?
- **Admin-area select (§4.4/§5.3):** v1.5 vs. v1? Needs a boundary import.
- **Custom POI upload schema:** assume `id, name, lat, lng (+ optional city/plz/category)`,
  reusing the donor's shop-mapping flow — confirm any required custom attributes.
- **Brand list curation:** rely on raw OSM `brand`/`brand:wikidata` (with trigram fuzzy search)
  vs. a curated alias list (e.g. "Müller", umlaut variants). v1 = raw + fuzzy; flag if you want
  curation.

## 17. Out of scope (v1) / future

- Healthcare & public POI categories (hospitals, pharmacies, government) — taxonomy extension.
- Impression/reach metrics — blocked on inventory carrying impressions (interview: it doesn't).
- Auth / multi-tenant / saved campaigns — schema leaves room; not built.
- Walking/drive-time isochrone proximity (interview chose straight-line radius).
- Self-hosted basemap tiles; regions beyond DACH.
