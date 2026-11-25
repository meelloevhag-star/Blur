/**
 * Ficha de zona en nodos: la topografía arriba, y debajo una vía de nodos que se abren de a uno
 * (condiciones → concretos y recetas → en el tiempo → costo aproximado). Nada de texto largo a la vista:
 * cada nodo cerrado muestra solo su título y un dato.
 */
import { AGENTES, REGIMENES } from "./capas";
import type { Durabilidad, Fick, PropsZona, Receta } from "./tipos";

export const esc = (s: unknown) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]!));
const n0 = (x: number) => Math.round(x).toLocaleString("es-PE");
const n1 = (x: number) => x.toLocaleString("es-PE", { maximumFractionDigits: 1, minimumFractionDigits: 1 });
const n2 = (x: number) => x.toLocaleString("es-PE", { maximumFractionDigits: 2, minimumFractionDigits: 2 });

export const TIPOS = [
  ["ideal", "Mejor desempeño"],
  ["economica", "Más económica"],
  ["disponible", "Más fácil de conseguir"],
] as const;
export type Tipo = (typeof TIPOS)[number][0];
export type Modo = "interior" | "frente";

/** Vida de diseño contra la que se juzga cada receta (EN 1990 / E.060: edificaciones comunes). */
export const VIDA_DISENO = 50;
export const HORIZONTE = 100;

/** Lo que cambia según dónde esté la obra dentro de la celda. */
export interface Vista {
  regimen: string; indice_niebla: number; deposicion_cl_mg_m2_d: number; clase_iso9223: string;
  vida_comun: number; comun?: Durabilidad; fick_comun?: Fick; reglas: PropsZona["reglas"]; aviso?: string | null;
  recetas: { ideal: Receta; economica: Receta; disponible: Receta };
}
export function vista(p: PropsZona, modo: Modo): Vista {
  const f = modo === "frente" && p.frente ? p.frente : null;
  return f
    ? { regimen: f.regimen, indice_niebla: f.indice_niebla, deposicion_cl_mg_m2_d: f.deposicion_cl_mg_m2_d, clase_iso9223: f.clase_iso9223,
        vida_comun: f.vida_util_concreto_comun_anios, comun: f.durabilidad_comun, fick_comun: f.fick_comun, reglas: f.reglas,
        recetas: f.recetas, aviso: f.aviso }
    : { regimen: p.regimen, indice_niebla: p.indice_niebla, deposicion_cl_mg_m2_d: p.deposicion_cl_mg_m2_d, clase_iso9223: p.clase_iso9223,
        vida_comun: p.vida_util_concreto_comun_anios, comun: p.durabilidad_comun, fick_comun: p.fick_comun, reglas: p.reglas,
        recetas: p.recetas!, aviso: p.aviso };
}

export function recetaCorta(r: Receta): string {
  const d = r.dosificacion;
  return `Cemento ${d.cemento_tipo} · a/c ${n2(d.a_c)} · ${(AGENTES[r.agente]?.corto ?? r.agente_nombre).toLowerCase()}`;
}
export function recetaEnPalabras(r: Receta): string {
  const d = r.dosificacion;
  return `Cemento tipo ${d.cemento_tipo}, a/c ${n2(d.a_c)}, con ${(AGENTES[r.agente]?.nombre ?? r.agente_nombre).toLowerCase()}`;
}

/**
 * Veredicto con el criterio de fib B34: cumple una vida de diseño si la probabilidad de que el acero
 * empiece a corroerse antes de esa edad es ≤ 10 % (β ≥ 1,3). Sin años inventados más allá de 100.
 */
export function veredicto(d: Durabilidad | undefined): { ok: boolean; txt: string; corto: string; detalle: string } {
  if (!d) return { ok: false, txt: "Sin cálculo", corto: "—", detalle: "" };
  const pf50 = Math.round(d.pf["50"] * 100);
  const detalle = `${pf50 < 1 ? "menos de 1" : pf50} % de probabilidad de corrosión antes de 50 años`;
  if (d.cumple_anios >= 100) return { ok: true, txt: "Cumple 100 años", corto: "100 años", detalle };
  if (d.cumple_anios >= VIDA_DISENO) return { ok: true, txt: `Cumple ${d.cumple_anios} años, no 100`, corto: `${d.cumple_anios} años`, detalle };
  if (d.cumple_anios > 0) return { ok: false, txt: `Solo cumple ${d.cumple_anios} años`, corto: `${d.cumple_anios} años`, detalle };
  return { ok: false, txt: "No llega a 25 años", corto: "< 25 años", detalle };
}

const ICONO: Record<string, string> = {
  terreno: `<path d="M2 18 8 9l4 5 3-4 7 8z"/>`,
  condiciones: `<path d="M4 15a5 5 0 0 1 4-8 6 6 0 0 1 11 2 4 4 0 0 1-1 8H7a3 3 0 0 1-3-2z"/>`,
  recetas: `<path d="M5 4h14v4H5zM7 8v12h10V8"/><path d="M10 12h4M10 16h4"/>`,
  tiempo: `<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>`,
  costo: `<path d="M12 3v18M16 7.5c0-1.5-1.8-2.5-4-2.5s-4 1-4 3 1.8 2.5 4 3 4 1.5 4 3.5-1.8 3-4 3-4-1-4-2.5"/>`,
};
const icono = (k: string) => `<svg viewBox="0 0 24 24" aria-hidden="true" class="ico">${ICONO[k]}</svg>`;

function nodo(id: string, titulo: string, dato: string, cuerpo: string, abierto: boolean) {
  return `<li class="nodo${abierto ? " abierto" : ""}" data-nodo="${id}">
    <button type="button" class="nodo-cab" aria-expanded="${abierto}" aria-controls="n-${id}">
      <span class="nodo-punto">${icono(id)}</span><span class="nodo-titulo">${titulo}</span><span class="nodo-dato">${dato}</span>
      <span class="nodo-flecha" aria-hidden="true"></span>
    </button>
    <div class="nodo-cuerpo" id="n-${id}" ${abierto ? "" : "hidden"}>${cuerpo}</div></li>`;
}

function filaCond(ic: string, et: string, val: string, frac: number, nota = "") {
  return `<div class="cond"><span class="cond-et">${et}</span><span class="cond-val">${val}</span>
    <span class="cond-barra"><span style="--p:${Math.round(Math.max(0, Math.min(1, frac)) * 100)}%" data-ic="${ic}"></span></span>
    ${nota ? `<span class="cond-nota">${nota}</span>` : ""}</div>`;
}

function htmlCondiciones(p: PropsZona, v: Vista) {
  const reg = REGIMENES[v.regimen];
  const rel = p.relieve ?? {}, a = p.ambiente ?? {};
  const salFrac = Math.log10(Math.max(v.deposicion_cl_mg_m2_d, 1)) / Math.log10(1500);
  return `<div class="conds">
    ${filaCond("reg", "Exposición", `${reg?.nombre ?? v.regimen} · ${esc(v.reglas?.clase ?? "")}`, [0.15, 0.3, 0.55, 0.8, 1][["seco", "atmosferico_marino", "niebla_orografica", "niebla_salina", "salpicadura"].indexOf(v.regimen)] ?? 0.5)}
    ${filaCond("niebla", "Neblina y garúa", `${n2(v.indice_niebla)} de 1`, v.indice_niebla)}
    ${filaCond("sal", "Sal en el aire", `${n0(v.deposicion_cl_mg_m2_d)} mg/m²·día`, salFrac, `ISO 9223 ${esc(v.clase_iso9223)}`)}
    ${filaCond("alt", "Altura media", `${n0(Number(rel.elev_media_m ?? p.elevacion_media_m ?? 0))} m`, Number(rel.elev_media_m ?? 0) / 1500,
      Number(rel.frac_loma ?? 0) > 0.05 ? `${n0(Number(rel.frac_loma) * 100)} % son laderas con neblina` : "")}
    ${filaCond("pob", "Población", `${n0(p.poblacion)} hab.`, Math.log10(Math.max(p.poblacion, 1)) / 6, esc(p.clase_urbana))}
    <p class="nota">${n1(Number(a.t_media_c ?? 0))} °C y ${n0(Number(a.hr_media_pct ?? 0))} % de humedad en promedio · a ${n1(p.dist_mar_km)} km del mar.</p>
  </div>`;
}

const firma = (r: Receta) => `${r.agente}|${r.dosificacion.cemento_tipo}|${r.dosificacion.a_c}|${r.dosificacion.tmn_mm}|${r.recubrimiento_mm}|${r.curado_humedo_previo}`;

function htmlTarjetas(v: Vista, tipo: Tipo) {
  return `<div class="tarjetas" role="radiogroup" aria-label="Receta">${TIPOS.map(([k, nombre]) => {
    const r = v.recetas[k], ve = veredicto(r.durabilidad);
    const igual = k !== "ideal" && firma(r) === firma(v.recetas.ideal);
    return `<button type="button" role="radio" class="tarjeta${k === tipo ? " sel" : ""}" data-tipo="${k}" aria-checked="${k === tipo}">
      <span class="tarjeta-tit">${nombre}</span>
      <span class="tarjeta-receta">${igual ? "La misma que la de mejor desempeño" : esc(recetaCorta(r))}</span>
      <span class="tarjeta-vida ${ve.ok ? "ok" : "no"}">${ve.ok ? "✓" : "!"} ${ve.corto}</span></button>`;
  }).join("")}</div>`;
}

export function htmlDosificacion(r: Receta) {
  const d = r.dosificacion;
  const ve = veredicto(r.durabilidad);
  return `<p class="receta-frase">${esc(recetaEnPalabras(r))}</p>
    <p class="veredicto ${ve.ok ? "ok" : "no"}">${ve.txt} <span>${ve.detalle}</span></p>
    <p class="nota">Sella ${n0(r.prediccion.cierre_pct)} % de una fisura de 0,3 mm a los 90 días (protege la fisura; no se suma a la vida útil).</p>
    <table class="dos"><tbody>
      <tr><th scope="row">Cemento ${esc(d.cemento_tipo)}</th><td>${n0(d.cemento_kg)} kg</td><td>${n1(d.cemento_kg / 42.5)} bolsas</td></tr>
      <tr><th scope="row">Agua</th><td>${n0(d.agua_kg)} kg</td><td>a/c ${n2(d.a_c)}</td></tr>
      <tr><th scope="row">Arena gruesa</th><td>${n0(d.arena_kg)} kg</td><td></td></tr>
      <tr><th scope="row">Piedra ${d.tmn_mm <= 12.5 ? "½″" : "¾″"}</th><td>${n0(d.piedra_kg)} kg</td><td></td></tr>
      ${d.superplastificante_kg ? `<tr><th scope="row">Superplastificante</th><td>${n1(d.superplastificante_kg)} kg</td><td></td></tr>` : ""}
      ${d.cristalino_kg ? `<tr><th scope="row">Cristalizante</th><td>${n1(d.cristalino_kg)} kg</td><td></td></tr>` : ""}
      ${d.agente_kg ? `<tr><th scope="row">Agente</th><td>${n1(d.agente_kg)} kg</td><td>${esc(r.dosis_agente)}</td></tr>` : ""}
      <tr><th scope="row">f′c especificado</th><td>${n0((d as any).fc_especificado_mpa ?? d.fc_estimado_mpa)} MPa</td><td>media ${n0(d.fc_estimado_mpa)} MPa</td></tr>
      <tr><th scope="row">Recubrimiento</th><td>${r.recubrimiento_mm} mm</td><td>al acero</td></tr>
    </tbody></table>
    <div class="fila-acciones"><button type="button" class="btn-sec" data-copiar>Copiar dosificación</button>
      <button type="button" class="btn-txt" data-info aria-expanded="false">ⓘ De dónde sale</button></div>
    <p class="nota info" hidden>Cierre: ${esc(r.origen.cierre)} (${r.prediccion.n_datos_combinacion} ensayos de Blur con esta combinación,
      IC 95 % ${n0(r.prediccion.cierre_ic95_pct[0])}–${n0(r.prediccion.cierre_ic95_pct[1])} %). Dosificación: ${esc(r.origen.dosificacion)}.
      Vida útil: ${esc(r.origen.vida_util)}; con 10 % de probabilidad el acero se despasiva a los ${n0(r.durabilidad.t10_anios)}${r.durabilidad.t10_anios > 100 ? "+" : ""} años. ${r.avisos.length ? esc(r.avisos.join(". ")) + "." : ""}</p>`;
}

const PARTIDAS: [string, string[]][] = [
  ["Cemento", ["cemento"]], ["Agregados", ["arena", "piedra"]], ["Aditivos", ["superplastificante", "cristalizante"]],
  ["Agente autorreparador", ["agente_autorreparador"]], ["Flete y acceso", ["flete_cemento", "acceso_ultimo_tramo"]],
];
export function htmlCosto(r: Receta, nombreTipo: string) {
  const v = r.viabilidad;
  const filas = PARTIDAS.map(([et, ks]) => [et, ks.reduce((s, k) => s + (v.partidas_pen[k] ?? 0), 0)] as [string, number]).filter(([, x]) => x > 0.5);
  const max = Math.max(...filas.map(([, x]) => x));
  const disp = Math.round(v.disponibilidad * 100);
  return `<p class="costo-total"><span>S/ ${n0(v.costo_m3_pen)}</span> por m³ puesto en obra <small>${esc(nombreTipo.toLowerCase())}</small></p>
    <div class="partidas">${filas.map(([et, x]) => `<div class="partida"><span>${et}</span>
      <span class="partida-barra"><span style="--p:${(x / max * 100).toFixed(0)}%"></span></span><span>S/ ${n0(x)}</span></div>`).join("")}</div>
    <div class="medidor" role="meter" aria-valuemin="0" aria-valuemax="100" aria-valuenow="${disp}" aria-label="Facilidad para conseguir los insumos">
      <span class="medidor-et">Facilidad para conseguir los insumos</span><span class="medidor-pista"><span style="--p:${disp}%"></span></span><span>${disp} %</span></div>
    <p class="nota">Cemento desde ${esc(v.planta_cemento)} (${n0(v.dist_planta_km)} km por carretera). Agente: ${esc(v.proveedor_agente)}.
      Precios de catálogo con fuente y fecha; los marcados como estimados deben cotizarse.</p>`;
}

export interface EstadoFicha { modo: Modo; tipo: Tipo; abierto: string | null }

export function htmlZona(p: PropsZona, e: EstadoFicha): string {
  const v = vista(p, e.modo);
  const reg = REGIMENES[v.regimen];
  const r = v.recetas[e.tipo];
  const nombreTipo = TIPOS.find(([k]) => k === e.tipo)![1];
  const rel = p.relieve ?? {};
  const comun = veredicto(v.comun);
  return `
    <header class="ficha-cab">
      <div class="ficha-titulos">
        <h2 id="ficha-titulo">${esc(p.distrito)}</h2>
        <p class="ficha-sub">${esc(p.provincia)}, ${esc(p.departamento)}</p>
      </div>
      <div class="ficha-acciones">
        <button type="button" class="btn-icono" data-comparar aria-pressed="false" aria-label="Fijar para comparar" title="Comparar">⇆</button>
        <button type="button" class="btn-icono" data-cerrar aria-label="Cerrar ficha">✕</button>
      </div>
    </header>
    <p class="etiqueta-reg"><span class="punto" style="background:${reg?.color}"></span>${reg?.nombre ?? v.regimen}</p>
    ${p.frente_marino && p.frente ? `<div class="modo" role="radiogroup" aria-label="Dónde está la obra">
      <span>Mi obra está</span>
      <button type="button" role="radio" data-modo="frente" aria-checked="${e.modo === "frente"}">frente al mar</button>
      <button type="button" role="radio" data-modo="interior" aria-checked="${e.modo === "interior"}">tierra adentro</button></div>` : ""}

    <section class="raiz" aria-labelledby="t-terreno">
      <h3 id="t-terreno" class="oculto">Topografía de la celda</h3>
      <div class="maqueta">
        <canvas id="maqueta" role="img" aria-label="Maqueta 3D de la celda: mar al frente, cerros al fondo; contorno verde: la celda"></canvas>
        <div class="maqueta-botones">
          <button type="button" class="btn-sec chico" data-girar>Girar</button>
          <button type="button" class="btn-sec chico" data-soplar aria-pressed="false">Neblina</button>
        </div>
        <p class="maqueta-sin" hidden>Tu navegador no muestra 3D.</p>
      </div>
      <p class="raiz-pie">${n0(Number(rel.elev_media_m ?? 0))} m de altura media${Number(rel.frac_loma ?? 0) > 0.05 ? ` · ${n0(Number(rel.frac_loma) * 100)} % laderas con neblina` : ""} · celda de 10 km</p>
    </section>

    ${v.aviso ? `<p class="aviso">${esc(v.aviso)}</p>` : ""}
    <ol class="via">
      ${nodo("condiciones", "Condiciones de la zona", esc(v.reglas?.clase ?? ""), htmlCondiciones(p, v), e.abierto === "condiciones")}
      ${nodo("recetas", "Concretos y recetas", esc(AGENTES[v.recetas.ideal.agente]?.corto ?? ""),
        htmlTarjetas(v, e.tipo) + `<div class="receta-detalle">${htmlDosificacion(r)}</div>`, e.abierto === "recetas")}
      ${nodo("tiempo", "En el tiempo", `común: ${comun.corto}`,
        `<div id="visor" class="visor"></div>`, e.abierto === "tiempo")}
      ${nodo("costo", "Costo aproximado", `S/ ${n0(r.viabilidad.costo_m3_pen)}/m³`, htmlCosto(r, nombreTipo), e.abierto === "costo")}
    </ol>
    <p class="nota pie-ficha">Zona ${esc(p.id)} · guía para planificar ensayos, no reemplaza el diseño firmado por un ingeniero.</p>`;
}
