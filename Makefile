.PHONY: up down build logs etl-de etl-at etl-ch test

up:            ## build + start the full stack (db, api, web) on localhost
	docker compose up -d --build

down:          ## stop the stack
	docker compose down

build:
	docker compose build

logs:
	docker compose logs -f api

# OSM imports — drop the extracts in ./data first (Geofabrik .osm.pbf).
etl-de:
	docker compose run --rm etl --pbf /data/germany-latest.osm.pbf --country de

etl-at:
	docker compose run --rm etl --pbf /data/austria-latest.osm.pbf --country at

etl-ch:
	docker compose run --rm etl --pbf /data/switzerland-latest.osm.pbf --country ch

test:          ## backend unit tests
	cd api && python -m pytest -q
