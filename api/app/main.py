"""DOOH POI Planner API (SPEC §2). FastAPI + PostGIS."""
from __future__ import annotations

import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from . import db
from .config import CORS_ORIGINS
from .routers import discovery, health, inventory, matching

SCHEMA_SQL = Path(__file__).resolve().parent.parent / "db" / "schema.sql"


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.pool.open()
    if os.getenv("AUTO_MIGRATE", "1") == "1":
        try:
            with db.pool.connection() as conn:
                conn.execute(SCHEMA_SQL.read_text())
        except Exception as e:  # pragma: no cover - surfaced via /health
            print(f"[startup] schema apply skipped/failed: {e}")
    yield
    db.pool.close()


app = FastAPI(title="DOOH POI Planner", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router, prefix="/api")
app.include_router(discovery.router, prefix="/api")
app.include_router(inventory.router, prefix="/api")
app.include_router(matching.router, prefix="/api")

# Optional: serve a built SPA from the same origin if WEB_DIR is present
# (compose uses a separate nginx service; this is for single-container runs).
_web = os.getenv("WEB_DIR")
if _web and Path(_web).is_dir():
    app.mount("/", StaticFiles(directory=_web, html=True), name="web")
