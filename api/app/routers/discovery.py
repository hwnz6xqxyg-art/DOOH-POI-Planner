"""POI discovery: brand search, category tree, area+filter search (SPEC §5)."""
from __future__ import annotations

from fastapi import APIRouter, Query

from .. import db
from ..config import POI_SEARCH_LIMIT, POI_SEARCH_MAX
from ..geo import area_clause, tag_filter_clauses
from ..schemas import PoiSearch
from ..taxonomy import CATEGORY_TREE

router = APIRouter()


@router.get("/brands")
def brands(q: str = "", limit: int = 50) -> dict:
    limit = max(1, min(limit, 200))
    if q:
        rows = db.fetch_all(
            """SELECT brand, brand_wikidata, count(*) AS n
               FROM poi WHERE brand IS NOT NULL AND brand ILIKE %s
               GROUP BY brand, brand_wikidata ORDER BY n DESC, brand LIMIT %s""",
            [f"%{q}%", limit],
        )
    else:
        rows = db.fetch_all(
            """SELECT brand, brand_wikidata, count(*) AS n
               FROM poi WHERE brand IS NOT NULL
               GROUP BY brand, brand_wikidata ORDER BY n DESC, brand LIMIT %s""",
            [limit],
        )
    return {"brands": rows}


@router.get("/categories")
def categories() -> dict:
    counts = db.fetch_all("SELECT category, subcategory, count(*) AS n FROM poi GROUP BY category, subcategory")
    by_cat: dict[str, int] = {}
    by_sub: dict[tuple, int] = {}
    for r in counts:
        by_cat[r["category"]] = by_cat.get(r["category"], 0) + r["n"]
        by_sub[(r["category"], r["subcategory"])] = r["n"]
    tree = []
    for cat in CATEGORY_TREE:
        subs = [{**s, "count": by_sub.get((cat["key"], s["key"]), 0)} for s in cat["subs"]]
        tree.append({**cat, "subs": subs, "count": by_cat.get(cat["key"], 0)})
    return {"categories": tree}


@router.post("/pois/search")
def search(req: PoiSearch) -> dict:
    where: list[str] = []
    params: list = []

    area_sql, area_params = area_clause(req.area)
    where.append(area_sql)
    params += area_params

    if req.brands:
        lowered = [b.lower() for b in req.brands]
        where.append("(lower(brand) = ANY(%s) OR brand_wikidata = ANY(%s))")
        params += [lowered, req.brands]

    if req.categories:
        where.append("(category = ANY(%s) OR subcategory = ANY(%s))")
        params += [req.categories, req.categories]

    tag_sql, tag_params = tag_filter_clauses(req.tag_filters)
    where += tag_sql
    params += tag_params

    where_sql = " AND ".join(where) if where else "TRUE"
    limit = min(req.limit or POI_SEARCH_LIMIT, POI_SEARCH_MAX)

    total = db.fetch_one(f"SELECT count(*) AS n FROM poi WHERE {where_sql}", params)["n"]
    rows = db.fetch_all(
        f"""SELECT id, name, brand, brand_wikidata, category, subcategory, city, plz,
                   ST_X(geom) AS lng, ST_Y(geom) AS lat
            FROM poi WHERE {where_sql} ORDER BY name NULLS LAST LIMIT {limit}""",
        params,
    )
    features = [
        {
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [r["lng"], r["lat"]]},
            "properties": {k: r[k] for k in ("id", "name", "brand", "brand_wikidata",
                                             "category", "subcategory", "city", "plz")},
        }
        for r in rows
    ]
    return {
        "type": "FeatureCollection",
        "features": features,
        "total": total,
        "returned": len(features),
        "capped": total > len(features),
    }
