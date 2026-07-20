#!/usr/bin/env node
// Compact osmium-exported GeoJSONseq into the app's static POI shards.
//
//   node pipeline/compact.js <filtered.geojsonseq> <outdir>
//
// Emits into <outdir>:
//   manifest.json          {generated, counts:{...}}
//   cat-<key>.json         one file per app category; rows [id,name,brand,lat,lng]
//   brands.json            every POI carrying a brand tag (any type);
//                          rows [id,name,brand,lat,lng,catKey|null]
//
// Category keys/tag mapping MIRROR the app's CATEGORIES/classify() — keep in sync.
"use strict";
const fs = require("fs");
const readline = require("readline");
const path = require("path");

const CATS = [
  { key: "chemist",     test: t => t.shop === "chemist" },
  { key: "perfumery",   test: t => t.shop === "perfumery" || t.shop === "cosmetics" },
  { key: "pharmacy",    test: t => t.amenity === "pharmacy" },
  { key: "hairdresser", test: t => t.shop === "hairdresser" },
  { key: "supermarket", test: t => t.shop === "supermarket" },
  { key: "electronics", test: t => t.shop === "electronics" },
  { key: "clothes",     test: t => t.shop === "clothes" },
  { key: "mall",        test: t => t.shop === "mall" || t.shop === "department_store" },
  { key: "airport",     test: t => t.aeroway === "aerodrome" },
  { key: "station",     test: t => t.railway === "station" || t.railway === "halt" },
  { key: "gym",         test: t => t.leisure === "fitness_centre" },
  { key: "university",  test: t => t.amenity === "university" || t.amenity === "college" },
  { key: "cinema",      test: t => t.amenity === "cinema" }
];

function catKey(tags) {
  for (const c of CATS) if (c.test(tags)) return c.key;
  return null;
}

// centroid: Point as-is; Polygon/MultiPolygon via bbox center (good enough for
// proximity planning; matches Overpass "out center" closely for compact shapes)
function centroid(geom) {
  if (!geom) return null;
  if (geom.type === "Point") return [geom.coordinates[1], geom.coordinates[0]];
  let minLa = 90, maxLa = -90, minLo = 180, maxLo = -180, seen = false;
  const walk = c => {
    if (typeof c[0] === "number") {
      seen = true;
      if (c[1] < minLa) minLa = c[1]; if (c[1] > maxLa) maxLa = c[1];
      if (c[0] < minLo) minLo = c[0]; if (c[0] > maxLo) maxLo = c[0];
    } else c.forEach(walk);
  };
  walk(geom.coordinates);
  if (!seen) return null;
  return [(minLa + maxLa) / 2, (minLo + maxLo) / 2];
}

const r6 = n => Math.round(n * 1e6) / 1e6;

async function main() {
  const [, , input, outdir] = process.argv;
  if (!input || !outdir) { console.error("usage: compact.js <in.geojsonseq> <outdir>"); process.exit(1); }
  fs.mkdirSync(outdir, { recursive: true });

  const shards = {};             // key -> rows
  for (const c of CATS) shards[c.key] = [];
  const brands = [];
  const seen = new Set();
  let read = 0, kept = 0;

  const rl = readline.createInterface({ input: fs.createReadStream(input), crlfDelay: Infinity });
  for await (let line of rl) {
    line = line.trim();
    if (!line) continue;
    if (line.charCodeAt(0) === 0x1e) line = line.slice(1);   // RFC 7464 record separator
    let f; try { f = JSON.parse(line); } catch { continue; }
    read++;
    const t = f.properties || {};
    const id = f.id || (t["@id"] || null);
    if (!id || seen.has(id)) continue;
    const ll = centroid(f.geometry);
    if (!ll) continue;
    const [lat, lng] = [r6(ll[0]), r6(ll[1])];
    if (lat < 47 || lat > 55.2 || lng < 5.5 || lng > 15.5) continue;  // sanity: Germany-ish
    const k = catKey(t);
    const name = t.name || t.brand || null;
    const brand = t.brand || null;
    if (k) shards[k].push([id, name, brand, lat, lng]);
    if (brand) brands.push([id, name, brand, lat, lng, k]);
    if (k || brand) { seen.add(id); kept++; }
  }

  const counts = {};
  for (const c of CATS) {
    counts["cat-" + c.key] = shards[c.key].length;
    fs.writeFileSync(path.join(outdir, "cat-" + c.key + ".json"), JSON.stringify(shards[c.key]));
  }
  counts.brands = brands.length;
  fs.writeFileSync(path.join(outdir, "brands.json"), JSON.stringify(brands));
  fs.writeFileSync(path.join(outdir, "manifest.json"), JSON.stringify({
    generated: new Date().toISOString().slice(0, 10),
    source: "OpenStreetMap via Geofabrik germany-latest (ODbL 1.0, © OpenStreetMap contributors)",
    counts
  }, null, 1));
  console.log(`read ${read} features, kept ${kept}`);
  console.log(counts);
}
main().catch(e => { console.error(e); process.exit(1); });
