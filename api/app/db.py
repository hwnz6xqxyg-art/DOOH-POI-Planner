"""Postgres connection pool (psycopg3) + small query helpers."""
from __future__ import annotations

from typing import Any

from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from .config import DATABASE_URL

# Single-user/local: a small pool is plenty. open=False so import never blocks;
# the pool is opened on FastAPI startup (lifespan).
pool = ConnectionPool(DATABASE_URL, min_size=1, max_size=8, open=False, kwargs={"row_factory": dict_row})


def fetch_all(sql: str, params: Any = None) -> list[dict]:
    with pool.connection() as conn, conn.cursor() as cur:
        cur.execute(sql, params)
        return cur.fetchall()


def fetch_one(sql: str, params: Any = None) -> dict | None:
    with pool.connection() as conn, conn.cursor() as cur:
        cur.execute(sql, params)
        return cur.fetchone()


def execute(sql: str, params: Any = None) -> None:
    with pool.connection() as conn, conn.cursor() as cur:
        cur.execute(sql, params)
