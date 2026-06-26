#!/usr/bin/env python3
"""
One-shot build step: Telekom shops .xlsx -> embedded JSON baked into index.html.

Zero install: Python stdlib only (zipfile + xml.etree). An .xlsx is a zip of XML
parts; we read the worksheet + shared strings directly, so no openpyxl/pandas.

Reads sheet `Shops_with_geocode_fields` and writes a lean per-shop JSON array
between the BUILD:DATA markers in index.html.

Critical data rules (see SPEC.md sec.3):
  - Coordinates come ONLY from `Latitude2`/`Longitude3`. The plain
    `Latitude`/`Longitude` columns are a 22-row decoy and are ignored.
  - The 4 `FAILED`-geocode rows have no usable coords -> lat/lng = null.
    Coordinates are NEVER invented.
  - Key = `Shop_Row_ID` (unique). `Bezeichnung` is not unique; never key on it.

Usage:  python3 build/build-shops.py
"""

import json
import os
import re
import sys
import zipfile
from xml.etree import ElementTree as ET

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

# Default input locations (the upload dir is where the source file was provided).
XLSX_CANDIDATES = [
    os.path.join(ROOT, "Telekom_Shops_Strassen_Geokoordinaten.xlsx"),
    os.path.join(ROOT, "data", "Telekom_Shops_Strassen_Geokoordinaten.xlsx"),
    "/root/.claude/uploads/045eee00-3939-5c97-941d-a1c6fa17ee67/"
    "40ac7c81-Telekom_Shops_Strassen_Geokoordinaten.xlsx",
]
INDEX_HTML = os.path.join(ROOT, "index.html")
SHEET_NAME = "Shops_with_geocode_fields"

NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}

# Source column -> output key. Coordinates handled separately.
FIELD_MAP = {
    "Shop_Row_ID": "id",
    "Bezeichnung": "name",
    "Ort": "ort",
    "PLZ": "plz",
    "Region": "region",
    "Bundesland": "bundesland",
    "PA/TS": "paTs",
    "Betreiber": "betreiber",
    "Status": "status",
    "Geocode_Quality": "geocodeQuality",
}


def col_index(ref):
    """'C12' -> 2 (zero-based column index)."""
    letters = "".join(ch for ch in ref if ch.isalpha())
    n = 0
    for ch in letters:
        n = n * 26 + (ord(ch) - 64)
    return n - 1


def find_xlsx():
    for p in XLSX_CANDIDATES:
        if os.path.exists(p):
            return p
    sys.exit(
        "ERROR: source .xlsx not found. Place "
        "'Telekom_Shops_Strassen_Geokoordinaten.xlsx' in the repo root "
        "(or data/) and re-run."
    )


def load_rows(xlsx_path):
    z = zipfile.ZipFile(xlsx_path)

    # shared strings
    shared = []
    if "xl/sharedStrings.xml" in z.namelist():
        sst = ET.fromstring(z.read("xl/sharedStrings.xml"))
        for si in sst.findall("m:si", NS):
            shared.append("".join(t.text or "" for t in si.findall(".//m:t", NS)))

    # locate the worksheet path for SHEET_NAME via workbook + rels
    wb = ET.fromstring(z.read("xl/workbook.xml"))
    rels = ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))
    rid_to_target = {
        r.get("Id"): r.get("Target")
        for r in rels.findall(
            "{http://schemas.openxmlformats.org/package/2006/relationships}Relationship"
        )
    }
    R = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"
    sheet_path = None
    for s in wb.findall(".//m:sheets/m:sheet", NS):
        if s.get("name") == SHEET_NAME:
            target = rid_to_target.get(s.get(R))
            sheet_path = "xl/" + target.lstrip("/") if target else None
            break
    if not sheet_path:
        sys.exit("ERROR: sheet '%s' not found in workbook." % SHEET_NAME)

    sheet = ET.fromstring(z.read(sheet_path))

    def cell_value(c):
        t = c.get("t")
        if t == "inlineStr":
            isel = c.find("m:is", NS)
            return "".join(x.text or "" for x in isel.findall(".//m:t", NS)) if isel is not None else None
        v = c.find("m:v", NS)
        if v is None:
            return None
        if t == "s":
            return shared[int(v.text)]
        return v.text

    rows = sheet.findall(".//m:sheetData/m:row", NS)
    if not rows:
        sys.exit("ERROR: worksheet has no rows.")

    # header
    header = {}
    for c in rows[0].findall("m:c", NS):
        header[col_index(c.get("r"))] = cell_value(c)

    records = []
    for r in rows[1:]:
        rec = {}
        for c in r.findall("m:c", NS):
            ci = col_index(c.get("r"))
            name = header.get(ci)
            if name is not None:
                rec[name] = cell_value(c)
        records.append(rec)
    return records


def to_num(v):
    if v in (None, ""):
        return None
    try:
        f = float(v)
        return f
    except (TypeError, ValueError):
        return None


def s(v):
    if v is None:
        return None
    v = str(v).strip()
    return v if v else None


def build_shops(records):
    shops = []
    for rec in records:
        lat = to_num(rec.get("Latitude2"))  # canonical coords (NOT the decoy)
        lng = to_num(rec.get("Longitude3"))
        shop = {}
        for src, key in FIELD_MAP.items():
            shop[key] = s(rec.get(src))
        # numeric id
        idnum = to_num(rec.get("Shop_Row_ID"))
        shop["id"] = int(idnum) if idnum is not None else shop.get("id")
        # coords: null when missing, never invented
        shop["lat"] = lat
        shop["lng"] = lng
        shops.append(shop)
    # deterministic order by id
    shops.sort(key=lambda x: (x["id"] is None, x["id"]))
    return shops


def summarize(shops):
    geocoded = sum(1 for s_ in shops if s_["lat"] is not None and s_["lng"] is not None)
    failed = sum(1 for s_ in shops if s_.get("geocodeQuality") == "FAILED")

    def counts(key):
        out = {}
        for s_ in shops:
            out[s_.get(key)] = out.get(s_.get(key), 0) + 1
        return out

    print("Shops total:      %d" % len(shops))
    print("Geocoded (coords):%d" % geocoded)
    print("FAILED geocode:   %d" % failed)
    print("Status:           %s" % counts("status"))
    print("Region:           %s" % counts("region"))
    print("Geocode_Quality:  %s" % counts("geocodeQuality"))
    # sanity guard against silently shipping bad data
    ids = [s_["id"] for s_ in shops]
    if len(set(ids)) != len(ids):
        sys.exit("ERROR: Shop_Row_ID not unique after build — aborting.")
    return geocoded, failed


def bake(shops):
    payload = "window.SHOPS = " + json.dumps(shops, ensure_ascii=False, separators=(",", ":")) + ";"
    block = "/* BUILD:DATA:START */\n" + payload + "\n/* BUILD:DATA:END */"

    if not os.path.exists(INDEX_HTML):
        sys.exit(
            "NOTE: index.html does not exist yet. Build the HTML shell first, "
            "then re-run to bake. (Shops JSON not written.)"
        )

    with open(INDEX_HTML, "r", encoding="utf-8") as f:
        html = f.read()

    pat = re.compile(r"/\* BUILD:DATA:START \*/.*?/\* BUILD:DATA:END \*/", re.DOTALL)
    if not pat.search(html):
        sys.exit("ERROR: BUILD:DATA markers not found in index.html.")
    html = pat.sub(lambda _: block, html, count=1)

    with open(INDEX_HTML, "w", encoding="utf-8") as f:
        f.write(html)
    print("Baked %d shops into %s" % (len(shops), os.path.relpath(INDEX_HTML, ROOT)))


def main():
    xlsx = find_xlsx()
    print("Source: %s" % xlsx)
    records = load_rows(xlsx)
    shops = build_shops(records)
    summarize(shops)
    bake(shops)


if __name__ == "__main__":
    main()
