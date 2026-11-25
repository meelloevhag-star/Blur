import type { Coleccion, Terreno, Zona } from "./tipos";

/** Datos estáticos publicados junto a la página (o servidos por la API en Go con ?api=). */
export interface Fuente {
  modo: "api" | "estatico";
  zonas(): Promise<Coleccion>;
  zona(id: string, slug: string): Promise<Zona>;
  terreno(id: string, slug: string): Promise<Terreno | null>;
  enviarAportes?(csv: string, clave: string): Promise<any>;
}

const json = async (u: string) => {
  const r = await fetch(u);
  if (!r.ok) throw new Error(`No se pudo cargar ${u} (${r.status})`);
  return r.json();
};

export function crearFuente(): Fuente {
  const base = (new URLSearchParams(location.search).get("api") ?? (window as any).ATLAS_API ?? "").replace(/\/$/, "");
  const cacheDet = new Map<string, Promise<Record<string, Zona>>>();
  const cacheTer = new Map<string, Promise<Record<string, any>>>();
  const detalle = (slug: string) => {
    if (!cacheDet.has(slug)) cacheDet.set(slug, json(`detalle/${slug}.json`));
    return cacheDet.get(slug)!;
  };
  const terreno = (slug: string) => {
    if (!cacheTer.has(slug)) cacheTer.set(slug, json(`terreno/${slug}.json`).catch(() => ({})));
    return cacheTer.get(slug)!;
  };
  let todo: Promise<Coleccion> | null = null;
  return {
    modo: base ? "api" : "estatico",
    zonas: () => (todo ??= json("zonas_ligero_per.geojson")),
    zona: async (id, slug) => base ? json(`${base}/api/zonas/${encodeURIComponent(id)}`) : (await detalle(slug))[id],
    terreno: async (id, slug) => {
      const t = (await terreno(slug))[id];
      if (!t) return null;
      if (!t.h && t.h64) {                       // alturas Int16 little-endian en base64
        const b = atob(t.h64), dv = new DataView(new ArrayBuffer(b.length));
        for (let i = 0; i < b.length; i++) dv.setUint8(i, b.charCodeAt(i));
        t.h = Array.from({ length: b.length / 2 }, (_, i) => dv.getInt16(i * 2, true));
      }
      return t as Terreno;
    },
    enviarAportes: base ? async (csv, clave) => (await fetch(`${base}/api/aportes`, {
      method: "POST", headers: { "Content-Type": "text/csv", "X-API-Key": clave }, body: csv })).json() : undefined,
  };
}
