import { cloruro } from "./fick";
import type { Durabilidad, Fick } from "./tipos";

/** Perfil medio (para dibujar) + verificación probabilista (para decidir cuándo empieza la corrosión). */
export interface Caso { f: Fick; d: Durabilidad }

/**
 * Visor "en el tiempo": corte del concreto, de la cara expuesta (izquierda) hacia adentro, con la
 * barra de acero a la profundidad del recubrimiento. El degradé es el cloruro medio que entra año a
 * año. El acero pasa a óxido en el año en que la probabilidad de despasivación llega a 10 % (t10,
 * criterio fib B34, β = 1,3), no cuando lo cruza el perfil medio. Dos cortes con la misma escala:
 * el concreto común de la zona y la receta elegida.
 */
export interface Visor { destruir(): void }

const PROF_MM = 90;               // profundidad dibujada
const W = 340, FILA = 66, X0 = 92, X1 = W - 10;

function colorCl(r: number): string {
  // 0 → gris concreto; 1 (umbral) → ámbar; > 1 → rojo óxido
  const a = Math.min(r, 1.6) / 1.6;
  const c0 = [200, 198, 190], c1 = [226, 170, 92], c2 = [168, 72, 40];
  const m = a < 0.62 ? a / 0.62 : (a - 0.62) / 0.38;
  const [p, q] = a < 0.62 ? [c0, c1] : [c1, c2];
  return `rgb(${p.map((v, i) => Math.round(v + (q[i] - v) * m)).join(",")})`;
}

export function crearVisor(el: HTMLElement, comunC: Caso, recetaC: Caso, nombreReceta: string, horizonte = 100, diseno = 50): Visor {
  const comun = comunC.f, rec = recetaC.f, nomRec = nombreReceta;
  let anio = diseno, raf = 0, jugando = false;
  const t10 = (c: Caso) => (c.d.t10_anios > horizonte ? null : c.d.t10_anios);
  el.innerHTML = `
    <svg class="visor-svg" viewBox="0 0 ${W} ${FILA * 2 + 112}" role="img" aria-label="Avance de los cloruros en el concreto según los años"></svg>
    <div class="visor-ctrl">
      <button type="button" class="btn-icono visor-play" aria-label="Reproducir">▶</button>
      <input type="range" min="0" max="${horizonte}" step="1" value="${anio}" aria-label="Año">
      <output class="visor-anio">${anio} años</output>
    </div>
    <p class="visor-estado" aria-live="polite"></p>`;
  const svg = el.querySelector("svg")!, rango = el.querySelector<HTMLInputElement>("input")!,
    salida = el.querySelector("output")!, estado = el.querySelector(".visor-estado")!, play = el.querySelector<HTMLButtonElement>(".visor-play")!;
  const X = (mm: number) => X0 + (mm / PROF_MM) * (X1 - X0);

  function fila(c: Caso, y: number, et: string, id: string) {
    const f = c.f, ini = t10(c);
    const paradas = Array.from({ length: 19 }, (_, i) => {
      const mm = (i / 18) * PROF_MM;
      return `<stop offset="${(i / 18).toFixed(3)}" stop-color="${colorCl(cloruro(f, mm, anio) / f.c_crit)}"/>`;
    }).join("");
    const oxida = ini !== null && anio >= ini;
    const frente = (() => {   // profundidad donde C = C_crit
      if (anio <= 0) return 0;
      let lo = 0, hi = PROF_MM;
      if (cloruro(f, 0, anio) < f.c_crit) return 0;
      if (cloruro(f, hi, anio) >= f.c_crit) return hi;
      for (let k = 0; k < 30; k++) { const m = (lo + hi) / 2; if (cloruro(f, m, anio) >= f.c_crit) lo = m; else hi = m; }
      return lo;
    })();
    return {
      ini,
      svg: `<defs><linearGradient id="g-${id}">${paradas}</linearGradient></defs>
      <text x="0" y="${y + 18}" class="v-et">${et}</text>
      <text x="0" y="${y + 34}" class="v-sub">${f.recubrimiento_mm} mm al acero</text>
      <rect x="${X0}" y="${y + 4}" width="${X1 - X0}" height="${FILA - 18}" rx="4" fill="url(#g-${id})"/>
      <line x1="${X0}" x2="${X0}" y1="${y}" y2="${y + FILA - 10}" class="v-cara"/>
      ${frente > 0 ? `<line x1="${X(frente)}" x2="${X(frente)}" y1="${y + 4}" y2="${y + FILA - 14}" class="v-frente"/>` : ""}
      <circle cx="${X(Math.min(f.recubrimiento_mm + 6, PROF_MM - 6))}" cy="${y + 4 + (FILA - 18) / 2}" r="7" class="${oxida ? "v-acero oxido" : "v-acero"}"/>`,
    };
  }

  function curva() {
    // cloruro en el acero (en veces el umbral) para los dos concretos, de 0 al horizonte
    const y0 = FILA * 2 + 14, h = 70, max = 2;
    const Y = (r: number) => y0 + h - (Math.min(r, max) / max) * h;
    const T = (t: number) => X0 + (t / horizonte) * (X1 - X0);
    const linea = (f: Fick) => Array.from({ length: horizonte + 1 }, (_, t) => `${T(t).toFixed(1)},${Y(cloruro(f, f.recubrimiento_mm, t) / f.c_crit).toFixed(1)}`).join(" ");
    return `<text x="0" y="${y0 + 10}" class="v-sub">cloruro en</text><text x="0" y="${y0 + 23}" class="v-sub">el acero</text>
      <line x1="${X0}" x2="${X1}" y1="${Y(1)}" y2="${Y(1)}" class="v-umbral"/><text x="${X1}" y="${Y(1) - 4}" class="v-sub" text-anchor="end">umbral medio de corrosión</text>
      <rect x="${X0}" y="${Y(1)}" width="${X1 - X0}" height="${Y(0.7) - Y(1)}" class="v-banda"/>
      <line x1="${T(diseno)}" x2="${T(diseno)}" y1="${y0}" y2="${y0 + h}" class="v-diseno"/><text x="${T(diseno) + 3}" y="${y0 + h + 12}" class="v-sub">${diseno} años de diseño</text>
      <polyline points="${linea(comun)}" class="v-l-comun"/><polyline points="${linea(rec)}" class="v-l-receta"/>
      ${[[comunC, "v-p-comun"], [recetaC, "v-p-receta"]].map(([c, k]) => { const t = t10(c as Caso); return t === null ? "" :
        `<circle cx="${T(t)}" cy="${y0 + h}" r="4" class="${k}"><title>10 % de probabilidad de corrosión: año ${Math.round(t)}</title></circle>`; }).join("")}
      <line x1="${T(anio)}" x2="${T(anio)}" y1="${y0 - 4}" y2="${y0 + h}" class="v-cursor"/>
      <text x="${X0}" y="${y0 + h + 12}" class="v-sub">0</text><text x="${X1}" y="${y0 + h + 12}" class="v-sub" text-anchor="end">${horizonte}</text>`;
  }

  function pintar() {
    const a = fila(comunC, 0, "Concreto común", "c"), b = fila(recetaC, FILA, "Receta", "r");
    svg.innerHTML = a.svg + b.svg + curva();
    salida.textContent = `${anio} años`;
    const txt = (n: string, ini: number | null) =>
      ini === null ? `${n}: menos de 10 % de probabilidad de corrosión en ${horizonte} años` :
      anio >= ini ? `${n}: ${ini < 1 ? "desde el primer año" : `desde el año ${Math.round(ini)}`} hay 10 % o más de probabilidad de que el acero se esté corroyendo` :
      `${n}: acero protegido (el riesgo llega a 10 % en el año ${Math.round(ini)})`;
    estado.textContent = `${txt("Común", a.ini)}. ${txt(nomRec, b.ini)}.`;
  }

  rango.addEventListener("input", () => { anio = Number(rango.value); pintar(); });
  const quieto = matchMedia("(prefers-reduced-motion: reduce)").matches;
  play.addEventListener("click", () => {
    jugando = !jugando;
    play.textContent = jugando ? "❚❚" : "▶";
    play.setAttribute("aria-label", jugando ? "Pausar" : "Reproducir");
    if (!jugando) return cancelAnimationFrame(raf);
    if (anio >= horizonte) anio = 0;
    if (quieto) { anio = horizonte; rango.value = String(anio); pintar(); jugando = false; play.textContent = "▶"; return; }
    let prev = 0;
    const paso = (ahora: number) => {
      if (!jugando) return;
      if (ahora - prev > 70) { prev = ahora; anio = Math.min(horizonte, anio + 1); rango.value = String(anio); pintar(); }
      if (anio >= horizonte) { jugando = false; play.textContent = "▶"; return; }
      raf = requestAnimationFrame(paso);
    };
    raf = requestAnimationFrame(paso);
  });
  pintar();
  return {
    destruir() { jugando = false; cancelAnimationFrame(raf); },
  };
}
