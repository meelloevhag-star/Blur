import { AGENTES, REGIMENES } from "./capas";
import type { PropsZona, Receta } from "./tipos";

const esc = (s: unknown) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]!));
const n0 = (x: number) => Math.round(x).toLocaleString("es-PE");
const n1 = (x: number) => x.toLocaleString("es-PE", { maximumFractionDigits: 1, minimumFractionDigits: 1 });
const n2 = (x: number) => x.toLocaleString("es-PE", { maximumFractionDigits: 2, minimumFractionDigits: 2 });
const anios = (x: number) => (x >= 150 ? "150+" : n0(x));
const FRANJA_TXT = ["A menos de 500 m del mar", "A 0,5–2 km del mar", "A 2–5 km del mar", "A 5–10 km del mar", "A 10–20 km del mar", "A 20–35 km del mar"];
export const TIPOS = [
  ["ideal", "Mejor desempeño"],
  ["economica", "Más económica"],
  ["disponible", "Más fácil de conseguir"],
] as const;

export function recetaEnPalabras(r: Receta): string {
  const d = r.dosificacion;
  const ag = AGENTES[r.agente]?.nombre ?? r.agente_nombre;
  return `Cemento tipo ${d.cemento_tipo}, relación agua/cemento ${n2(d.a_c)}, con ${ag.toLowerCase()}`;
}

function porQue(p: PropsZona): string {
  const reg = REGIMENES[p.regimen];
  const partes = [reg?.explicacion ?? ""];
  const vida = p.vida_util_concreto_comun_anios;
  if (vida < 150) partes.push(`Aquí, un concreto común empieza a oxidar su acero en unos ${n0(vida)} años.`);
  else partes.push("Un concreto común aguanta bien la corrosión aquí; el agente sirve sobre todo para sellar fisuras.");
  return partes.join(" ");
}

function barra(etiqueta: string, v: number, clase: string) {
  const pct = Math.min(v, 150) / 150 * 100;
  return `<div class="barra ${clase}"><span class="barra-et">${etiqueta}</span>
    <span class="barra-pista"><span class="barra-relleno" style="--p:${pct}%"></span></span>
    <span class="barra-val">${anios(v)} años</span></div>`;
}

export function htmlReceta(r: Receta, p: PropsZona): string {
  const v = r.viabilidad, d = r.dosificacion, pr = r.prediccion;
  const disp = Math.round(v.disponibilidad * 100);
  const avisos = r.avisos.length ? `<p class="aviso">${r.avisos.map(esc).join(". ")}.</p>` : "";
  return `
    <p class="receta-frase">${esc(recetaEnPalabras(r))}.</p>
    <div class="cifras">
      <div><span class="cifra">S/ ${n0(v.costo_m3_pen)}</span><span class="cifra-et">por m³ puesto en obra</span></div>
      <div><span class="cifra">${n0(pr.cierre_pct)} %</span><span class="cifra-et">de una fisura de 0,3 mm sellada a los 90 días</span></div>
      <div><span class="cifra">${disp} %</span><span class="cifra-et">facilidad para conseguir los insumos</span></div>
    </div>
    <div class="barras" aria-label="Años hasta la corrosión del acero">
      ${barra("Esta receta", r.vida_util_anios, "b-receta")}
      ${barra("La misma, sin sellar fisuras", r.vida_util_sin_reparacion_anios, "b-sin")}
      ${barra("Concreto común de hoy", p.vida_util_concreto_comun_anios, "b-comun")}
    </div>
    ${avisos}
    <details class="plegable">
      <summary>Dosificación por m³</summary>
      <table class="dos"><tbody>
        <tr><th scope="row">Cemento tipo ${esc(d.cemento_tipo)}</th><td>${n0(d.cemento_kg)} kg</td><td>${n1(d.cemento_kg / 42.5)} bolsas</td></tr>
        <tr><th scope="row">Agua</th><td>${n0(d.agua_kg)} kg</td><td>a/c ${n2(d.a_c)}</td></tr>
        <tr><th scope="row">Arena gruesa</th><td>${n0(d.arena_kg)} kg</td><td>módulo de finura 2,8</td></tr>
        <tr><th scope="row">Piedra chancada ${d.tmn_mm <= 12.5 ? "½″" : "¾″"}</th><td>${n0(d.piedra_kg)} kg</td><td></td></tr>
        ${d.superplastificante_kg ? `<tr><th scope="row">Superplastificante</th><td>${n1(d.superplastificante_kg)} kg</td><td>1 % del cemento</td></tr>` : ""}
        ${d.cristalino_kg ? `<tr><th scope="row">Cristalizante</th><td>${n1(d.cristalino_kg)} kg</td><td></td></tr>` : ""}
        ${d.agente_kg ? `<tr><th scope="row">Agente autorreparador</th><td>${n1(d.agente_kg)} kg</td><td>${esc(r.dosis_agente)}</td></tr>` : ""}
        <tr><th scope="row">Resistencia esperada</th><td>${n0(d.fc_estimado_mpa)} MPa</td><td>f′c a 28 días</td></tr>
      </tbody></table>
      <p class="nota">Agente: ${esc(r.agente_nombre)}. Cepa: ${esc(r.cepa)}. Nutriente: ${esc(r.nutriente)}.
        ${r.curado_humedo_previo ? "Con curado húmedo antes de exponer." : "Exposición directa tras el vaciado."}
        Cemento desde ${esc(v.planta_cemento)}, a ${n0(v.dist_planta_km)} km por carretera.</p>
      <button type="button" class="btn-sec" data-copiar>Copiar dosificación</button>
    </details>`;
}

export function htmlFicha(p: PropsZona, tipo: string): string {
  const reg = REGIMENES[p.regimen];
  const r = (p.recetas as any)[tipo] as Receta;
  const a = p.ambiente ?? {}, rel = p.relieve ?? {}, urb = p.urbano ?? {};
  return `
    <header class="ficha-cab">
      <div class="ficha-titulos">
        <h2 id="ficha-titulo">${esc(p.distrito)}</h2>
        <p class="ficha-sub">${esc(p.provincia)}, ${esc(p.departamento)}. ${FRANJA_TXT[p.franja] ?? ""}.</p>
      </div>
      <div class="ficha-acciones">
        <button type="button" class="btn-icono" data-comparar aria-pressed="false" title="Comparar con otras zonas">Comparar</button>
        <button type="button" class="btn-icono" data-cerrar aria-label="Cerrar ficha">✕</button>
      </div>
    </header>
    <p class="etiqueta-reg"><span class="punto" style="background:${reg?.color}"></span>${reg?.nombre ?? p.regimen}
      <span class="sep">·</span>${esc(p.clase_urbana)}${p.poblacion ? `, ${n0(p.poblacion)} hab.` : ""}</p>
    <p class="porque">${esc(porQue(p))}</p>

    <section class="bloque-receta luz" aria-labelledby="t-receta">
      <h3 id="t-receta">Qué concreto usar aquí</h3>
      <div class="segmentos" role="tablist" aria-label="Tipo de receta">
        ${TIPOS.map(([k, n]) => `<button role="tab" type="button" data-tipo="${k}" aria-selected="${k === tipo}">${n}</button>`).join("")}
      </div>
      <div class="receta" role="tabpanel">${htmlReceta(r, p)}</div>
    </section>

    <section class="bloque-terreno" aria-labelledby="t-terreno">
      <h3 id="t-terreno">El terreno de este tramo</h3>
      <div class="maqueta luz">
        <canvas id="maqueta" role="img" aria-label="Maqueta 3D del tramo de costa: mar al frente, cerros al fondo"></canvas>
        <p class="maqueta-ayuda">Pasa el cursor para girar el tramo y soltar la neblina de las laderas.</p>
        <div class="maqueta-botones">
          <button type="button" class="btn-sec" data-girar>Girar</button>
          <button type="button" class="btn-sec" data-soplar aria-pressed="false">Ver neblina</button>
        </div>
        <p class="maqueta-sin" hidden>Tu navegador no muestra 3D. El perfil de abajo resume el mismo terreno.</p>
      </div>
      <p class="leyenda-maqueta"><span class="ln ln-niebla"></span>300 y 1 000 m: franja de nubes donde se forma la neblina
        <span class="ln ln-franja"></span>zona elegida</p>
      <div id="perfil" class="perfil"></div>
    </section>

    <details class="plegable luz">
      <summary>Clima y territorio</summary>
      <dl class="datos">
        <div><dt>Neblina</dt><dd>${n2(p.indice_niebla)} de 1</dd></div>
        <div><dt>Sal en el aire</dt><dd>${n0(p.deposicion_cl_mg_m2_d)} mg/m²·día</dd></div>
        <div><dt>Temperatura media</dt><dd>${n1(Number(a.t_media_c ?? 0))} °C</dd></div>
        <div><dt>Humedad media</dt><dd>${n0(Number(a.hr_media_pct ?? 0))} %</dd></div>
        <div><dt>Altura media</dt><dd>${n0(Number(rel.elev_media_m ?? 0))} m</dd></div>
        <div><dt>Laderas al mar en la franja de nubes</dt><dd>${n0(Number(rel.frac_loma ?? 0) * 100)} % del área</dd></div>
        <div><dt>Cerro entre el mar y la zona</dt><dd>${n0(Number(rel.barrera_m ?? 0))} m</dd></div>
        <div><dt>Carretera principal</dt><dd>a ${n1(Number(urb.dist_via_principal_km ?? 0))} km</dd></div>
      </dl>
    </details>
    <details class="plegable luz">
      <summary>Datos técnicos</summary>
      <p class="nota">Clase de exposición ${esc(p.reglas?.clase)} (${esc(p.reglas?.fuente)}): a/c máximo ${n2(p.reglas?.a_c_max ?? 0)},
        cemento mínimo ${p.reglas?.cemento_min_kg} kg/m³, f′c mínimo ${p.reglas?.fc_min_mpa} MPa, recubrimiento ${p.reglas?.recubrimiento_mm} mm.
        Corrosividad atmosférica ISO 9223 ${esc(p.clase_iso9223)}. Clima ERA5 2024, celda ${esc(a.celda_era5)}${a.correccion_altitud_c ? `, corregido ${n1(a.correccion_altitud_c)} °C por altitud` : ""}.
        Cierre de fisura: ${esc(r.origen.cierre)}, ${r.prediccion.n_datos_combinacion} ensayos en Blur con esta combinación
        (intervalo ${n0(r.prediccion.cierre_ic95_pct[0])}–${n0(r.prediccion.cierre_ic95_pct[1])} %). Vida útil: ${esc(r.origen.vida_util)}.
        Zona ${esc(p.id)}.</p>
    </details>`;
}

/** Perfil del tramo: las 6 franjas de la costa al interior (altura, neblina y sal). */
export function htmlPerfil(zonas: PropsZona[], sel: string): string {
  const fs = [...zonas].sort((a, b) => a.franja - b.franja);
  const W = 340, H = 120, x0 = 8, x1 = W - 8;
  const pos = [0.25, 1.25, 3.5, 7.5, 15, 27.5];
  const X = (km: number) => x0 + (Math.log1p(km) / Math.log1p(35)) * (x1 - x0);
  const hmax = Math.max(1100, ...fs.map((z) => z.elevacion_media_m ?? 0));
  const Y = (h: number) => H - 22 - (Math.max(h, 0) / hmax) * (H - 40);
  const pts = fs.map((z) => [X(pos[z.franja]), Y(z.elevacion_media_m ?? 0)]);
  const area = `M${x0},${H - 22} ` + pts.map(([x, y]) => `L${x.toFixed(1)},${y.toFixed(1)}`).join(" ") + ` L${x1},${pts.at(-1)?.[1] ?? H - 22} L${x1},${H - 22} Z`;
  const banda = `<rect x="${x0}" y="${Y(1000)}" width="${x1 - x0}" height="${Y(300) - Y(1000)}" class="pf-banda"/>`;
  const cortes = [0.5, 2, 5, 10, 20].map((k) => `<line x1="${X(k)}" x2="${X(k)}" y1="10" y2="${H - 22}" class="pf-corte"/>`).join("");
  const botones = fs.map((z, i) => {
    const xa = X([0, 0.5, 2, 5, 10, 20][z.franja]), xb = X([0.5, 2, 5, 10, 20, 35][z.franja]);
    const r = 3 + z.indice_niebla * 6;
    return `<g class="pf-franja${z.id === sel ? " sel" : ""}" data-zona="${z.id}" role="button" tabindex="0"
      aria-label="Franja ${(FRANJA_TXT[z.franja] ?? "").toLowerCase()}: neblina ${n2(z.indice_niebla)}, altura ${n0(z.elevacion_media_m ?? 0)} m">
      <rect x="${xa}" y="6" width="${xb - xa}" height="${H - 28}" class="pf-hit"/>
      <circle cx="${pts[i][0]}" cy="${pts[i][1] - 10}" r="${r.toFixed(1)}" class="pf-niebla"/></g>`;
  }).join("");
  const ejes = `<text x="${x0}" y="${H - 6}" class="pf-txt">mar</text><text x="${X(5)}" y="${H - 6}" class="pf-txt" text-anchor="middle">5 km</text><text x="${x1}" y="${H - 6}" class="pf-txt" text-anchor="end">35 km</text>
    <text x="${x1}" y="${Y(1000) - 3}" class="pf-txt" text-anchor="end">franja de nubes</text>`;
  return `<svg viewBox="0 0 ${W} ${H}" role="group" aria-label="Perfil del tramo de la costa al interior">
    ${banda}${cortes}<path d="${area}" class="pf-tierra"/>${botones}${ejes}</svg>
    <p class="nota">Cada círculo es una franja: más grande, más neblina. Toca una para verla.</p>`;
}
