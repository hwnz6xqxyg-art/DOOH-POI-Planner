// Typed client for the DOOH POI Planner API (SPEC §5, §7, §8, §9).

export interface Brand { brand: string; brand_wikidata: string | null; n: number; }
export interface CatSub { key: string; label: string; count: number; }
export interface Cat { key: string; label: string; count: number; subs: CatSub[]; }

export interface PoiProps {
  id: string; name: string | null; brand: string | null; brand_wikidata: string | null;
  category: string; subcategory: string | null; city: string | null; plz: string | null;
}
export interface PoiFeature {
  type: "Feature";
  geometry: { type: "Point"; coordinates: [number, number] };
  properties: PoiProps;
}
export interface SearchResult { features: PoiFeature[]; total: number; returned: number; capped: boolean; }

export interface MatchScreen {
  partner: string; screen_id: string; name: string | null; lat: number; lng: number;
  city: string | null; plz: string | null; address: string | null; format: string | null;
  matched_poi_ids: string[]; nearest_poi_id: string; nearest_distance_m: number; radius_used_m: number;
}
export interface MatchStats {
  screens_total: number; anchors_total: number; anchors_covered: number; coverage_pct: number;
  by_category: { category: string; total: number; covered: number }[];
}
export interface MatchResult { screens: MatchScreen[]; stats: MatchStats; error?: string; }

export interface ScreenPoint {
  partner: string; screen_id: string; name: string | null; format: string | null;
  city: string | null; plz: string | null; lat: number; lng: number;
}

async function jget<T>(u: string): Promise<T> {
  const r = await fetch(u);
  return r.json();
}
async function jpost<T>(u: string, body: unknown): Promise<T> {
  const r = await fetch(u, { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(body) });
  return r.json();
}

export const api = {
  health: () => jget<any>("/api/health"),
  brands: (q: string) => jget<{ brands: Brand[] }>(`/api/brands?q=${encodeURIComponent(q)}`),
  categories: () => jget<{ categories: Cat[] }>("/api/categories"),
  search: (body: unknown) => jpost<SearchResult>("/api/pois/search", body),
  match: (body: unknown) => jpost<MatchResult>("/api/match", body),
  partners: () => jget<{ partners: { partner: string; n: number }[]; total: number }>("/api/inventory/partners"),
  screens: () => jget<{ screens: ScreenPoint[] }>("/api/inventory/screens"),
  deletePartner: (p: string) => fetch(`/api/inventory/partner/${encodeURIComponent(p)}`, { method: "DELETE" }),
  previewForm: (fd: FormData) => fetch("/api/inventory/preview", { method: "POST", body: fd }).then((r) => r.json()),
  importForm: (fd: FormData) => fetch("/api/inventory/import", { method: "POST", body: fd }).then((r) => r.json()),
  importPoisForm: (fd: FormData) => fetch("/api/pois/custom/import", { method: "POST", body: fd }).then((r) => r.json()),
};

export async function downloadCsv(url: string, body: unknown, fallback: string) {
  const r = await fetch(url, { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(body) });
  const blob = await r.blob();
  const cd = r.headers.get("Content-Disposition") || "";
  const m = cd.match(/filename="(.+?)"/);
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = m ? m[1] : fallback;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(a.href), 1000);
}
