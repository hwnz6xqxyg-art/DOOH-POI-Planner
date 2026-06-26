"""DOOH inventory ingest + partner management (SPEC §7). Ported donor flow:
preview -> confirm mapping -> import (replace-by-partner, accumulate)."""
from __future__ import annotations

import json

from fastapi import APIRouter, File, Form, UploadFile

from .. import db
from ..ingest import (POI_FIELDS, SCREEN_FIELDS, auto_detect, build_poi_records,
                      build_screen_records, read_spreadsheet)

router = APIRouter()


def _guess_partner(rows: list[dict], mapping: dict, filename: str) -> str:
    col = mapping.get("partnerCol")
    if col:
        for r in rows[:50]:
            v = r.get(col)
            if v and str(v).strip():
                return str(v).strip()
    return (filename or "Partner").rsplit(".", 1)[0]


@router.post("/inventory/preview")
async def preview(file: UploadFile = File(...), mode: str = Form("screens")) -> dict:
    data = await file.read()
    parsed = read_spreadsheet(data, file.filename or "")
    fields = POI_FIELDS if mode == "pois" else SCREEN_FIELDS
    mapping = auto_detect(parsed["headers"], fields)
    out = {
        "sheet": parsed["sheet"],
        "headers": parsed["headers"],
        "row_count": len(parsed["rows"]),
        "sample": parsed["rows"][:5],
        "mapping": mapping,
        "fields": [{"key": k, "required": req} for k, _p, req in fields],
    }
    if mode != "pois":
        out["partner_guess"] = _guess_partner(parsed["rows"], mapping, file.filename or "")
    return out


@router.post("/inventory/import")
async def import_screens(
    file: UploadFile = File(...),
    partner: str = Form(...),
    mapping: str = Form(...),
) -> dict:
    data = await file.read()
    parsed = read_spreadsheet(data, file.filename or "")
    m = json.loads(mapping)
    built = build_screen_records(parsed["rows"], m, partner)
    recs = built["recs"]

    with db.pool.connection() as conn, conn.cursor() as cur:
        cur.execute("DELETE FROM screen WHERE partner = %s", [partner])  # replace partner only
        if recs:
            cur.executemany(
                """INSERT INTO screen (partner, screen_id, name, city, plz, address, format, geom)
                   VALUES (%(partner)s,%(screen_id)s,%(name)s,%(city)s,%(plz)s,%(address)s,%(format)s,
                           ST_SetSRID(ST_MakePoint(%(lng)s,%(lat)s),4326))""",
                recs,
            )
        cur.execute(
            """INSERT INTO partner_meta (partner, mapping, source_headers, screen_count, updated_at)
               VALUES (%s,%s,%s,%s, now())
               ON CONFLICT (partner) DO UPDATE SET mapping=EXCLUDED.mapping,
                 source_headers=EXCLUDED.source_headers, screen_count=EXCLUDED.screen_count,
                 updated_at=now()""",
            [partner, json.dumps(m), json.dumps(parsed["headers"]), len(recs)],
        )
    return {"partner": partner, "imported": len(recs),
            "skipped": built["skipped"], "dupes": built["dupes"]}


@router.get("/inventory/partners")
def partners() -> dict:
    rows = db.fetch_all(
        """SELECT partner, count(*) AS n FROM screen GROUP BY partner ORDER BY partner""")
    total = db.fetch_one("SELECT count(*) AS n FROM screen")["n"]
    return {"partners": rows, "total": total}


@router.get("/inventory/screens")
def screens(limit: int = 20000) -> dict:
    """Light screen points for map rendering (capped). SPEC §9.2."""
    rows = db.fetch_all(
        """SELECT partner, screen_id, name, city, plz, format,
                  ST_X(geom) AS lng, ST_Y(geom) AS lat
           FROM screen LIMIT %s""",
        [max(1, min(limit, 50000))],
    )
    return {"screens": rows}


@router.delete("/inventory/partner/{partner}")
def delete_partner(partner: str) -> dict:
    db.execute("DELETE FROM screen WHERE partner = %s", [partner])
    db.execute("DELETE FROM partner_meta WHERE partner = %s", [partner])
    return {"deleted": partner}


# --- custom POI upload (hybrid input, SPEC §4.3) ----------------------------
@router.post("/pois/custom/import")
async def import_custom_pois(
    file: UploadFile = File(...),
    list_id: str = Form("default"),
    mapping: str = Form(...),
) -> dict:
    data = await file.read()
    parsed = read_spreadsheet(data, file.filename or "")
    m = json.loads(mapping)
    built = build_poi_records(parsed["rows"], m, list_id)
    recs = built["recs"]
    with db.pool.connection() as conn, conn.cursor() as cur:
        cur.execute("DELETE FROM custom_poi WHERE list_id = %s", [list_id])  # replace whole list
        plottable = [r for r in recs if r["lat"] is not None and r["lng"] is not None]
        unplottable = [r for r in recs if r["lat"] is None or r["lng"] is None]
        if plottable:
            cur.executemany(
                """INSERT INTO custom_poi (id, list_id, name, category, subcategory, city, plz, geom)
                   VALUES (%(id)s,%(list_id)s,%(name)s,%(category)s,%(subcategory)s,%(city)s,%(plz)s,
                           ST_SetSRID(ST_MakePoint(%(lng)s,%(lat)s),4326))""",
                plottable,
            )
        for r in unplottable:
            cur.execute(
                """INSERT INTO custom_poi (id, list_id, name, category, subcategory, city, plz, geom)
                   VALUES (%(id)s,%(list_id)s,%(name)s,%(category)s,%(subcategory)s,%(city)s,%(plz)s, NULL)""",
                r,
            )
    return {"list_id": list_id, "imported": len(recs),
            "unplottable": built["no_coord"], "no_id": built["no_id"], "dupes": built["dupes"]}
