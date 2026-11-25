/**
 * Modo "Recorrido" (ECLIPSE + scroll-progress-timeline): la costa de norte a sur en 7 capítulos.
 * Al llegar a cada uno con el scroll, el mapa vuela a su tramo y cambia de capa. Las cifras se
 * calculan de los datos del Atlas, no se escriben a mano.
 */
import { AGENTES, REGIMENES } from "./capas";
import type { PropsZona } from "./tipos";

interface Capitulo { n: string; titulo: string; lat: [number, number]; capa: string; nota: string }

const CAPITULOS: Capitulo[] = [
  { n: "01", titulo: "Tumbes", lat: [-4.3, -3.0], capa: "regimen", nota: "El extremo norte: mar cálido, manglares y el clima más húmedo del litoral." },
  { n: "02", titulo: "Paita y Colán", lat: [-5.6, -4.3], capa: "cloruros", nota: "Puerto y playas expuestos al viento del sur: la sal llega lejos tierra adentro." },
  { n: "03", titulo: "Chiclayo y Trujillo", lat: [-8.6, -5.6], capa: "poblacion", nota: "Grandes ciudades sobre llanuras desérticas: mucha obra, mucha gente." },
  { n: "04", titulo: "Lima, Callao y Lachay", lat: [-12.6, -8.6], capa: "niebla", nota: "La garúa de invierno y las lomas que la atrapan entre 300 y 1 000 m." },
  { n: "05", titulo: "Pisco e Ica", lat: [-15.2, -12.6], capa: "vida", nota: "Desierto y bahías abiertas: el concreto común dura poco cerca del mar." },
  { n: "06", titulo: "Atiquipa y Mollendo", lat: [-17.2, -15.2], capa: "relieve", nota: "Cerros que suben rápido desde el mar y lomas de neblina." },
  { n: "07", titulo: "Ilo y Tacna", lat: [-18.6, -17.2], capa: "prioridad", nota: "El extremo sur: árido, ventoso y con puertos expuestos." },
];

const n0 = (x: number) => Math.round(x).toLocaleString("es-PE");
const moda = <T,>(xs: T[]) => {
  const c = new Map<T, number>();
  xs.forEach((x) => c.set(x, (c.get(x) ?? 0) + 1));
  return [...c.entries()].sort((a, b) => b[1] - a[1])[0]?.[0];
};

export interface OpcionesRecorrido {
  encuadrar(b: [[number, number], [number, number]]): void;
  ponerCapa(id: string): void;
  abrir(id: string): void;
  alCerrar(): void;
}

export function crearRecorrido(el: HTMLElement, props: PropsZona[], op: OpcionesRecorrido) {
  const datos = CAPITULOS.map((c) => {
    const zs = props.filter((p) => p.lat <= c.lat[1] && p.lat > c.lat[0]);
    const lats = zs.map((p) => p.lat), lons = zs.map((p) => p.lon);
    const reg = moda(zs.map((p) => p.regimen)) ?? "";
    const ag = moda(zs.map((p) => p.ideal_agente)) ?? "";
    const comun = zs.filter((p) => !p.comun_cumple_anios).length;
    const top = [...zs].sort((a, b) => b.prioridad - a.prioridad)[0];
    return { c, zs, reg, ag, comun, top,
      b: [[Math.min(...lats), Math.min(...lons)], [Math.max(...lats), Math.max(...lons)]] as [[number, number], [number, number]] };
  });
  el.innerHTML = `
    <header class="rec-cab"><p class="mono">Recorrido · Tumbes → Tacna</p>
      <button type="button" class="btn-icono" data-cerrar-rec aria-label="Cerrar recorrido">✕</button></header>
    <div class="rec-riel" aria-hidden="true"><span class="rec-progreso"></span></div>
    <div class="rec-scroll">
      <section class="rec-intro"><h2>2 500 km de costa,<br><em>siete paisajes para el concreto</em></h2>
        <p>Baja con el scroll. El mapa te acompaña tramo por tramo.</p></section>
      ${datos.map((d, i) => `<section class="rec-cap" data-i="${i}" aria-labelledby="rec-t${i}">
        <p class="mono rec-n">${d.c.n} / 07</p>
        <h3 id="rec-t${i}">${d.c.titulo}</h3>
        <p class="rec-nota">${d.c.nota}</p>
        <dl class="rec-cifras">
          <div><dt>celdas</dt><dd>${d.zs.length}</dd></div>
          <div><dt>habitantes</dt><dd>${n0(d.zs.reduce((s, p) => s + p.poblacion, 0))}</dd></div>
          <div><dt>exposición más común</dt><dd>${REGIMENES[d.reg]?.nombre ?? "—"}</dd></div>
          <div><dt>agente recomendado</dt><dd>${AGENTES[d.ag]?.corto ?? "—"}</dd></div>
          <div class="ancho"><dt>concreto común que no llega a 25 años</dt>
            <dd><span class="rec-barra"><span style="--p:${d.zs.length ? Math.round(d.comun / d.zs.length * 100) : 0}%"></span></span>
            ${d.zs.length ? Math.round(d.comun / d.zs.length * 100) : 0} %</dd></div>
        </dl>
        ${d.top ? `<button type="button" class="btn-sec" data-abrir="${d.top.id}">Abrir ${d.top.distrito}</button>` : ""}
      </section>`).join("")}
      <section class="rec-fin"><p>Fin del recorrido. Toca cualquier hexágono para ver su receta.</p>
        <button type="button" class="btn-pri" data-cerrar-rec>Explorar libremente</button></section>
    </div>`;
  const scroll = el.querySelector<HTMLElement>(".rec-scroll")!, barra = el.querySelector<HTMLElement>(".rec-progreso")!;
  let actual = -1;
  const io = new IntersectionObserver((ents) => {
    for (const e of ents) {
      if (!e.isIntersecting) continue;
      const i = Number((e.target as HTMLElement).dataset.i);
      e.target.classList.add("visto");
      if (i === actual) continue;
      actual = i;
      el.querySelectorAll(".rec-cap").forEach((s) => s.classList.toggle("activo", Number((s as HTMLElement).dataset.i) === i));
      op.ponerCapa(datos[i].c.capa);
      op.encuadrar(datos[i].b);
    }
  }, { root: scroll, rootMargin: "-40% 0px -40% 0px" });
  el.querySelectorAll(".rec-cap").forEach((s) => io.observe(s));
  scroll.addEventListener("scroll", () => {
    const k = scroll.scrollTop / Math.max(1, scroll.scrollHeight - scroll.clientHeight);
    barra.style.setProperty("--p", `${(k * 100).toFixed(1)}%`);
  }, { passive: true });
  el.addEventListener("click", (e) => {
    const t = e.target as HTMLElement;
    const ab = t.closest<HTMLElement>("[data-abrir]");
    if (ab) { cerrar(); op.abrir(ab.dataset.abrir!); return; }
    if (t.closest("[data-cerrar-rec]")) cerrar();
  });
  el.addEventListener("keydown", (e) => { if (e.key === "Escape") cerrar(); });
  function cerrar() { el.hidden = true; document.body.classList.remove("en-recorrido"); op.alCerrar(); }
  return {
    abrir() {
      el.hidden = false; actual = -1;
      document.body.classList.add("en-recorrido");
      scroll.scrollTop = 0;
      el.querySelector<HTMLElement>("[data-cerrar-rec]")!.focus();
      op.encuadrar([[-18.6, -81.5], [-3.2, -69.8]]);
    },
  };
}
