# DOOH POI Planner

A **single-file, double-clickable** geo-proximity planning tool for Digital-out-of-Home
(DOOH), Germany-focused. Upload your DOOH screen inventory, **discover Points of Interest
live from OpenStreetMap** — brands (e.g. Rossmann, DM), drugstores, pharmacies, airports,
stations, gyms … — **select** them, set a radius, and get every screen within
range: deduped, mapped, counted, and exportable.

**The whole app is [`index.html`](./index.html).** No install, no server, no build:

1. Download `index.html` (or clone the repo) and **double-click it** — it opens in your
   browser. Internet is required at runtime for the map and the OpenStreetMap queries.
2. **Upload your DOOH inventory** (right panel): any `.xlsx`/`.csv` with ID + lat/lng
   columns. Common layouts auto-detect (incl. SSP, Publisher and Venue-Typ columns);
   confirm the mapping. Inventory persists in the browser.
3. **Discover POIs** (left panel): add brands (optionally bound to a category, e.g.
   *DM · nur Drogerie*), tick categories, choose the area (Germany-wide, Bundesland,
   city, or map view), then **"POIs suchen"**.
4. Click POIs (or *Alle POIs auswählen*) to **select** them, set the radius, and the
   plan card shows screens in range + coverage.
5. **Export**: matched screens as `;`-CSV (German Excel), or the selected POIs' lat/long
   as a Trade-Desk **StoreList XLSX**.

## Features

- **POI discovery via Overpass API** (3 public mirrors with automatic failover, 14-day
  result cache): brand search with whole-word matching, category filters, Bundesland +
  city scoping — combinable, precise AND semantics.
- **Inventory filters**: uploaded lists plus SSP / Publisher / Venue dimensions behind a
  segmented switcher; filters are faceted (each tab shows what remains under the other
  tabs' selections), with select-all/deselect-all and per-list provenance.
- **Fast matching**: spatial grid index, ~10 ms for 100k screens × thousands of selected
  POIs; radius 50 m – 5 km (log slider + presets), per-POI override in the popup.
- **Readable map**: "Positron" light basemap (MapLibre GL under Leaflet), match-aware
  cluster bubbles (gold = in range, `n/m` = partial, grey = out of range), legend,
  L'Oréal-style white/gold/black theme.
- **Everything stays in your browser** — inventory and settings persist locally
  (IndexedDB); nothing is uploaded anywhere except the POI queries to OpenStreetMap.

## Statische POI-Daten (empfohlen für „Ganz Deutschland")

Nationwide searches are the heaviest thing the public Overpass servers can be asked
for — on busy days they queue or rate-limit. The repo therefore ships a data pipeline
that pre-builds the POI dataset, and **the app automatically prefers it**:

- **One-time setup:** in the GitHub repo, open **Actions → "Build POI data" → Run
  workflow**. It downloads the Geofabrik Germany extract, filters the app's categories
  plus every branded POI, and publishes compact JSON shards to the `poi-data` branch
  (~30–60 min). It then re-runs monthly by itself.
- ⚠️ **The repo must be public** (or the data mirrored to a public repo): the app
  fetches the shards anonymously via `raw.githubusercontent.com`, which serves public
  repos only. On a private repo the app tells you and falls back to live Overpass.
  The app itself still runs locally either way — nothing needs to be "hosted"; GitHub
  only serves the data files.
- After the first load the shards are **cached in the browser** (keyed by dataset
  version): repeat nationwide searches are instant and even work offline.
- From then on, "Ganz Deutschland" searches load those shards in **seconds** — no rate
  limits, no queues — and show their `Datenstand` next to the result.
- No setup / branch missing / offline? The app **falls back to live Overpass**
  automatically. Bundesland/city/map-view searches always use live Overpass (they are
  small and fast).

Data license is unchanged: © OpenStreetMap contributors, ODbL 1.0 (extract via
[Geofabrik](https://download.geofabrik.de/), free incl. commercial use).

## Lizenz & Attribution

**Free for commercial use.** The code is **MIT-licensed** ([`LICENSE`](./LICENSE)); every
bundled library, data source, and service is free of charge including commercial use —
full license texts in [`THIRD_PARTY_NOTICES.md`](./THIRD_PARTY_NOTICES.md), summary in
the app's **"Lizenzen"** link (top right):

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
- The public **Overpass API** servers and **OpenFreeMap** are donation-funded community
  infrastructure. Interactive planning use is fine (OpenFreeMap explicitly has no usage
  caps); sustained automated/bulk Overpass querying should run against a self-hosted
  Overpass instance.

## History

Earlier iterations included a full-stack variant (FastAPI + PostGIS + pyosmium ETL +
Vite SPA) and the donor tool this project grew out of (**DOOH Shop Connector**). Both
were superseded by the standalone app and removed from the working tree — they remain
available in the git history (before the "standalone-only" restructure).
