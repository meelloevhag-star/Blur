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
  alPasar(fn: (p: PropsZona | null) => void): void;
  encuadrar(b: L.LatLngBoundsExpression, volar?: boolean): void;
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
  mapa.createPane("curvas").style.zIndex = "430";
  mapa.getPane("curvas")!.style.pointerEvents = "none";
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
  let alPasarFn: (p: PropsZona | null) => void = () => {};
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
      l.on("mouseover", () => { encima = f.properties.id; l.setStyle(estilo(f.properties)); l.bringToFront(); alPasarFn(f.properties); });
      l.on("mouseout", () => { if (encima === f.properties.id) encima = null; l.setStyle(estilo(f.properties)); alPasarFn(null); });
      l.bindTooltip(() => `<strong>${f.properties.distrito}</strong><span>${capa.formato(capa.valor(f.properties))}</span>`,
        { sticky: true, direction: "top", offset: [0, -10], className: "tip" });
    },
  } as any).addTo(mapa);
  const capas = new Map<string, L.Path>();
  hexes.eachLayer((l: any) => capas.set(l.feature.properties.id, l));

  // ---------- curvas de nivel (DEM de Blur): maestras desde zoom 6, todas desde zoom 8,5 ----------
  const lienzoCurvas = L.canvas({ pane: "curvas", padding: 0.3 } as any);
  const maestras = L.layerGroup(), menores = L.layerGroup();
  const trazosCurva: [L.Polyline, number][] = [];
  try {
    const c = await (await fetch("fondo/curvas.json")).json();
    for (const [h, plano] of c.lineas as [number, number[]][]) {
      const pts: [number, number][] = [];
      for (let i = 0; i < plano.length; i += 2) pts.push([plano[i + 1], plano[i]]);
      const l = L.polyline(pts, { renderer: lienzoCurvas, interactive: false, pane: "curvas" } as any);
      trazosCurva.push([l, h]);
      ((h % c.maestra === 0 || c.franja_nubes.includes(h)) ? maestras : menores).addLayer(l);
    }
  } catch { /* sin curvas */ }
  function estiloCurvas() {
    const nubes = tok("--curva-nubes"), linea = tok("--curva");
    for (const [l, h] of trazosCurva) {
      const n = h === 300 || h === 1000, m = h % 500 === 0;
      l.setStyle({ color: n ? nubes : linea, weight: n ? 1.1 : m ? 0.9 : 0.5, opacity: n ? 0.75 : m ? 0.5 : 0.3 });
    }
  }
  estiloCurvas();
  function nivelCurvas() {
    const z = mapa.getZoom();
    z >= 6 ? maestras.addTo(mapa) : mapa.removeLayer(maestras);
    z >= 8.5 ? menores.addTo(mapa) : mapa.removeLayer(menores);
  }
  mapa.on("zoomend", nivelCurvas);

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

  // ---------- ciudades como puntos de cobertura (Locations & Coverage): núcleo + anillo que late ----------
  const etiquetas = L.layerGroup().addTo(mapa);
  const urbanas = props.filter((p) => p.clase_urbana === "urbano" || p.clase_urbana === "periurbano")
    .sort((a, b) => b.poblacion - a.poblacion);
  const pobMax = urbanas[0]?.poblacion || 1;
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
      if (puestas.some((q) => Math.abs(q.x - pt.x) < 96 && Math.abs(q.y - pt.y) < 24)) continue;
      vistos.add(nombre);
      puestas.push(pt);
      const i = Math.sqrt(p.poblacion / pobMax);
      L.marker([p.lat, p.lon], { interactive: false, keyboard: false,
        icon: L.divIcon({ className: "cobertura", iconSize: [0, 0],
          html: `<span class="cob-punto" style="--i:${(0.35 + 0.65 * i).toFixed(2)};--d:${(puestas.length * 0.37 % 2.4).toFixed(2)}s"></span><span class="cob-nombre">${nombre}</span>` }) }).addTo(etiquetas);
    }
  }
  mapa.on("zoomend", ponerEtiquetas);

  mapa.fitBounds(limites, { padding: [30, 30] });
  ponerEtiquetas();
  nivelCurvas();

  // ---------- pulso de escaneo al elegir (3d-survey-scan en 2D): anillo + vecinos que se encienden ----------
  const quieto = () => matchMedia("(prefers-reduced-motion: reduce)").matches;
  let pulsoRaf = 0;
  function pulso(p: PropsZona) {
    if (quieto()) return;
    cancelAnimationFrame(pulsoRaf);
    const anillo = L.circle([p.lat, p.lon], { radius: 10, pane: "seleccion", interactive: false, fill: false,
      color: tok("--acento"), weight: 1.5, renderer: L.svg({ pane: "seleccion" }) } as any).addTo(resalte);
    const t0 = performance.now(), dur = 1300, R = 26000;
    const paso = (t: number) => {
      const k = Math.min(1, (t - t0) / dur), e = 1 - Math.pow(1 - k, 3);
      anillo.setRadius(10 + R * e);
      anillo.setStyle({ opacity: 0.9 * (1 - k) });
      if (k < 1) pulsoRaf = requestAnimationFrame(paso); else resalte.removeLayer(anillo);
    };
    pulsoRaf = requestAnimationFrame(paso);
    const kx = 111.32 * Math.cos((p.lat * Math.PI) / 180);
    props.map((q) => [q, Math.hypot((q.lon - p.lon) * kx, (q.lat - p.lat) * 111.32)] as [PropsZona, number])
      .filter(([q, d]) => d < 28 && q.id !== p.id)
      .forEach(([q, d]) => {
        const l = capas.get(q.id) as any;
        if (!l) return;
        setTimeout(() => {
          l.setStyle({ color: tok("--acento"), weight: 1.8 });
          setTimeout(() => l.setStyle(estilo(q)), 420);
        }, (d / 26) * dur * 0.85);
      });
  }

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
      if (p) { (capas.get(p.id) as any)?.bringToFront(); setTimeout(() => pulso(p), volar ? 900 : 0); }
    },
    alSeleccionar(fn) { oyente = fn; },
    alPasar(fn) { alPasarFn = fn; },
    encuadrar(b, volar = true) {
      const movil = document.body.classList.contains("movil");
      const op = { paddingTopLeft: movil ? [20, 120] : [460, 60], paddingBottomRight: movil ? [20, window.innerHeight * (document.body.classList.contains("en-recorrido") ? 0.6 : 0.45)] : [40, 40] } as any;
      volar && !quieto() ? mapa.flyToBounds(b, { ...op, duration: 1.1 }) : mapa.fitBounds(b, op);
    },
    repintarTema() { tierra?.setStyle({ color: tok("--linea"), fillColor: tok("--tierra") }); estiloCurvas(); repintar(); },
  };
}
