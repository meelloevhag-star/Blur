import type { Coleccion, Zona } from "./tipos";

/** Dos modos: con API (Go) o estático (GeoJSON publicado junto a la página). */
export interface Fuente {
  modo: "api" | "estatico";
  zonas(): Promise<Coleccion>;
  zona(id: string): Promise<Zona>;
  enviarAportes?(csv: string, clave: string): Promise<any>;
}

export function crearFuente(): Fuente {
  const base = new URLSearchParams(location.search).get("api") ?? (window as any).ATLAS_API ?? "";
  if (base) {
    const url = base.replace(/\/$/, "");
    return {
      modo: "api",
      zonas: async () => (await fetch(`${url}/api/zonas`)).json(),
      zona: async (id) => (await fetch(`${url}/api/zonas/${encodeURIComponent(id)}`)).json(),
      enviarAportes: async (csv, clave) =>
        (await fetch(`${url}/api/aportes`, { method: "POST", headers: { "Content-Type": "text/csv", "X-API-Key": clave }, body: csv })).json(),
    };
  }
  // estático: GeoJSON ligero para el mapa + un archivo de detalle por departamento, pedido al abrir una zona
  let cache: Promise<Coleccion> | null = null;
  const detalles = new Map<string, Promise<Record<string, Zona>>>();
  const todo = () => (cache ??= fetch("zonas_ligero_per.geojson").then((r) => {
    if (!r.ok) throw new Error(`No se pudo cargar zonas_ligero_per.geojson (${r.status})`);
    return r.json();
  }));
  return {
    modo: "estatico",
    zonas: todo,
    zona: async (id) => {
      const lig = (await todo()).features.find((f: Zona) => f.properties.id === id) as Zona;
      const slug = lig.properties.detalle!;
      if (!detalles.has(slug)) detalles.set(slug, fetch(`detalle/${slug}.json`).then((r) => r.json()));
      return (await detalles.get(slug)!)[id];
    },
  };
}
