"""v1 category taxonomy + OSM tag -> category normalization (SPEC §6.2).

Shared by the ETL importer (classify every OSM element) and the /api/categories
endpoint (expose the tree). DACH, v1 categories: branded retail POS, transport
hubs, leisure & education. Healthcare/public are deferred (SPEC §17).
"""
from __future__ import annotations

# Category tree surfaced to the UI (German labels; SPEC §10 "German UI text").
CATEGORY_TREE = [
    {
        "key": "branded_retail",
        "label": "Marken-Filialen (POS)",
        "subs": [
            {"key": "chemist", "label": "Drogerie"},
            {"key": "supermarket", "label": "Supermarkt"},
            {"key": "electronics", "label": "Elektronik"},
            {"key": "clothes", "label": "Mode"},
            {"key": "other_branded", "label": "Andere Marken"},
        ],
    },
    {
        "key": "transport_hub",
        "label": "Verkehrsknoten",
        "subs": [
            {"key": "airport", "label": "Flughafen"},
            {"key": "rail_station", "label": "Bahnhof"},
            {"key": "bus_station", "label": "Busbahnhof"},
        ],
    },
    {
        "key": "leisure_education",
        "label": "Freizeit & Bildung",
        "subs": [
            {"key": "gym", "label": "Fitnessstudio"},
            {"key": "university", "label": "Universität / Hochschule"},
            {"key": "school", "label": "Schule"},
            {"key": "stadium", "label": "Stadion"},
            {"key": "cinema", "label": "Kino"},
            {"key": "mall", "label": "Einkaufszentrum"},
        ],
    },
]

# Tag keys that *might* indicate a POI of interest. Used as a cheap prefilter in
# the ETL so the vast majority of OSM elements are skipped before classify().
PREFILTER_KEYS = ("shop", "amenity", "aeroway", "railway", "leisure", "public_transport")


def classify(tags: dict) -> tuple[str, str] | None:
    """Map an OSM tag dict to (category, subcategory), or None if not in scope.

    Order matters: transport + leisure/education win over a generic branded-shop
    fallback, and `mall`/`department_store` are treated as leisure venues per the
    spec, not as branded retail.
    """
    shop = tags.get("shop")
    amenity = tags.get("amenity")
    aeroway = tags.get("aeroway")
    railway = tags.get("railway")
    leisure = tags.get("leisure")
    ptype = tags.get("public_transport")
    brand = tags.get("brand") or tags.get("brand:wikidata")

    # transport hubs
    if aeroway == "aerodrome":
        return ("transport_hub", "airport")
    if railway in ("station", "halt") or (ptype == "station" and tags.get("train") == "yes"):
        return ("transport_hub", "rail_station")
    if amenity == "bus_station":
        return ("transport_hub", "bus_station")

    # leisure & education
    if leisure == "fitness_centre" or (leisure == "sports_centre" and tags.get("sport") == "fitness"):
        return ("leisure_education", "gym")
    if amenity in ("university", "college"):
        return ("leisure_education", "university")
    if amenity == "school":
        return ("leisure_education", "school")
    if leisure == "stadium":
        return ("leisure_education", "stadium")
    if amenity == "cinema":
        return ("leisure_education", "cinema")
    if shop in ("mall", "department_store"):
        return ("leisure_education", "mall")

    # branded retail POS
    if shop == "chemist":
        return ("branded_retail", "chemist")
    if shop == "supermarket":
        return ("branded_retail", "supermarket")
    if shop == "electronics":
        return ("branded_retail", "electronics")
    if shop == "clothes":
        return ("branded_retail", "clothes")
    # any other retail shop that carries a brand stays discoverable (SPEC §6.2)
    if shop and brand:
        return ("branded_retail", "other_branded")

    return None


def extract_brand(tags: dict) -> tuple[str | None, str | None]:
    """(brand, brand_wikidata) — falls back to operator for name-less chains."""
    brand = tags.get("brand") or tags.get("operator")
    return (brand or None, tags.get("brand:wikidata") or None)
