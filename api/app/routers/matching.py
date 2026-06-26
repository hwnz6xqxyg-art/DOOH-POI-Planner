"""Proximity matching (PostGIS ST_DWithin) + CSV export (SPEC §8, §9)."""
from __future__ import annotations

import io
import json
from datetime import datetime, timezone

from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse

from .. import db
from ..config import MATCH_ANCHOR_MAX, RADIUS_DEFAULT
from ..schemas import MatchRequest

router = APIRouter()

# Canonical export columns (donor EXPORT_COLS, shop->poi rename). SPEC §9.1
EXPORT_COLS = ["screen_id", "partner", "name", "lat", "lng", "city", "plz", "address",
               "format", "matched_poi_ids", "nearest_poi_id", "nearest_distance_m", "radius_used_m"]

_MATCH_SQL = """
WITH sel AS (
  SELECT unnest(%(ids)s::text[]) AS id, unnest(%(radii)s::int[]) AS r
),
anchors AS (
  SELECT a.id, a.geom, COALESCE(sel.r, %(global)s) AS radius
  FROM (
    SELECT id, geom FROM poi        WHERE id = ANY(%(ids)s)
    UNION ALL
    SELECT id, geom FROM custom_poi WHERE id = ANY(%(ids)s) AND geom IS NOT NULL
  ) a JOIN sel ON sel.id = a.id
),
hits AS (
  SELECT s.partner, s.screen_id, s.name, ST_Y(s.geom) AS lat, ST_X(s.geom) AS lng,
         s.city, s.plz, s.address, s.format,
         a.id AS anchor_id, a.radius,
         ST_Distance(s.geom::geography, a.geom::geography) AS dist
  FROM screen s JOIN anchors a
    ON ST_DWithin(s.geom::geography, a.geom::geography, a.radius)
  WHERE NOT (s.partner = ANY(%(hidden)s))
)
SELECT partner, screen_id, name, lat, lng, city, plz, address, format,
       array_agg(DISTINCT anchor_id)              AS matched_poi_ids,
       (array_agg(anchor_id ORDER BY dist))[1]    AS nearest_poi_id,
       round(min(dist))::int                      AS nearest_distance_m,
       (array_agg(radius ORDER BY dist))[1]       AS radius_used_m
FROM hits
GROUP BY partner, screen_id, name, lat, lng, city, plz, address, format
ORDER BY partner, screen_id
"""


def _run(req: MatchRequest) -> list[dict]:
    if not req.anchors:
        return []
    ids = [a.id for a in req.anchors]
    radii = [a.radius for a in req.anchors]  # None -> COALESCE to global
    g = req.global_radius or RADIUS_DEFAULT
    rows = db.fetch_all(_MATCH_SQL, {"ids": ids, "radii": radii, "global": g,
                                     "hidden": req.hidden_partners or []})
    for r in rows:  # deterministic order of matched ids for stable export
        r["matched_poi_ids"] = sorted(r["matched_poi_ids"])
    return rows


def _resolve_anchors(ids: list[str]) -> list[dict]:
    if not ids:
        return []
    return db.fetch_all(
        """SELECT id, category FROM poi WHERE id = ANY(%s)
           UNION ALL
           SELECT id, COALESCE(category,'custom') FROM custom_poi WHERE id = ANY(%s) AND geom IS NOT NULL""",
        [ids, ids],
    )


@router.post("/match")
def match(req: MatchRequest) -> dict:
    if len(req.anchors) > MATCH_ANCHOR_MAX:
        return {"error": f"Zu viele Anker ausgewählt (max {MATCH_ANCHOR_MAX})."}
    rows = _run(req)
    anchors = _resolve_anchors([a.id for a in req.anchors])
    covered = set()
    for r in rows:
        covered.update(r["matched_poi_ids"])
    cat_total: dict[str, int] = {}
    cat_cov: dict[str, int] = {}
    for a in anchors:
        cat_total[a["category"]] = cat_total.get(a["category"], 0) + 1
        if a["id"] in covered:
            cat_cov[a["category"]] = cat_cov.get(a["category"], 0) + 1
    stats = {
        "screens_total": len(rows),
        "anchors_total": len(anchors),
        "anchors_covered": len([a for a in anchors if a["id"] in covered]),
        "coverage_pct": round(100 * len([a for a in anchors if a["id"] in covered]) / len(anchors), 1) if anchors else 0,
        "by_category": [{"category": c, "total": cat_total[c], "covered": cat_cov.get(c, 0)} for c in sorted(cat_total)],
    }
    return {"screens": rows, "stats": stats}


# --- CSV export (donor csvCell / BOM / CRLF). SPEC §9.1, §9.4 ----------------
def _cell(v) -> str:
    s = "" if v is None else str(v)
    if any(c in s for c in (';', '"', '\n', '\r')):
        return '"' + s.replace('"', '""') + '"'
    return s


def _csv_canonical(rows: list[dict]) -> str:
    lines = [";".join(EXPORT_COLS)]
    for r in rows:
        rec = dict(r)
        rec["matched_poi_ids"] = ";".join(str(x) for x in r["matched_poi_ids"])
        lines.append(";".join(_cell(rec.get(c)) for c in EXPORT_COLS))
    return "﻿" + "\r\n".join(lines)


def _csv_roundtrip(rows: list[dict], partner: str) -> str:
    """Re-emit one partner's matched screens under its original source headers
    (SPEC §9.4). mapping = {canonicalField: sourceHeader}."""
    meta = db.fetch_one("SELECT mapping FROM partner_meta WHERE partner = %s", [partner])
    mapping: dict = (meta or {}).get("mapping") or {}
    # canonical field -> source header (only fields we actually store)
    field_to_col = {
        "screenId": "screen_id", "lat": "lat", "lng": "lng", "name": "name",
        "city": "city", "plz": "plz", "address": "address", "format": "format",
    }
    cols = [(mapping[f], field_to_col[f]) for f in field_to_col
            if mapping.get(f)]
    if not cols:  # no stored mapping -> fall back to canonical
        return _csv_canonical([r for r in rows if r["partner"] == partner])
    header = [src for src, _ in cols]
    lines = [";".join(_cell(h) for h in header)]
    for r in rows:
        if r["partner"] != partner:
            continue
        lines.append(";".join(_cell(r.get(canon)) for _src, canon in cols))
    return "﻿" + "\r\n".join(lines)


@router.post("/export")
def export(req: MatchRequest, layout: str = Query("canonical"), partner: str = Query("")) -> StreamingResponse:
    rows = _run(req)
    if layout == "roundtrip" and partner:
        text = _csv_roundtrip(rows, partner)
        fname = f"dooh-screens_{partner}".replace(" ", "_")
    else:
        text = _csv_canonical(rows)
        fname = "dooh-screens-in-radius"
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M")
    return StreamingResponse(
        io.BytesIO(text.encode("utf-8")),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{fname}_{ts}.csv"'},
    )
