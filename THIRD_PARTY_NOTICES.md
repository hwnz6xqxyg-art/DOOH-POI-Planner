# Third-Party Notices

The DOOH POI Planner itself is MIT-licensed (see [`LICENSE`](./LICENSE)). It bundles,
uses, or displays the following third-party software, services, and data. All of them
are free of charge **including commercial use**, subject to the notices below.

## Bundled libraries (inlined in `standalone/index.html`)

### Leaflet 1.9.4 — BSD-2-Clause

<https://leafletjs.com>

```
BSD 2-Clause License

Copyright (c) 2010-2023, Volodymyr Agafonkin
Copyright (c) 2010-2011, CloudMade
All rights reserved.

Redistribution and use in source and binary forms, with or without
modification, are permitted provided that the following conditions are met:

1. Redistributions of source code must retain the above copyright notice, this
   list of conditions and the following disclaimer.

2. Redistributions in binary form must reproduce the above copyright notice,
   this list of conditions and the following disclaimer in the documentation
   and/or other materials provided with the distribution.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
```

### Leaflet.markercluster 1.5.3 — MIT

<https://github.com/Leaflet/Leaflet.markercluster>

```
MIT License

Copyright (c) 2012-2017 Dave Leaver

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

## Map data & services

### POI data — OpenStreetMap (ODbL 1.0)

POI discovery queries the **Overpass API** against OpenStreetMap data.

- Data: **© OpenStreetMap contributors**, licensed under the
  [Open Database License 1.0 (ODbL)](https://opendatacommons.org/licenses/odbl/1-0/).
  Free for commercial use; attribution is required and must accompany published
  maps and shared data extracts. The tool shows it in the map attribution and adds a
  source note to the POI XLSX export.
- Service: the public Overpass instances used
  (`overpass-api.de`, `overpass.kumi.systems`, `overpass.private.coffee`)
  are donation-funded community infrastructure operated under fair-use policies.
  Moderate interactive use (as in this tool) is fine; sustained heavy or automated
  load should move to a self-hosted Overpass instance.

### Basemap — basemap.de / BKG (dl-de/by-2-0)

The background map uses the **basemap.de Web Raster** tiles of the Bundesamt für
Kartographie und Geodäsie (BKG), licensed under the
[Datenlizenz Deutschland – Namensnennung – Version 2.0](https://www.govdata.de/dl-de/by-2-0)
(dl-de/by-2-0): free of charge **including commercial use**, attribution required.

Required attribution (shown in the map's attribution control): **© basemap.de / BKG**

Coverage is Germany (plus border areas) — matching this tool's Germany-only scope.

## Backend stack (`api/` + `web/`, optional full-stack variant)

All dependencies are free for commercial use:

| Package | License |
|---|---|
| FastAPI, pydantic, Vite, TypeScript, Leaflet (npm) | MIT |
| uvicorn, pyosmium | BSD |
| psycopg | LGPL-3.0 (used as a library, unmodified) |
| PostgreSQL | PostgreSQL License |
| PostGIS | GPL-2.0 (runs as a separate database server; not linked into this codebase) |
| Geofabrik OSM extracts | data © OpenStreetMap contributors, ODbL 1.0 |
