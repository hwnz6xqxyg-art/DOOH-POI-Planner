import L from "leaflet";
import "leaflet/dist/leaflet.css";
import "@geoman-io/leaflet-geoman-free";
import "@geoman-io/leaflet-geoman-free/dist/leaflet-geoman.css";
import "./styles.css";
import {
  api, downloadCsv, Cat, PoiFeature, MatchResult, ScreenPoint,
} from "./api";

// ---------------------------------------------------------------- helpers ---
const $ = (id: string) => document.getElementById(id)!;
const debounce = <T extends (...a: any[]) => void>(fn: T, ms: number) => {
  let t: number; return (...a: Parameters<T>) => { clearTimeout(t); t = setTimeout(() => fn(...a), ms); };
};
function toast(msg: string, kind: "ok" | "warn" | "err" = "ok") {
  const el = $("toast"); el.textContent = msg; el.className = `toast ${kind}`;
  setTimeout(() => el.classList.add("hidden"), 3200);
}
type Area = { bbox?: number[]; polygon?: any; point?: any } | null;

// ------------------------------------------------------------------ state ---
const state = {
  brands: new Set<string>(),
  cats: new Set<string>(),
  area: null as Area,
  tagFilters: [] as { key: string; op: string; value: string }[],
  pois: [] as PoiFeature[],
  anchors: new Map<string, { radius: number | null; feature: PoiFeature | null }>(),
  globalRadius: 500,
  hiddenPartners: new Set<string>(),
  matched: new Set<string>(),  // screen keys "partner||screen_id" currently in radius
};

function saveState() {
  try {
    localStorage.setItem("dooh-poi-planner", JSON.stringify({
      globalRadius: state.globalRadius,
      anchors: Array.from(state.anchors.entries()).map(([id, a]) => [id, a.radius]),
      hidden: Array.from(state.hiddenPartners),
    }));
  } catch { /* private mode */ }
}
function loadState() {
  try {
    const o = JSON.parse(localStorage.getItem("dooh-poi-planner") || "{}");
    if (typeof o.globalRadius === "number") state.globalRadius = o.globalRadius;
    if (Array.isArray(o.hidden)) o.hidden.forEach((p: string) => state.hiddenPartners.add(p));
    if (Array.isArray(o.anchors)) o.anchors.forEach(([id, r]: [string, number | null]) => state.anchors.set(id, { radius: r, feature: null }));
  } catch { /* ignore */ }
}

// -------------------------------------------------------------------- map ---
const map = L.map("map", { preferCanvas: true }).setView([51.1, 10.4], 6); // DACH
L.tileLayer("https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png", {
  attribution: "&copy; OpenStreetMap &copy; CARTO", subdomains: "abcd", maxZoom: 19,
}).addTo(map);

const poiLayer = L.layerGroup().addTo(map);
const circleLayer = L.layerGroup().addTo(map);
const screenLayer = L.layerGroup().addTo(map);
const poiMarkers = new Map<string, L.CircleMarker>();
const anchorCircles = new Map<string, L.Circle>();
const screenMarkers = new Map<string, L.CircleMarker>();

const POI_BASE = { radius: 6, color: "#e20074", weight: 1, fillColor: "#e20074", fillOpacity: 0.55 };
const POI_ANCHOR = { radius: 7, color: "#ffffff", weight: 2, fillColor: "#e20074", fillOpacity: 1 };
const SCREEN_BASE = { radius: 3, stroke: false, fillColor: "#34d1e0", fillOpacity: 0.5 };
const SCREEN_HI = { radius: 4.5, stroke: true, color: "#ffffff", weight: 1, fillColor: "#34d1e0", fillOpacity: 1 };

// ----------------------------------------------------------- POI rendering --
function renderPois() {
  poiLayer.clearLayers(); poiMarkers.clear();
  state.pois.forEach((f) => {
    const [lng, lat] = f.geometry.coordinates;
    const id = f.properties.id;
    const m = L.circleMarker([lat, lng], state.anchors.has(id) ? POI_ANCHOR : POI_BASE);
    m.bindPopup(() => poiPopup(f));
    m.on("click", () => toggleAnchor(f));
    poiLayer.addLayer(m);
    poiMarkers.set(id, m);
  });
}
function poiPopup(f: PoiFeature): HTMLElement {
  const p = f.properties;
  const wrap = document.createElement("div");
  const isAnchor = state.anchors.has(p.id);
  wrap.innerHTML = `<strong>${esc(p.name || p.brand || p.id)}</strong>
    <div class="pp-meta">${esc(p.subcategory || p.category)}${p.city ? " · " + esc(p.city) : ""}</div>`;
  const btn = document.createElement("button");
  btn.className = "btn sm"; btn.textContent = isAnchor ? "Anker entfernen" : "Als Anker";
  btn.onclick = () => { toggleAnchor(f); map.closePopup(); };
  wrap.appendChild(btn);
  if (isAnchor) {
    const a = state.anchors.get(p.id)!;
    const row = document.createElement("div"); row.className = "pp-meta"; row.style.marginTop = "8px";
    const r = a.radius ?? state.globalRadius;
    row.innerHTML = `Radius <b class="rv">${r}</b> m`;
    const sl = document.createElement("input");
    sl.type = "range"; sl.min = "50"; sl.max = "5000"; sl.step = "50"; sl.value = String(r);
    sl.className = "pp-radius";
    sl.oninput = () => {
      const v = parseInt(sl.value, 10);
      state.anchors.get(p.id)!.radius = v;
      (row.querySelector(".rv") as HTMLElement).textContent = String(v);
      drawCircles(); doMatch(); saveState();
    };
    wrap.appendChild(row); wrap.appendChild(sl);
  }
  return wrap;
}

function toggleAnchor(f: PoiFeature) {
  const id = f.properties.id;
  if (state.anchors.has(id)) state.anchors.delete(id);
  else state.anchors.set(id, { radius: null, feature: f });
  const m = poiMarkers.get(id);
  if (m) m.setStyle(state.anchors.has(id) ? POI_ANCHOR : POI_BASE);
  drawCircles(); doMatch(); saveState(); refreshAnchorButtons();
}

function drawCircles() {
  circleLayer.clearLayers(); anchorCircles.clear();
  state.anchors.forEach((a, id) => {
    const f = a.feature || state.pois.find((p) => p.properties.id === id);
    if (!f) return;
    const [lng, lat] = f.geometry.coordinates;
    const c = L.circle([lat, lng], { radius: a.radius ?? state.globalRadius, color: "#e20074", weight: 1, fillOpacity: 0.06 });
    circleLayer.addLayer(c); anchorCircles.set(id, c);
  });
}

// --------------------------------------------------------- screen rendering -
async function loadScreens() {
  const { screens } = await api.screens();
  screenLayer.clearLayers(); screenMarkers.clear();
  screens.forEach((s: ScreenPoint) => {
    if (state.hiddenPartners.has(s.partner)) return;
    const m = L.circleMarker([s.lat, s.lng], SCREEN_BASE);
    m.bindPopup(`<strong>${esc(s.name || s.screen_id)}</strong><div class="pp-meta">${esc(s.partner)} · ${esc(s.screen_id)}${s.format ? " · " + esc(s.format) : ""}</div>`);
    screenLayer.addLayer(m);
    screenMarkers.set(`${s.partner}||${s.screen_id}`, m);
  });
  applyMatchHighlight();
}
function applyMatchHighlight() {
  screenMarkers.forEach((m, key) => m.setStyle(state.matched.has(key) ? SCREEN_HI : SCREEN_BASE));
}

// ------------------------------------------------------------------ match ---
const doMatch = debounce(async () => {
  if (!state.anchors.size) { state.matched.clear(); applyMatchHighlight(); updatePlanCard(null); return; }
  const anchors = Array.from(state.anchors.entries()).map(([id, a]) => ({ id, radius: a.radius }));
  const res: MatchResult = await api.match({
    anchors, global_radius: state.globalRadius, hidden_partners: Array.from(state.hiddenPartners),
  });
  if (res.error) { toast(res.error, "err"); return; }
  state.matched = new Set(res.screens.map((s) => `${s.partner}||${s.screen_id}`));
  applyMatchHighlight();
  updatePlanCard(res);
}, 250);

function updatePlanCard(res: MatchResult | null) {
  $("pcAnchors").textContent = String(state.anchors.size);
  $("pcScreens").textContent = res ? String(res.stats.screens_total) : "0";
  $("pcCoverage").textContent = res && res.stats.anchors_total ? `${res.stats.coverage_pct}%` : "–";
  const has = !!res && res.stats.screens_total > 0;
  ($("exportCsv") as HTMLButtonElement).disabled = !has;
  ($("exportRound") as HTMLButtonElement).disabled = !has;
}

// ------------------------------------------------------------- discovery UI -
const onBrandInput = debounce(async () => {
  const q = ($("brandInput") as HTMLInputElement).value.trim();
  const box = $("brandSuggest");
  if (!q) { box.innerHTML = ""; return; }
  const { brands } = await api.brands(q);
  box.innerHTML = brands.map((b) => `<div data-b="${esc(b.brand)}">${esc(b.brand)}<span class="n">${b.n}</span></div>`).join("");
  Array.from(box.querySelectorAll("div")).forEach((d) =>
    d.addEventListener("click", () => { addBrand(d.getAttribute("data-b")!); box.innerHTML = ""; ($("brandInput") as HTMLInputElement).value = ""; }));
}, 200);

function addBrand(b: string) { state.brands.add(b); renderBrandChips(); }
function renderBrandChips() {
  $("brandChips").innerHTML = "";
  state.brands.forEach((b) => {
    const c = document.createElement("span"); c.className = "chip"; c.textContent = b;
    c.onclick = () => { state.brands.delete(b); renderBrandChips(); };
    $("brandChips").appendChild(c);
  });
}

function renderCatTree(cats: Cat[]) {
  const root = $("catTree"); root.innerHTML = "";
  cats.forEach((cat) => {
    const g = document.createElement("div"); g.className = "cat-group";
    const head = document.createElement("label");
    head.innerHTML = `<input type="checkbox" data-cat="${cat.key}"><span>${esc(cat.label)}</span><span class="cnt">${cat.count}</span>`;
    g.appendChild(head);
    cat.subs.forEach((s) => {
      const sub = document.createElement("label"); sub.className = "cat-sub";
      sub.innerHTML = `<input type="checkbox" data-sub="${s.key}"><span>${esc(s.label)}</span><span class="cnt">${s.count}</span>`;
      const cb = sub.querySelector("input") as HTMLInputElement;
      cb.onchange = () => { cb.checked ? state.cats.add(s.key) : state.cats.delete(s.key); };
      g.appendChild(sub);
    });
    const head_cb = head.querySelector("input") as HTMLInputElement;
    head_cb.onchange = () => {
      cat.subs.forEach((s) => {
        const el = g.querySelector(`input[data-sub="${s.key}"]`) as HTMLInputElement;
        el.checked = head_cb.checked; el.checked ? state.cats.add(s.key) : state.cats.delete(s.key);
      });
    };
    root.appendChild(g);
  });
}

function addTagFilterRow(key = "", op = "exists", value = "") {
  const wrap = $("tagFilters");
  const row = document.createElement("div"); row.className = "tf";
  row.innerHTML = `<input type="text" placeholder="tag (z. B. opening_hours)" value="${esc(key)}" style="flex:2">
    <select style="flex:1"><option value="exists">vorhanden</option><option value="eq">=</option><option value="ne">≠</option><option value="contains">~</option></select>
    <input type="text" placeholder="Wert" value="${esc(value)}" style="flex:2">
    <button class="btn sm ghost">✕</button>`;
  (row.querySelector("select") as HTMLSelectElement).value = op;
  (row.querySelector("button") as HTMLButtonElement).onclick = () => row.remove();
  wrap.appendChild(row);
}
function collectTagFilters() {
  return Array.from($("tagFilters").querySelectorAll(".tf")).map((r) => {
    const inps = r.querySelectorAll("input"); const sel = r.querySelector("select") as HTMLSelectElement;
    return { key: (inps[0] as HTMLInputElement).value.trim(), op: sel.value, value: (inps[1] as HTMLInputElement).value.trim() };
  }).filter((f) => f.key);
}

async function searchPois() {
  const body = {
    area: state.area || undefined,
    brands: Array.from(state.brands),
    categories: Array.from(state.cats),
    tag_filters: collectTagFilters(),
  };
  $("poiResult").textContent = "Suche …";
  const res = await api.search(body);
  state.pois = res.features;
  renderPois(); drawCircles();
  const el = $("poiResult"); el.className = "result " + (res.capped ? "warn" : "ok");
  el.textContent = `${res.returned} POIs${res.capped ? ` (von ${res.total} – Gebiet/Filter eingrenzen)` : ""}`;
  refreshAnchorButtons();
}
function refreshAnchorButtons() {
  ($("selectAllPois") as HTMLButtonElement).disabled = state.pois.length === 0;
  ($("clearAnchors") as HTMLButtonElement).disabled = state.anchors.size === 0;
}

// ---------------------------------------------------------------- area UI ---
function setAreaFromView() {
  const b = map.getBounds();
  state.area = { bbox: [b.getWest(), b.getSouth(), b.getEast(), b.getNorth()] };
  $("areaInfo").textContent = "Gebiet = aktueller Kartenausschnitt";
}
function enableDraw() {
  (map as any).pm.enableDraw("Polygon", { snappable: true });
}
map.on("pm:create" as any, (e: any) => {
  (map as any).pm.disableDraw();
  circleLayer.eachLayer; // noop keep import
  const gj = e.layer.toGeoJSON();
  state.area = { polygon: gj.geometry };
  $("areaInfo").textContent = "Gebiet = gezeichnetes Polygon";
  e.layer.setStyle?.({ color: "#e20074", weight: 1, fillOpacity: 0.04 });
});

// ------------------------------------------------------------- inventory UI -
let pendingFile: File | null = null;
let pendingMode: "screens" | "pois" = "screens";

function pickFile(mode: "screens" | "pois") {
  pendingMode = mode;
  const inp = $("fileInput") as HTMLInputElement;
  inp.value = ""; inp.click();
}
($("fileInput") as HTMLInputElement).addEventListener("change", async (e) => {
  const f = (e.target as HTMLInputElement).files?.[0];
  if (!f) return;
  pendingFile = f;
  const fd = new FormData(); fd.append("file", f); fd.append("mode", pendingMode);
  toast("Lese Datei …", "warn");
  const pv = await api.previewForm(fd);
  openMappingModal(pv);
});

function openMappingModal(pv: any) {
  $("mapTitle").textContent = pendingMode === "pois" ? "POI-Liste – Spalten zuordnen" : "Inventar – Spalten zuordnen";
  $("mapSub").textContent = `Blatt „${pv.sheet}" · ${pv.row_count} Zeilen`;
  $("mapPartnerRow").classList.toggle("hidden", pendingMode === "pois");
  if (pendingMode === "screens") ($("mapPartner") as HTMLInputElement).value = pv.partner_guess || "";
  const opt = (sel: string) => `<option value="">— (keine) —</option>` +
    (pv.headers as string[]).map((h) => `<option ${h === sel ? "selected" : ""}>${esc(h)}</option>`).join("");
  $("mapFields").innerHTML = (pv.fields as any[]).map((f) =>
    `<div class="maprow"><div class="mlabel">${f.key}${f.required ? ' <span class="req">*</span>' : ""}</div>
     <select data-field="${f.key}">${opt(pv.mapping[f.key] || "")}</select></div>`).join("");
  $("mapModal").classList.remove("hidden");
}
function currentMapping() {
  const m: Record<string, string> = {};
  $("mapFields").querySelectorAll("select").forEach((s) => {
    const sel = s as HTMLSelectElement; if (sel.value) m[sel.getAttribute("data-field")!] = sel.value;
  });
  return m;
}
async function doImport() {
  if (!pendingFile) return;
  const mapping = currentMapping();
  const fd = new FormData(); fd.append("file", pendingFile); fd.append("mapping", JSON.stringify(mapping));
  ($("mapImport") as HTMLButtonElement).disabled = true;
  try {
    if (pendingMode === "pois") {
      fd.append("list_id", "default");
      const r = await api.importPoisForm(fd);
      toast(`${r.imported} POIs importiert${r.unplottable ? ` · ${r.unplottable} ohne Koordinaten` : ""}`, "ok");
    } else {
      const partner = ($("mapPartner") as HTMLInputElement).value.trim() || "Partner";
      fd.append("partner", partner);
      const r = await api.importForm(fd);
      toast(`${r.imported} Screens „${partner}" importiert${r.skipped ? ` · ${r.skipped} übersprungen` : ""}`, "ok");
      await refreshInventory(); await loadScreens(); doMatch();
    }
    $("mapModal").classList.add("hidden");
  } catch (err: any) {
    toast("Import fehlgeschlagen: " + (err?.message || err), "err");
  } finally {
    ($("mapImport") as HTMLButtonElement).disabled = false;
  }
}

async function refreshInventory() {
  const { partners, total } = await api.partners();
  $("invTotal").textContent = total ? `${total} Screens · ${partners.length} Partner` : "";
  $("invEmpty").style.display = partners.length ? "none" : "";
  const list = $("partnerList"); list.innerHTML = "";
  partners.forEach((p) => {
    const hidden = state.hiddenPartners.has(p.partner);
    const row = document.createElement("div");
    row.className = "partner-row" + (hidden ? " hidden-p" : "");
    row.innerHTML = `<span class="pdot"></span><span class="pname">${esc(p.partner)}</span><span class="pcount">${p.n}</span><button class="px" title="entfernen">✕</button>`;
    row.onclick = (e) => {
      if ((e.target as HTMLElement).classList.contains("px")) return;
      hidden ? state.hiddenPartners.delete(p.partner) : state.hiddenPartners.add(p.partner);
      saveState(); refreshInventory(); loadScreens(); doMatch();
    };
    (row.querySelector(".px") as HTMLButtonElement).onclick = async (e) => {
      e.stopPropagation();
      if (!confirm(`Partner „${p.partner}" und alle Screens löschen?`)) return;
      await api.deletePartner(p.partner);
      state.hiddenPartners.delete(p.partner);
      await refreshInventory(); await loadScreens(); doMatch();
    };
    list.appendChild(row);
  });
}

// ------------------------------------------------------------------ export --
function matchBody() {
  return {
    anchors: Array.from(state.anchors.entries()).map(([id, a]) => ({ id, radius: a.radius })),
    global_radius: state.globalRadius, hidden_partners: Array.from(state.hiddenPartners),
  };
}
async function exportRoundtrip() {
  const { partners } = await api.partners();
  for (const p of partners) {
    if (state.hiddenPartners.has(p.partner)) continue;
    await downloadCsv(`/api/export?layout=roundtrip&partner=${encodeURIComponent(p.partner)}`, matchBody(), `dooh-${p.partner}.csv`);
  }
}

// -------------------------------------------------------------------- util --
function esc(s: unknown): string {
  return String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]!));
}

// ------------------------------------------------------------------- wiring -
function wire() {
  ($("globalRadius") as HTMLInputElement).value = String(state.globalRadius);
  $("radiusVal").textContent = String(state.globalRadius);
  ($("globalRadius") as HTMLInputElement).addEventListener("input", (e) => {
    state.globalRadius = parseInt((e.target as HTMLInputElement).value, 10);
    $("radiusVal").textContent = String(state.globalRadius);
    drawCircles(); doMatch(); saveState();
  });
  ($("brandInput") as HTMLInputElement).addEventListener("input", onBrandInput);
  $("searchPois").addEventListener("click", searchPois);
  $("areaView").addEventListener("click", setAreaFromView);
  $("areaDraw").addEventListener("click", enableDraw);
  $("areaClear").addEventListener("click", () => { state.area = null; $("areaInfo").textContent = ""; });
  $("addTagFilter").addEventListener("click", () => addTagFilterRow());
  $("selectAllPois").addEventListener("click", () => {
    state.pois.forEach((f) => { if (!state.anchors.has(f.properties.id)) state.anchors.set(f.properties.id, { radius: null, feature: f }); });
    renderPois(); drawCircles(); doMatch(); saveState(); refreshAnchorButtons();
  });
  $("clearAnchors").addEventListener("click", () => {
    state.anchors.clear(); renderPois(); drawCircles(); doMatch(); saveState(); refreshAnchorButtons();
  });
  $("uploadScreens").addEventListener("click", () => pickFile("screens"));
  $("uploadPois").addEventListener("click", () => pickFile("pois"));
  $("mapCancel").addEventListener("click", () => $("mapModal").classList.add("hidden"));
  $("mapImport").addEventListener("click", doImport);
  $("exportCsv").addEventListener("click", () => downloadCsv("/api/export", matchBody(), "dooh-screens.csv"));
  $("exportRound").addEventListener("click", exportRoundtrip);
}

// -------------------------------------------------------------------- init --
async function init() {
  loadState();
  wire();
  try {
    const [cats, health] = await Promise.all([api.categories(), api.health()]);
    renderCatTree(cats.categories);
    if (health.last_import) $("freshness").textContent = `OSM-Daten: ${health.poi_count} POIs · Import ${String(health.last_import.imported_at).slice(0, 10)}`;
    else $("freshness").textContent = `${health.poi_count ?? 0} POIs geladen`;
  } catch {
    toast("API nicht erreichbar – läuft das Backend?", "err");
  }
  await refreshInventory();
  await loadScreens();
  drawCircles();
  if (state.anchors.size) doMatch();
}

init();
