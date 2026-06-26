"""Runtime configuration, read from the environment (SPEC §12)."""
from __future__ import annotations

import os

from dotenv import load_dotenv

load_dotenv()


def _db_url() -> str:
    url = os.getenv("DATABASE_URL")
    if url:
        return url
    host = os.getenv("PGHOST", "localhost")
    port = os.getenv("PGPORT", "5432")
    db = os.getenv("PGDATABASE", "dooh")
    user = os.getenv("PGUSER", "dooh")
    pw = os.getenv("PGPASSWORD", "dooh")
    return f"postgresql://{user}:{pw}@{host}:{port}/{db}"


DATABASE_URL: str = _db_url()

# Radius model (donor §5 / SPEC §8). Metres.
RADIUS_DEFAULT = int(os.getenv("RADIUS_DEFAULT", "500"))
RADIUS_MIN = int(os.getenv("RADIUS_MIN", "50"))
RADIUS_MAX = int(os.getenv("RADIUS_MAX", "5000"))

# Caps to keep a single query sane (SPEC §5.5 / §8).
POI_SEARCH_LIMIT = int(os.getenv("POI_SEARCH_LIMIT", "2000"))
POI_SEARCH_MAX = int(os.getenv("POI_SEARCH_MAX", "20000"))
MATCH_ANCHOR_MAX = int(os.getenv("MATCH_ANCHOR_MAX", "20000"))

# CORS for the vite dev server (prod serves same-origin behind nginx).
CORS_ORIGINS = [
    o.strip()
    for o in os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",")
    if o.strip()
]
