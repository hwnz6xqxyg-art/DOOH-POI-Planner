# Reference material

Read-only donor code, included so the build can reuse proven logic faithfully. **Not part of
the new application's runtime.**

## `dooh-shop-connector/`

The donor **DOOH Shop Connector** (branch `claude/gracious-wozniak-rdvfwh`):

- `index.html` — the complete single-file tool. Port from here: the zero-dependency xlsx/csv
  reader, `SCREEN_FIELDS` column auto-detect + mapping modal, the canonical screen record and
  `partner||screenId` keying, the `;`-CSV export (BOM/CRLF), the radius model, and the dark
  Leaflet UI. See `../SPEC.md` §15 for the exact reuse index.
- `SPEC.md` — the donor's own spec: design rationale, verified Ströer/WallDecaux partner
  schemas, and data-integrity decisions ("never invent coordinates", etc.).
- `build/build-shops.py` — the donor's Excel→embedded-JSON build step. **Superseded** in the
  new tool (POIs come from PostGIS/OSM, not an embedded list); kept only to show the xlsx
  parsing approach.

> The donor's embedded ~522 Telekom shops and its source `.xlsx` are donor-specific and are
> **not** used by the POI Planner. The `.xlsx` is intentionally omitted from this repo.
