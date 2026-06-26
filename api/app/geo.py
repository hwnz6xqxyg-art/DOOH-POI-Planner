"""Translate an Area (bbox / polygon / radius point) into a SQL predicate +
params against a geometry column. Used by POI discovery (SPEC §5.3)."""
from __future__ import annotations

import json

from .schemas import Area, TagFilter


def area_clause(area: Area | None, geom_col: str = "geom") -> tuple[str, list]:
    """Return (sql_fragment, params). Fragment is 'TRUE' when unrestricted."""
    if area is None:
        return "TRUE", []
    if area.bbox and len(area.bbox) == 4:
        return (
            f"ST_Intersects({geom_col}, ST_MakeEnvelope(%s,%s,%s,%s,4326))",
            [area.bbox[0], area.bbox[1], area.bbox[2], area.bbox[3]],
        )
    if area.polygon:
        return (
            f"ST_Intersects({geom_col}, ST_SetSRID(ST_GeomFromGeoJSON(%s),4326))",
            [json.dumps(area.polygon)],
        )
    if area.point:
        p = area.point
        return (
            f"ST_DWithin({geom_col}::geography, "
            f"ST_SetSRID(ST_MakePoint(%s,%s),4326)::geography, %s)",
            [float(p["lng"]), float(p["lat"]), float(p.get("radius_m", 1000))],
        )
    return "TRUE", []


def tag_filter_clauses(filters: list[TagFilter]) -> tuple[list[str], list]:
    """jsonb predicates on the `tags` column (SPEC §5.4)."""
    clauses: list[str] = []
    params: list = []
    for f in filters:
        if not f.key:
            continue
        if f.op == "exists":
            clauses.append("tags ? %s")
            params.append(f.key)
        elif f.op == "ne":
            clauses.append("tags->>%s IS DISTINCT FROM %s")
            params += [f.key, f.value]
        elif f.op == "contains":
            clauses.append("tags->>%s ILIKE %s")
            params += [f.key, f"%{f.value or ''}%"]
        else:  # eq
            clauses.append("tags->>%s = %s")
            params += [f.key, f.value]
    return clauses, params
