.PHONY: local up down build logs etl-sample etl-de etl-at etl-ch test

# ---- No-Docker (macOS native) --------------------------------------------
local:         ## set up + run everything natively (no Docker) on :8000
	./scripts/run-local.sh

# ---- Docker ---------------------------------------------------------------
up:            ## build + start the full stack (db, api, web) on localhost
	docker compose up -d --build

down:          ## stop the stack
	docker compose down

build:
	docker compose build

logs:
	docker compose logs -f api

# Quick smoke test: import the bundled 5-POI sample fixture (no download).
etl-sample:
	cp api/tests/sample.osm data/sample.osm
	docker compose run --rm etl --pbf /data/sample.osm --country de

# OSM imports — drop the extracts in ./data first (Geofabrik .osm.pbf).
etl-de:
	docker compose run --rm etl --pbf /data/germany-latest.osm.pbf --country de

etl-at:
	docker compose run --rm etl --pbf /data/austria-latest.osm.pbf --country at

etl-ch:
	docker compose run --rm etl --pbf /data/switzerland-latest.osm.pbf --country ch

test:          ## backend unit tests
	cd api && python -m pytest -q
