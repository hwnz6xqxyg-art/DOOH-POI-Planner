"""ETL: OSM extract (.osm.pbf / .osm) -> PostGIS `poi` table (SPEC §6).

Streams an OSM file with pyosmium, keeps only elements that classify into the v1
taxonomy, computes a representative point (node location, or the average of a
way's node locations), and bulk-loads them. Truncate-and-reload per country
(monthly refresh, SPEC §6.1). Relations are skipped in v1 (documented limitation).

Usage:
    python -m etl.import_osm --pbf /data/germany-latest.osm.pbf --country de
Run from the `api/` directory (so `app.taxonomy` is importable).
"""
from __future__ import annotations

import argparse
import json
import os
import sys

import osmium
import psycopg

from app.config import DATABASE_URL
from app.taxonomy import PREFILTER_KEYS, classify, extract_brand

BATCH = 5000

INSERT_SQL = """
INSERT INTO poi (id, osm_type, name, brand, brand_wikidata, category, subcategory,
                 city, plz, country, tags, geom)
VALUES (%(id)s,%(osm_type)s,%(name)s,%(brand)s,%(brand_wikidata)s,%(category)s,%(subcategory)s,
        %(city)s,%(plz)s,%(country)s,%(tags)s, ST_SetSRID(ST_MakePoint(%(lng)s,%(lat)s),4326))
ON CONFLICT (id) DO UPDATE SET
  name=EXCLUDED.name, brand=EXCLUDED.brand, brand_wikidata=EXCLUDED.brand_wikidata,
  category=EXCLUDED.category, subcategory=EXCLUDED.subcategory, city=EXCLUDED.city,
  plz=EXCLUDED.plz, country=EXCLUDED.country, tags=EXCLUDED.tags, geom=EXCLUDED.geom
"""


class PoiHandler(osmium.SimpleHandler):
    def __init__(self, country: str, conn):
        super().__init__()
        self.country = country
        self.conn = conn
        self.buf: list[dict] = []
        self.counts: dict[str, int] = {}
        self.total = 0

    @staticmethod
    def _tags(o) -> dict:
        return {t.k: t.v for t in o.tags}

    def _maybe(self, tags: dict):
        if not any(k in tags for k in PREFILTER_KEYS):
            return None
        return classify(tags)

    def _emit(self, osm_type: str, oid: int, lon: float, lat: float, tags: dict, cls):
        category, subcategory = cls
        brand, brand_wd = extract_brand(tags)
        self.buf.append({
            "id": f"{osm_type}/{oid}", "osm_type": osm_type,
            "name": tags.get("name"), "brand": brand, "brand_wikidata": brand_wd,
            "category": category, "subcategory": subcategory,
            "city": tags.get("addr:city"), "plz": tags.get("addr:postcode"),
            "country": self.country, "tags": json.dumps(tags), "lng": lon, "lat": lat,
        })
        self.counts[category] = self.counts.get(category, 0) + 1
        self.total += 1
        if len(self.buf) >= BATCH:
            self.flush()

    def node(self, n):
        tags = self._tags(n)
        cls = self._maybe(tags)
        if cls and n.location.valid():
            self._emit("node", n.id, n.location.lon, n.location.lat, tags, cls)

    def way(self, w):
        tags = self._tags(w)
        cls = self._maybe(tags)
        if not cls:
            return
        xs, ys = [], []
        for nr in w.nodes:
            if nr.location.valid():
                xs.append(nr.lon)
                ys.append(nr.lat)
        if xs:
            self._emit("way", w.id, sum(xs) / len(xs), sum(ys) / len(ys), tags, cls)

    def flush(self):
        if not self.buf:
            return
        with self.conn.cursor() as cur:
            cur.executemany(INSERT_SQL, self.buf)
        self.conn.commit()
        self.buf.clear()


def main(argv=None):
    ap = argparse.ArgumentParser(description="Import OSM POIs into PostGIS.")
    ap.add_argument("--pbf", required=True, help="path to .osm.pbf or .osm")
    ap.add_argument("--country", required=True, help="de | at | ch")
    ap.add_argument("--keep", action="store_true",
                    help="keep existing rows for this country (default: replace)")
    args = ap.parse_args(argv)

    if not os.path.exists(args.pbf):
        sys.exit(f"ERROR: file not found: {args.pbf}")

    idx = os.getenv("OSMIUM_INDEX", "flex_mem")
    with psycopg.connect(DATABASE_URL) as conn:
        if not args.keep:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM poi WHERE country = %s", [args.country])
            conn.commit()
        h = PoiHandler(args.country, conn)
        # locations=True so way nodes carry coordinates for the centroid.
        h.apply_file(args.pbf, locations=True, idx=idx)
        h.flush()
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO import_meta (country, source, poi_count, counts) VALUES (%s,%s,%s,%s)",
                [args.country, os.path.basename(args.pbf), h.total, json.dumps(h.counts)],
            )
        conn.commit()

    print(f"Imported {h.total} POIs for '{args.country}': {h.counts}")
    return h.total


if __name__ == "__main__":
    main()
