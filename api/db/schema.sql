-- DOOH POI Planner — PostGIS schema (SPEC §4)
-- Idempotent: safe to apply repeatedly.

CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- ---------------------------------------------------------------------------
-- poi — OSM-derived points of interest (the discoverable anchors). SPEC §4.1
-- id = "{osm_type}/{osm_id}", e.g. "node/240095754".
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS poi (
  id              text PRIMARY KEY,
  osm_type        text NOT NULL,                       -- node | way | relation
  name            text,
  brand           text,                                -- drives brand search
  brand_wikidata  text,                                -- clean brand identity
  category        text NOT NULL,                       -- normalized (SPEC §6.2)
  subcategory     text,
  city            text,
  plz             text,
  country         text,                                -- de | at | ch
  tags            jsonb NOT NULL DEFAULT '{}'::jsonb,   -- full tag set
  geom            geometry(Point, 4326) NOT NULL
);
CREATE INDEX IF NOT EXISTS poi_geom_gix    ON poi USING gist (geom);
CREATE INDEX IF NOT EXISTS poi_category_ix ON poi (category);
CREATE INDEX IF NOT EXISTS poi_brand_trgm  ON poi USING gin (brand gin_trgm_ops);
CREATE INDEX IF NOT EXISTS poi_name_trgm   ON poi USING gin (name gin_trgm_ops);
CREATE INDEX IF NOT EXISTS poi_tags_gin    ON poi USING gin (tags);

-- ---------------------------------------------------------------------------
-- custom_poi — manually uploaded anchors (hybrid input). SPEC §4.3
-- geom NULL = un-plottable; kept, never invented.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS custom_poi (
  id          text PRIMARY KEY,                         -- "custom/{list}/{id}"
  list_id     text NOT NULL,                            -- replaces like donor customShops
  name        text,
  category    text NOT NULL DEFAULT 'custom',
  subcategory text,
  city        text,
  plz         text,
  tags        jsonb NOT NULL DEFAULT '{}'::jsonb,
  geom        geometry(Point, 4326),
  created_at  timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS custom_poi_geom_gix ON custom_poi USING gist (geom);
CREATE INDEX IF NOT EXISTS custom_poi_list_ix  ON custom_poi (list_id);

-- ---------------------------------------------------------------------------
-- screen — DOOH inventory (ported canonical record). SPEC §4.2
-- Key = (partner, screen_id): partners may reuse ids without colliding.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS screen (
  partner   text NOT NULL,
  screen_id text NOT NULL,
  name      text,
  city      text,
  plz       text,
  address   text,
  format    text,
  geom      geometry(Point, 4326) NOT NULL,
  PRIMARY KEY (partner, screen_id)
);
CREATE INDEX IF NOT EXISTS screen_geom_gix   ON screen USING gist (geom);
CREATE INDEX IF NOT EXISTS screen_partner_ix ON screen (partner);

-- ---------------------------------------------------------------------------
-- partner_meta — per-partner confirmed column mapping, for round-trip export
-- (SPEC §9.4). mapping = {canonicalField: sourceHeader}.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS partner_meta (
  partner        text PRIMARY KEY,
  mapping        jsonb NOT NULL,
  source_headers jsonb,
  screen_count   integer NOT NULL DEFAULT 0,
  updated_at     timestamptz NOT NULL DEFAULT now()
);

-- ---------------------------------------------------------------------------
-- import_meta — ETL provenance / data freshness (SPEC §6.1).
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS import_meta (
  id           serial PRIMARY KEY,
  country      text,
  source       text,
  poi_count    integer,
  counts       jsonb,
  imported_at  timestamptz NOT NULL DEFAULT now()
);
