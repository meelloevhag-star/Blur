import { CAPAS, clase, color, resumirTramo, type Capa } from "./capas";
import type { Coleccion, PropsZona } from "./tipos";

declare const L: typeof import("leaflet");

const ZOOM_POLIGONOS = 9;
const tok = (n: string) => getComputedStyle(document.documentElement).getPropertyValue(n).trim();

export interface Mapa {
  ponerCapa(c: Capa): void;
  filtrarClase(i: number | null): void;
  seleccionar(id: string | null, volar?: boolean): void;
  alSeleccionar(fn: (p: PropsZona) => void): void;
  repintarTema(): void;
  mapa: L.Map;
}

export async function crearMapa(el: HTMLElement, col: Coleccion): Promise<Mapa> {
  const lienzo = L.canvas({ padding: 0.4, tolerance: 6 });
  const mapa = L.map(el, { zoomControl: false, attributionControl: true, minZoom: 4, maxZoom: 13, renderer: lienzo,
    zoomSnap: 0.25, wheelPxPerZoomLevel: 90 });
  L.control.zoom({ position: "bottomright" }).addTo(mapa);
  // orden de pintado: tierra (200) < zonas (overlayPane, 400) < relieve sombreado (450) < etiquetas
  mapa.createPane("tierra").style.zIndex = "200";
  mapa.createPane("relieve").style.zIndex = "450";   // sombreado encima de las zonas (multiplicar)
  mapa.getPane("relieve")!.style.pointerEvents = "none";
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

  // ---------- zonas: polígonos (zoom alto) y cinta costera (zoom bajo) ----------
  const props = col.features.map((f) => f.properties);
  const porTramo = new Map<number, PropsZona[]>();
  props.forEach((p) => { if (!porTramo.has(p.tramo)) porTramo.set(p.tramo, []); porTramo.get(p.tramo)!.push(p); });
  const tramos = [...porTramo.keys()].sort((a, b) => a - b);
  const costa = new Map<number, [number, number]>();
  tramos.forEach((t) => { const z = porTramo.get(t)!.reduce((a, b) => (b.franja < a.franja ? b : a)); costa.set(t, [z.lat, z.lon]); });

  let capa: Capa = CAPAS[0];
  let filtro: number | null = null;
  let sel: string | null = null;
  let oyente: (p: PropsZona) => void = () => {};
  const visible = (v: number) => filtro === null || clase(capa, v) === filtro;

  const poligonos = L.geoJSON(col as any, {
    renderer: lienzo,
    style: (f: any) => estiloPol(f.properties),
    onEachFeature: (f: any, l: any) => {
      l.on("click", () => oyente(f.properties));
      l.on("mouseover", () => { if (f.properties.id !== sel) l.setStyle({ weight: 1.6, color: tok("--tinta") }); });
      l.on("mouseout", () => { if (f.properties.id !== sel) l.setStyle(estiloPol(f.properties)); });
      l.bindTooltip(() => tip(f.properties), { sticky: true, direction: "top", offset: [0, -8], className: "tip" });
    },
  } as any);
  function estiloPol(p: PropsZona) {
    const v = capa.valor(p);
    const on = visible(v);
    return { color: p.id === sel ? tok("--tinta") : tok("--borde-zona"), weight: p.id === sel ? 2.4 : 0.35,
      fillColor: color(capa, v), fillOpacity: on ? 0.8 : 0.08, opacity: on ? 1 : 0.2 };
  }
  const tip = (p: PropsZona) =>
    `<strong>${p.distrito}</strong><span>${capa.nombre}: ${capa.formato(capa.valor(p))}</span>`;

  const cinta = L.layerGroup();
  const segmentos = new Map<number, L.Polyline>();
  tramos.forEach((t, i) => {
    const a = costa.get(tramos[Math.max(i - 1, 0)])!, b = costa.get(t)!, c = costa.get(tramos[Math.min(i + 1, tramos.length - 1)])!;
    const ab: [number, number] = [(a[0] + b[0]) / 2, (a[1] + b[1]) / 2], bc: [number, number] = [(b[0] + c[0]) / 2, (b[1] + c[1]) / 2];
    const seg = L.polyline([ab, b, bc], { renderer: lienzo, lineCap: "butt", lineJoin: "round" });
    seg.on("click", () => {
      const z = porTramo.get(t)!.reduce((m, x) => (x.franja < m.franja ? x : m));
      oyente(z);
    });
    seg.bindTooltip(() => {
      const zs = porTramo.get(t)!;
      const z0 = zs.reduce((m, x) => (x.franja < m.franja ? x : m));
      return `<strong>${z0.distrito}</strong><span>${capa.nombre}: ${capa.formato(resumirTramo(capa, zs))}</span>`;
    }, { sticky: true, direction: "top", offset: [0, -8], className: "tip" });
    segmentos.set(t, seg);
    cinta.addLayer(seg);
  });
  function pintarCinta() {
    const z = mapa.getZoom();
    const ancho = Math.max(5, Math.min(16, (z - 3.5) * 3.2));
    segmentos.forEach((seg, t) => {
      const v = resumirTramo(capa, porTramo.get(t)!);
      const zSel = sel ? props.find((p) => p.id === sel) : null;
      seg.setStyle({ color: color(capa, v), weight: zSel?.tramo === t ? ancho + 5 : ancho, opacity: visible(v) ? 1 : 0.15 });
    });
  }
  function nivel() {
    const alto = mapa.getZoom() >= ZOOM_POLIGONOS;
    if (alto && !mapa.hasLayer(poligonos)) { mapa.removeLayer(cinta); poligonos.addTo(mapa); }
    if (!alto && !mapa.hasLayer(cinta)) { mapa.removeLayer(poligonos); cinta.addTo(mapa); }
    if (!alto) pintarCinta();
  }
  mapa.on("zoomend", nivel);
  mapa.fitBounds(L.latLngBounds(props.map((p) => [p.lat, p.lon] as [number, number])), { padding: [30, 30] });
  nivel();

  // ---------- etiquetas de ciudades principales ----------
  const etiquetas = L.layerGroup().addTo(mapa);
  const urbanas = props.filter((p) => p.clase_urbana === "urbano").sort((a, b) => b.poblacion - a.poblacion);
  const vistos = new Set<string>();
  const puestos: [number, number][] = [];
  urbanas.forEach((p) => {
    const nombre = p.provincia;
    if (vistos.has(nombre) || vistos.size > 12) return;
    if (puestos.some(([a, b]) => Math.hypot(a - p.lat, b - p.lon) < 0.6)) return;   // sin etiquetas encimadas
    vistos.add(nombre);
    puestos.push([p.lat, p.lon]);
    L.marker([p.lat, p.lon], { interactive: false, icon: L.divIcon({ className: "ciudad", html: `<span>${nombre}</span>`, iconSize: [0, 0] }) }).addTo(etiquetas);
  });

  function repintar() {
    poligonos.setStyle((f: any) => estiloPol(f.properties));
    pintarCinta();
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
        const z = Math.max(mapa.getZoom(), 10);
        const mov = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
        const panel = document.body.classList.contains("movil") ? [0, -window.innerHeight * 0.18] : [-200, 0];
        const destino = mapa.unproject(mapa.project([p.lat, p.lon], z).add(L.point(-panel[0], -panel[1])), z);
        mov ? mapa.setView(destino, z) : mapa.flyTo(destino, z, { duration: 0.9 });
      }
    },
    alSeleccionar(fn) { oyente = fn; },
    repintarTema() { tierra?.setStyle({ color: tok("--linea"), fillColor: tok("--tierra") }); repintar(); },
  };
}
