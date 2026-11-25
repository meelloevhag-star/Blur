/**
 * Marco técnico del visor (lenguaje Terrain Plume / wireframe técnico): reglas de latitud y longitud
 * que siguen al mapa, escuadras en las esquinas y una lectura mono bajo el cursor (coordenadas,
 * celda, altura, zoom y celdas en vista).
 */
import type { PropsZona } from "./tipos";

declare const L: typeof import("leaflet");

const fmt = (v: number, pos: string, neg: string) => `${Math.abs(v).toFixed(2)}°${v < 0 ? neg : pos}`;

function paso(rango: number) {
  for (const p of [0.05, 0.1, 0.25, 0.5, 1, 2, 5]) if (rango / p <= 8) return p;
  return 10;
}

export interface Hud { celda(p: PropsZona | null): void }

export function crearHud(mapa: L.Map, props: PropsZona[]): Hud {
  const raiz = document.createElement("div");
  raiz.className = "hud";
  raiz.setAttribute("aria-hidden", "true");
  raiz.innerHTML = `<div class="hud-regla hud-arriba"></div><div class="hud-regla hud-izq"></div>
    <span class="hud-esq e1"></span><span class="hud-esq e2"></span><span class="hud-esq e3"></span><span class="hud-esq e4"></span>`;
  const lectura = document.createElement("div");
  lectura.className = "hud-lectura";
  lectura.setAttribute("role", "status");
  lectura.setAttribute("aria-live", "off");
  mapa.getContainer().parentElement!.append(raiz, lectura);
  const arriba = raiz.querySelector<HTMLElement>(".hud-arriba")!, izq = raiz.querySelector<HTMLElement>(".hud-izq")!;
  let cursor: L.LatLng | null = null, enCelda: PropsZona | null = null;

  function reglas() {
    const b = mapa.getBounds(), z = mapa.getSize();
    const pl = paso(b.getEast() - b.getWest()), pa = paso(b.getNorth() - b.getSouth());
    let h = "";
    for (let x = Math.ceil(b.getWest() / pl) * pl; x <= b.getEast(); x += pl) {
      const px = mapa.latLngToContainerPoint([b.getCenter().lat, x]).x;
      if (px > 40 && px < z.x - 40) h += `<span style="left:${px.toFixed(0)}px">${fmt(x, "E", "O")}</span>`;
    }
    arriba.innerHTML = h;
    h = "";
    for (let y = Math.ceil(b.getSouth() / pa) * pa; y <= b.getNorth(); y += pa) {
      const py = mapa.latLngToContainerPoint([y, b.getCenter().lng]).y;
      if (py > 40 && py < z.y - 40) h += `<span style="top:${py.toFixed(0)}px">${fmt(y, "N", "S")}</span>`;
    }
    izq.innerHTML = h;
  }

  function leer() {
    const b = mapa.getBounds();
    const visibles = props.reduce((n, p) => n + (b.contains([p.lat, p.lon]) ? 1 : 0), 0);
    const c = cursor ?? mapa.getCenter();
    const partes = [
      `<b>${fmt(c.lat, "N", "S")} ${fmt(c.lng, "E", "O")}</b>`,
      enCelda ? `<span>${enCelda.id}</span><span>${Math.round(enCelda.elevacion_media_m ?? 0)} m</span>` : "",
      `<span>Z ${mapa.getZoom().toFixed(1)}</span>`,
      `<span>${visibles} celdas en vista</span>`,
    ];
    lectura.innerHTML = partes.filter(Boolean).join("<i></i>");
  }

  mapa.on("move zoom resize", () => { reglas(); leer(); });
  mapa.on("mousemove", (e: L.LeafletMouseEvent) => { cursor = e.latlng; leer(); });
  mapa.on("mouseout", () => { cursor = null; enCelda = null; leer(); });
  L.control.scale({ position: "bottomright", imperial: false, maxWidth: 120 }).addTo(mapa);
  reglas(); leer();
  return { celda(p) { enCelda = p; leer(); } };
}
