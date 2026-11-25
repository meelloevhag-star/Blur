import { CAPAS, clase, color, type Capa } from "./capas";
import type { Coleccion, PropsZona } from "./tipos";

declare const L: typeof import("leaflet");

const tok = (n: string) => getComputedStyle(document.documentElement).getPropertyValue(n).trim();
const oscuro = () => document.documentElement.dataset.theme === "dark";

export interface Mapa {
  ponerCapa(c: Capa): void;
  filtrarClase(i: number | null): void;
  seleccionar(id: string | null, volar?: boolean): void;
  alSeleccionar(fn: (p: PropsZona) => void): void;
  repintarTema(): void;
  mapa: L.Map;
}

/**
 * Malla hexagonal de 10 km: una sola capa a todo zoom. Cada celda es una baldosa separada por un
 * borde del color del mar; la elegida se enciende y las demás se atenúan un poco.
 */
export async function crearMapa(el: HTMLElement, col: Coleccion): Promise<Mapa> {
  const lienzo = L.canvas({ padding: 0.4, tolerance: 2 });
  const props = col.features.map((f) => f.properties);
  const limites = L.latLngBounds(props.map((p) => [p.lat, p.lon] as [number, number]));
  const mapa = L.map(el, {
    zoomControl: false, attributionControl: true, minZoom: 5, maxZoom: 12, renderer: lienzo,
    zoomSnap: 0.25, wheelPxPerZoomLevel: 90, maxBounds: limites.pad(0.6), maxBoundsViscosity: 0.8,
  });
  L.control.zoom({ position: "bottomright" }).addTo(mapa);
  mapa.createPane("tierra").style.zIndex = "200";
  mapa.createPane("relieve").style.zIndex = "450";
  mapa.getPane("relieve")!.style.pointerEvents = "none";
  mapa.createPane("seleccion").style.zIndex = "460";
  mapa.getPane("seleccion")!.style.pointerEvents = "none";
  mapa.attributionControl.setPrefix(false).addAttribution("Copernicus DEM · Natural Earth · ERA5 · WorldPop · Blur");

  // ---------- fondo: tierra (departamentos) + relieve sombreado ----------
  let tierra: L.GeoJSON | null = null;
  try {
    const deptos = await (await fetch("departamentos_per.geojson")).json();
    tierra = L.geoJSON(deptos, { interactive: false, pane: "tierra", renderer: L.svg({ padding: 0.5, pane: "tierra" }),
      style: () => ({ color: tok("--linea"), weight: 0.7, fillColor: tok("--tierra"), fillOpacity: 1 }) } as any).addTo(mapa);
  } catch { /* el mapa sigue sin fondo */ }
  try {
    const meta = await (await fetch("fondo/relieve.json")).json();
    L.imageOverlay("fondo/relieve.png", meta.limites, { interactive: false, className: "relieve", pane: "relieve" }).addTo(mapa);
  } catch { /* sin relieve */ }

  let capa: Capa = CAPAS[0];
  let filtro: number | null = null;
  let sel: string | null = null;
  let encima: string | null = null;
  let oyente: (p: PropsZona) => void = () => {};
  const visible = (v: number) => filtro === null || clase(capa, v) === filtro;

  function estilo(p: PropsZona) {
    const v = capa.valor(p);
    const on = visible(v);
    const base = oscuro() ? 0.78 : 0.86;
    const atenuar = sel && p.id !== sel ? 0.72 : 1;
    return {
      color: p.id === encima ? tok("--tinta") : tok("--mar"),
      weight: p.id === encima ? 1.6 : 1.1,
      fillColor: color(capa, v),
      fillOpacity: on ? base * atenuar : 0.07,
      opacity: on ? 1 : 0.35,
    };
  }

  const hexes = L.geoJSON(col as any, {
    renderer: lienzo,
    style: (f: any) => estilo(f.properties),
    onEachFeature: (f: any, l: any) => {
      l.on("click", () => oyente(f.properties));
      l.on("mouseover", () => { encima = f.properties.id; l.setStyle(estilo(f.properties)); l.bringToFront(); });
      l.on("mouseout", () => { if (encima === f.properties.id) encima = null; l.setStyle(estilo(f.properties)); });
      l.bindTooltip(() => `<strong>${f.properties.distrito}</strong><span>${capa.formato(capa.valor(f.properties))}</span>`,
        { sticky: true, direction: "top", offset: [0, -10], className: "tip" });
    },
  } as any).addTo(mapa);
  const capas = new Map<string, L.Path>();
  hexes.eachLayer((l: any) => capas.set(l.feature.properties.id, l));

  // contorno luminoso de la celda elegida (dos trazos: resplandor + línea)
  const resalte = L.layerGroup().addTo(mapa);
  function pintarSeleccion() {
    resalte.clearLayers();
    const f = sel ? col.features.find((x) => x.properties.id === sel) : null;
    if (!f) return;
    const anillo = (f.geometry.coordinates[0] as number[][]).map(([lon, lat]) => [lat, lon] as [number, number]);
    const acento = tok("--acento");
    L.polygon(anillo, { pane: "seleccion", interactive: false, color: acento, weight: 9, opacity: 0.25, fill: false, renderer: L.svg({ pane: "seleccion" }) } as any).addTo(resalte);
    L.polygon(anillo, { pane: "seleccion", interactive: false, color: oscuro() ? "#ffffff" : tok("--tinta"), weight: 2.2, fill: false, renderer: L.svg({ pane: "seleccion" }) } as any).addTo(resalte);
  }

  // ---------- etiquetas de ciudades: más a mayor zoom, sin choques ----------
  const etiquetas = L.layerGroup().addTo(mapa);
  const urbanas = props.filter((p) => p.clase_urbana === "urbano" || p.clase_urbana === "periurbano")
    .sort((a, b) => b.poblacion - a.poblacion);
  function ponerEtiquetas() {
    etiquetas.clearLayers();
    const z = mapa.getZoom();
    const max = z < 6 ? 6 : z < 7 ? 10 : z < 8.5 ? 16 : 30;
    const puestas: L.Point[] = [];
    const vistos = new Set<string>();
    for (const p of urbanas) {
      if (puestas.length >= max) break;
      const nombre = z >= 8.5 ? p.distrito : p.provincia;
      if (vistos.has(nombre)) continue;
      const pt = mapa.latLngToLayerPoint([p.lat, p.lon]);
      if (puestas.some((q) => Math.abs(q.x - pt.x) < 90 && Math.abs(q.y - pt.y) < 22)) continue;
      vistos.add(nombre);
      puestas.push(pt);
      L.marker([p.lat, p.lon], { interactive: false, keyboard: false,
        icon: L.divIcon({ className: "ciudad", html: `<span>${nombre}</span>`, iconSize: [0, 0] }) }).addTo(etiquetas);
    }
  }
  mapa.on("zoomend", ponerEtiquetas);

  mapa.fitBounds(limites, { padding: [30, 30] });
  ponerEtiquetas();

  function repintar() {
    hexes.setStyle((f: any) => estilo(f.properties));
    pintarSeleccion();
  }
  return {
    mapa,
    ponerCapa(c) { capa = c; filtro = null; repintar(); },
    filtrarClase(i) { filtro = i; repintar(); },
    seleccionar(id, volar = true) {
      sel = id;
      repintar();
      const p = id ? props.find((x) => x.id === id) : null;
      if (p && volar) {
        const z = Math.max(mapa.getZoom(), 9.5);
        const mov = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
        const movil = document.body.classList.contains("movil");
        const despl = movil ? L.point(0, window.innerHeight * 0.2) : L.point(Math.min(240, window.innerWidth * 0.18), 0);
        const destino = mapa.unproject(mapa.project([p.lat, p.lon], z).add(despl), z);
        mov ? mapa.setView(destino, z) : mapa.flyTo(destino, z, { duration: 0.9 });
      }
      if (p) (capas.get(p.id) as any)?.bringToFront();
    },
    alSeleccionar(fn) { oyente = fn; },
    repintarTema() { tierra?.setStyle({ color: tok("--linea"), fillColor: tok("--tierra") }); repintar(); },
  };
}
