"""Pydantic request/response models (SPEC §5, §8, §9)."""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class Area(BaseModel):
    """One of bbox / polygon / radius-around-point (SPEC §5.3). All optional;
    an empty Area means 'no spatial restriction'."""
    bbox: list[float] | None = Field(None, description="[minLng,minLat,maxLng,maxLat]")
    polygon: dict | None = Field(None, description="GeoJSON Polygon/MultiPolygon geometry")
    point: dict | None = Field(None, description='{"lng":..,"lat":..,"radius_m":..}')


class TagFilter(BaseModel):
    key: str
    op: Literal["eq", "ne", "exists", "contains"] = "eq"
    value: str | None = None


class PoiSearch(BaseModel):
    area: Area | None = None
    brands: list[str] = []           # match brand / brand:wikidata / name
    categories: list[str] = []       # category or subcategory keys
    tag_filters: list[TagFilter] = []
    limit: int | None = None


class Anchor(BaseModel):
    id: str
    radius: int | None = None        # per-anchor override (SPEC §8)


class MatchRequest(BaseModel):
    anchors: list[Anchor] = []
    global_radius: int | None = None
    hidden_partners: list[str] = []


class InventoryImport(BaseModel):
    partner: str
    mapping: dict[str, str]
    headers: list[str] = []


class CustomPoiImport(BaseModel):
    list_id: str = "default"
    mapping: dict[str, str]
