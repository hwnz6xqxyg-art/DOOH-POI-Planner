# DOOH POI Planner

A geo-proximity planning tool for Digital-out-of-Home (DOOH). Upload your DOOH screen
inventory, **discover Points of Interest from OpenStreetMap** — branded POS (e.g. Rossmann),
airports, gyms, universities — select them as **anchors**, set a radius, and get every screen
within range of any selected POI: deduped, mapped, counted, and exportable.

It is the successor to the **DOOH Shop Connector** (a single-file tool fixed to a Telekom shop
list). This version keeps the inventory upload, proximity matching, and export, and **replaces
the fixed shop list with on-demand OSM POI discovery** (brand search, category picker,
draw-an-area, attribute filters).

## Status

**Pre-build.** This repo currently contains the build-handoff specification, not the
application. See **[`SPEC.md`](./SPEC.md)** for the full spec.

## Architecture (summary)

Runs locally, single user, no auth — `docker compose up` on one machine.

- **PostGIS** — DACH OSM POIs (refreshed monthly) + uploaded DOOH screen inventory.
- **FastAPI** — POI discovery, inventory ingest, proximity matching, export.
- **Leaflet SPA** — dark map, brand/category/area discovery, anchor selection, plan card.
- **ETL** — pyosmium importer: Geofabrik DE/AT/CH `.osm.pbf` → normalized `poi` table.

Geography: **DACH (DE/AT/CH)**. Proximity: straight-line radius (default 500 m, 50–5000 m).

## Layout

```
SPEC.md                          # build-handoff specification (start here)
reference/dooh-shop-connector/   # the donor tool, for faithful reuse (code only)
```

## Reference / donor

`reference/dooh-shop-connector/` holds the donor *DOOH Shop Connector* (`index.html` +
`SPEC.md` + `build/`) so the builder can port its proven plumbing — xlsx ingest, column
auto-detect, Ströer/WallDecaux mappings, export format, radius model, dark map UX. The donor's
embedded Telekom shop data is **not used** by this tool; the proprietary source `.xlsx` is
intentionally omitted.
