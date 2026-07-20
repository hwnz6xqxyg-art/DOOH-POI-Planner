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

// {key, t: OSM tag key, v: accepted values} — MUST mirror CATEGORIES in
// index.html (same keys, same tag mapping; labels live only in the app).
const CATS = [
  { key: "chemist",      t: "shop",    v: ["chemist"] },
  { key: "supermarket",  t: "shop",    v: ["supermarket"] },
  { key: "convenience",  t: "shop",    v: ["convenience"] },
  { key: "kiosk",        t: "shop",    v: ["kiosk"] },
  { key: "bakery",       t: "shop",    v: ["bakery"] },
  { key: "butcher",      t: "shop",    v: ["butcher"] },
  { key: "beverages",    t: "shop",    v: ["beverages"] },
  { key: "clothes",      t: "shop",    v: ["clothes"] },
  { key: "shoes",        t: "shop",    v: ["shoes"] },
  { key: "sports_shop",  t: "shop",    v: ["sports"] },
  { key: "electronics",  t: "shop",    v: ["electronics"] },
  { key: "mobile_phone", t: "shop",    v: ["mobile_phone"] },
  { key: "furniture",    t: "shop",    v: ["furniture"] },
  { key: "doityourself", t: "shop",    v: ["doityourself"] },
  { key: "garden_centre",t: "shop",    v: ["garden_centre"] },
  { key: "perfumery",    t: "shop",    v: ["perfumery", "cosmetics"] },
  { key: "hairdresser",  t: "shop",    v: ["hairdresser"] },
  { key: "beauty",       t: "shop",    v: ["beauty"] },
  { key: "optician",     t: "shop",    v: ["optician"] },
  { key: "jewelry",      t: "shop",    v: ["jewelry"] },
  { key: "books",        t: "shop",    v: ["books"] },
  { key: "toys",         t: "shop",    v: ["toys"] },
  { key: "pet",          t: "shop",    v: ["pet"] },
  { key: "bicycle",      t: "shop",    v: ["bicycle"] },
  { key: "car_dealer",   t: "shop",    v: ["car"] },
  { key: "mall",         t: "shop",    v: ["mall", "department_store"] },
  { key: "pharmacy",     t: "amenity", v: ["pharmacy"] },
  { key: "doctors",      t: "amenity", v: ["doctors"] },
  { key: "dentist",      t: "amenity", v: ["dentist"] },
  { key: "hospital",     t: "amenity", v: ["hospital", "clinic"] },
  { key: "restaurant",   t: "amenity", v: ["restaurant"] },
  { key: "fast_food",    t: "amenity", v: ["fast_food"] },
  { key: "cafe",         t: "amenity", v: ["cafe"] },
  { key: "bar",          t: "amenity", v: ["bar"] },
  { key: "pub",          t: "amenity", v: ["pub"] },
  { key: "nightclub",    t: "amenity", v: ["nightclub"] },
  { key: "fuel",         t: "amenity", v: ["fuel"] },
  { key: "charging",     t: "amenity", v: ["charging_station"] },
  { key: "bank",         t: "amenity", v: ["bank"] },
  { key: "post",         t: "amenity", v: ["post_office"] },
  { key: "cinema",       t: "amenity", v: ["cinema"] },
  { key: "theatre",      t: "amenity", v: ["theatre"] },
  { key: "university",   t: "amenity", v: ["university", "college"] },
  { key: "school",       t: "amenity", v: ["school"] },
  { key: "kindergarten", t: "amenity", v: ["kindergarten"] },
  { key: "casino",       t: "amenity", v: ["casino", "gambling"] },
  { key: "gym",          t: "leisure", v: ["fitness_centre"] },
  { key: "swimming",     t: "leisure", v: ["swimming_pool", "water_park"] },
  { key: "stadium",      t: "leisure", v: ["stadium"] },
  { key: "hotel",        t: "tourism", v: ["hotel"] },
  { key: "museum",       t: "tourism", v: ["museum"] },
  { key: "zoo",          t: "tourism", v: ["zoo"] },
  { key: "theme_park",   t: "tourism", v: ["theme_park"] },
  { key: "station",      t: "railway", v: ["station", "halt"] },
  { key: "airport",      t: "aeroway", v: ["aerodrome"] }
];

function catKey(tags) {
  for (const c of CATS) if (c.v.includes(tags[c.t])) return c.key;
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
