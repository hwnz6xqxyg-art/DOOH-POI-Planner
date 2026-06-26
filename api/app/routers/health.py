from __future__ import annotations

from fastapi import APIRouter

from .. import db

router = APIRouter()


@router.get("/health")
def health() -> dict:
    out: dict = {"status": "ok"}
    try:
        row = db.fetch_one("SELECT count(*) AS n FROM poi")
        out["poi_count"] = row["n"] if row else 0
        meta = db.fetch_one("SELECT country, poi_count, imported_at FROM import_meta ORDER BY imported_at DESC LIMIT 1")
        out["last_import"] = meta
    except Exception as e:  # DB not ready / not migrated yet
        out["status"] = "degraded"
        out["error"] = str(e)
    return out
