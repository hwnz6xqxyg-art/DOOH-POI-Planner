# Dev Spec — DOOH Shop Connector (v1)

**Owner:** Malte · **Build target:** Claude Code · **Deliverable:** single self-contained `index.html` (no backend) · **Status:** v1 complete (P1–P5 shipped)

A deterministic geo-proximity planning tool for Digital-out-of-Home. ~522 geocoded Telekom shops act as **anchors**; the planner selects shops, sets a **radius in metres**, and the tool returns every **DOOH screen** inside any selected shop's radius — deduped, counted live, exportable. No scoring, no ranking, no randomness.

---

## 1. Hard constraints (carried from handoff)
- **One file.** All data, logic, styles inside `index.html`. CDN libs only if version-pinned + SRI.
- **Zero npm runtime deps.** Only runtime dep = Leaflet 1.9.4 (CDN, pinned + SRI — copied from donor). Build-time Excel→JSON uses Node ≥18 / Python stdlib only, zero installs.
- **No invented data.** Missing coords/fields shown as missing, never zero or guessed.
- **Determinism.** Same inputs → same selection.
- **German UI text; English code comments.**

## 2. Reuse from the donor `index.html` (Magenta Matchday Planner)
Keep the plumbing, drop the football. Reuse near-verbatim: the dark `:root` palette + Leaflet overrides; the Leaflet map shell (dark CartoDB `dark_all`, `preferCanvas:true`, pinned CSS/JS+SRI); custom marker icons (repurposed); the popup radius slider (`L.circle(center,{radius:r})`, already metres internally); the haversine helper (km→m); the multi-select + live overlay dashboard; the `;`-CSV export helpers (`exportCsvText`, `csvCell`, `downloadText`, clipboard copy); the map overlay plan/reach card.

**Delete entirely:** all scoring (`scoreMatch`, weights, presets), fixtures/OpenLigaDB, derby logic, club DB editor, ZIP/PLZ population overlay, Trade-Desk export, and SPEC §§D–K football contracts.

## 3. Data contract — Telekom shops (PROVIDED, verified)
Sheet `Shops_with_geocode_fields`, **526 rows / 32 cols**. Baked into the HTML as embedded JSON via a one-shot Python/Node build step (Excel not needed at runtime). Verified facts:
- **Coords = `Latitude2` / `Longitude3`** (522/526 populated). The `Latitude`/`Longitude` columns are a decoy (22 populated) — not used.
- **Key = `Shop_Row_ID`** (unique 526/526). `Bezeichnung` is NOT unique (489/526) — never key on it.
- **Geocode_Quality:** 504 `exact`, 18 `street`, 4 `FAILED`.
- **Status:** 519 `IN_BETRIEB`, 7 `IN_PLANUNG`.

**Decision (interview):** **All geocoded shops are anchorable; status is a filter dimension, not a gate.** The 4 `FAILED` shops have no usable coords → listed/flagged as unplottable, never placed at a made-up point.

**Embedded per-shop JSON (lean):** `id` (Shop_Row_ID), `name` (Bezeichnung), `ort`, `plz`, `region`, `bundesland`, `paTs` (PA/TS), `betreiber`, `lat`, `lng`, `status`, `geocodeQuality`. (`betreiber`/`paTs` kept because they're filter dimensions.)

### 3a. Runtime shop-list override (added post-v1)
The embedded list is the baseline; a revised shop list can be **uploaded at runtime** (`.xlsx`/`.csv`, same zero-dependency reader + column-mapping modal as partner inventories). Semantics mirror partner uploads: the uploaded file **replaces the entire anchor list** (add/edit/remove = maintain the Excel, re-upload), persists in IndexedDB (`meta` store, key `customShops`), and survives reloads. One-click reset restores the embedded baseline. Auto-detect prefers `Latitude2`/`Longitude3` over the decoy columns; rows without coordinates are kept as unplottable (never invented); rows without an id are skipped. Stale selections/per-shop radii are pruned on list swap.

## 4. Data contract — DOOH screens (samples received: Ströer + WallDecaux/VIOOH)
**Decision (interview):** the tool maintains a **persistent, additive multi-partner inventory database** in **IndexedDB** — partners (Ströer, WallDecaux/VIOOH, …) are uploaded over time and accumulate; not reloaded each session. (IndexedDB, not localStorage: two sample partners already total ~8,200 screens, past localStorage's ~5 MB comfort zone.)
- **Format = Excel `.xlsx`** (the provided samples are xlsx, not CSV). Runtime ingest uses a **zero-dependency in-browser reader**: an `.xlsx` is a ZIP, so we parse the ZIP central directory and inflate parts with the browser-native `DecompressionStream('deflate-raw')`, then parse the sheet XML via `DOMParser` — no SheetJS, no new CDN dependency. CSV is also accepted as a fallback.
- **Per-partner column mapping:** partners share almost no headers (Ströer `location id`/`latitude`; Wall `Frame ID`/`Latitude`), so ingest **auto-detects** the canonical columns and shows a **confirm/remap step** before import — new partners onboard with no code change.
- **Canonical record (lean, stored):** `partner`, `screenId`, `name`, `lat`, `lng`, `city`, `plz`, `address`, `format`. (Fields chosen in interview.) No raw-row passthrough stored, to keep the DB lean.
- **Keying:** IndexedDB keyPath = **`partner||screenId`** — partners may reuse IDs without colliding; indexed by `partner`.
- **Re-upload:** **replace that partner's screens entirely** (delete-by-partner then bulk put); other partners untouched.
- **Validation:** rows lacking `screenId`/`lat`/`lng` are skipped (never invented); a summary of imported/skipped is shown.
- **Scale:** ~8k now, accumulating → canvas `circleMarker`s; linear in-radius test is fine at this size, add a grid-bucket index only if it gets sluggish.

### 4a. Verified partner schemas (sample files)
| Canonical | Ströer (`stroeer_dooh_inventory`, 6,659 rows) | WallDecaux/VIOOH (`Export`, ~1,552 rows) |
|---|---|---|
| partner | `publisher` (="Ströer") | `Environment` (="WallDecaux") |
| screenId | `location id` (unique) | `Frame ID` (unique) |
| lat / lng | `latitude` / `longitude` | `Latitude` / `Longitude` |
| name | `location name` | *(none → fall back to address/id)* |
| city / plz | `city` / `postcode` | `City DE` / `Postcode` |
| address | `address/street` | `Address` |
| format | `venue type` / `frame size` | `Channel` / `Category` |

## 5. Radius & selection (interview decisions)
- **Radius:** global default **500 m**, range **50–5000 m**, step **50 m**. **Global radius + optional per-shop override** set via a slider in the shop's marker popup (mirrors the donor's per-club slider).
- **Shop selection:** click-to-toggle markers **+** a filter panel (Region / Bundesland / Ort / Status / PA-TS) with **"select all filtered/visible"**. (Best-practice combo for ~522 markers.)
- **Screen filtering:** proximity is the **only** filter in v1; a clean hook left for v2 partner/format/status pre-filters.

## 6. Proximity engine
A screen is *in-proximity* if `haversineMetres(shop, screen) ≤ radius(shop)` for **any** selected shop (geometric union). The deduped set (by namespaced screen key) is the output. `radius(shop)` = per-shop override if set, else the global radius. Distance in metres via the donor's haversine (km helper × 1000).

## 7. Output & export
- **Live count** of deduped in-proximity screens in the map overlay, updating on every selection/radius change.
- **Export:** `;`-delimited, UTF-8 (BOM) CSV for German Excel. Columns: `screen_id`, `partner`, `name`, `lat`, `lng`, `city`, `plz`, `address`, `format`, `matched_shop_ids` (`;`-joined inside a quoted cell), `nearest_shop_id`, `nearest_distance_m`, `radius_used_m`. Optional one-click plain ID list later.

## 8. Persistence
**IndexedDB**: the inventory DB (all partners' screens) — the accumulating store, survives reloads. **localStorage**: the selected-shop set, global radius, and per-shop overrides — restore the working session.

## 9. Build phases (checkpoint at each boundary)
- **P1** Build step: Excel → embedded `shops.json`; render shop markers on the dark map; filter panel + click-to-toggle selection. *(Fully unblocked.)*
- **P2** Screen inventory ingest: CSV upload + per-partner column mapping + persistent multi-partner DB; render screen markers (distinct class). *(Needs samples.)*
- **P3** Global radius + per-shop override; draw radius circles; persistence of radii/selection.
- **P4** Proximity engine (haversine, metres, union, dedupe) + live in-proximity count.
- **P5** Export (rich `;`-CSV) + full persistence polish.

## 10. Acceptance criteria
1. Opening the file shows all geocoded shops on the dark map with no network beyond basemap tiles; tile failure degrades gracefully.
2. The 4 FAILED-geocode shops are listed/flagged, never plotted at a made-up point.
3. Uploading a partner CSV adds its screens to the persistent DB; re-uploading replaces that partner only; other partners survive a reload.
4. Selecting shops and changing the global radius redraws circles and updates the in-proximity count deterministically.
5. A per-shop radius override affects only that shop's catchment.
6. A screen inside multiple selected shops' radii is counted exactly once.
7. Export contains every in-proximity screen and nothing else; opens cleanly in German Excel (`;`-delimited, UTF-8).

## 11. Open / pending
- **Screen samples** (Ströer + JCDecaux/Wall) — re-attach to finalise §4 + §7 export passthrough. P1 proceeds without them.
