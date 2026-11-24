import type { Coleccion, Receta, Zona } from "./tipos";
import { REGIMENES } from "./capas";

const esc = (s: unknown) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]!));
const n0 = (x: number) => Math.round(x).toLocaleString("es-PE");
const n1 = (x: number) => x.toLocaleString("es-PE", { maximumFractionDigits: 1, minimumFractionDigits: 1 });
const n2 = (x: number) => x.toLocaleString("es-PE", { maximumFractionDigits: 2, minimumFractionDigits: 2 });

const TIPOS: [keyof NonNullable<Zona["properties"]["recetas"]> | "referencia", string, string][] = [
  ["ideal", "Ideal", "Mejor desempeño con datos que la respaldan"],
  ["economica", "Económica", "La más barata que llega a 50 años"],
  ["disponible", "Disponible", "Insumos más fáciles de conseguir, ≥ 50 años"],
  ["referencia", "Sin agente", "Referencia: mejor mezcla sin agente autorreparador"],
];

const PARTIDAS: Record<string, string> = {
  cemento: "Cemento", flete_cemento: "Flete del cemento", acceso_ultimo_tramo: "Acceso desde la vía principal", arena: "Arena gruesa", piedra: "Piedra chancada",
  superplastificante: "Superplastificante", cristalizante: "Cristalizante", agente_autorreparador: "Agente autorreparador",
};

function filaDos(nombre: string, valor: string, nota = "") {
  return `<tr><th scope="row">${nombre}</th><td class="num">${valor}</td><td class="nota">${nota}</td></tr>`;
}

function htmlReceta(r: Receta, vidaObj: number): string {
  const d = r.dosificacion, p = r.prediccion, v = r.viabilidad;
  const vidaTxt = r.vida_util_anios >= 150 ? "≥ 150" : n0(r.vida_util_anios);
  const sinTxt = r.vida_util_sin_reparacion_anios >= 150 ? "≥ 150" : n0(r.vida_util_sin_reparacion_anios);
  const estado = r.vida_util_anios >= vidaObj ? "ok" : "alerta";
  const partidas = Object.entries(v.partidas_pen).filter(([, x]) => x > 0.05)
    .map(([k, x]) => `<tr><th scope="row">${PARTIDAS[k] ?? k}</th><td class="num">S/ ${n1(x)}</td></tr>`).join("");
  const avisos = r.avisos.length
    ? `<ul class="avisos">${r.avisos.map((a) => `<li>${esc(a)}</li>`).join("")}</ul>` : "";
  return `
  <div class="metricas">
    <div class="metrica ${estado}"><span class="et">Vida útil (cloruros)</span><span class="val">${vidaTxt}<small> años</small></span>
      <span class="sub">sin reparación: ${sinTxt} años</span></div>
    <div class="metrica"><span class="et">Cierre a 90 d · fisura 0,3 mm</span><span class="val">${n0(p.cierre_pct)}<small> %</small></span>
      <span class="sub">IC 95 %: ${n0(p.cierre_ic95_pct[0])}–${n0(p.cierre_ic95_pct[1])} % · ${p.n_datos_combinacion} datos</span></div>
    <div class="metrica"><span class="et">Costo</span><span class="val">S/ ${n0(v.costo_m3_pen)}<small> /m³</small></span>
      <span class="sub">disponibilidad ${n2(v.disponibilidad)}</span></div>
  </div>
  ${avisos}
  <h4>Agente autorreparador</h4>
  <dl class="agente">
    <dt>Producto</dt><dd>${esc(r.agente_nombre)}</dd>
    <dt>Cepa</dt><dd>${esc(r.cepa)}</dd>
    <dt>Portador</dt><dd>${esc(r.portador)}</dd>
    <dt>Nutriente</dt><dd>${esc(r.nutriente)}</dd>
    <dt>Dosis</dt><dd>${esc(r.dosis_agente)}</dd>
    <dt>Curado</dt><dd>${r.curado_humedo_previo ? "Curado húmedo previo antes de exponer" : "Exposición directa"}</dd>
  </dl>
  <h4>Dosificación por m³</h4>
  <div class="tabla-scroll"><table class="dos">
    <tbody>
      ${filaDos(`Cemento tipo ${esc(d.cemento_tipo)}`, `${n0(d.cemento_kg)} kg`, `${n1(d.cemento_kg / 42.5)} bolsas`)}
      ${filaDos("Agua", `${n0(d.agua_kg)} kg`, `a/c ${n2(d.a_c)}`)}
      ${filaDos("Arena gruesa", `${n0(d.arena_kg)} kg`, "MF 2,8")}
      ${filaDos(`Piedra chancada ${d.tmn_mm === 12.5 ? "½″" : "¾″"}`, `${n0(d.piedra_kg)} kg`, `TMN ${d.tmn_mm} mm`)}
      ${d.superplastificante_kg ? filaDos("Superplastificante", `${n1(d.superplastificante_kg)} kg`, "1 % del cemento") : ""}
      ${d.cristalino_kg ? filaDos("Cristalizante integral", `${n1(d.cristalino_kg)} kg`, "1–1,5 % del cemento") : ""}
      ${d.agente_kg ? filaDos("Agente autorreparador", `${n1(d.agente_kg)} kg`, "") : ""}
      ${filaDos("Aire atrapado", `${n1(d.aire_pct)} %`, "")}
      ${filaDos("f′c estimado", `${n0(d.fc_estimado_mpa)} MPa`, "ACI 211.1")}
    </tbody></table></div>
  <h4>Costo por m³ en esta zona</h4>
  <div class="tabla-scroll"><table class="costo"><tbody>${partidas}
    <tr class="total"><th scope="row">Total</th><td class="num">S/ ${n0(v.costo_m3_pen)}</td></tr></tbody></table></div>
  <p class="fuente">Cemento desde ${esc(v.planta_cemento)} (${n0(v.dist_planta_km)} km por carretera, estimado).
    Agente: ${esc(v.proveedor_agente)}.</p>
  <p class="fuente">Origen: cierre — ${esc(r.origen.cierre)}; dosificación — ${esc(r.origen.dosificacion)};
    vida útil — ${esc(r.origen.vida_util)}.</p>`;
}

export function mostrarZona(cont: HTMLElement, z: Zona, meta: Coleccion["metadata"]) {
  const p = z.properties;
  const reg = REGIMENES[p.regimen];
  const a = p.ambiente ?? {};
  const rg = p.reglas!;
  const franjas = ["0–0,5 km del mar", "0,5–2 km del mar", "2–5 km del mar", "5–10 km del mar", "10–20 km del mar", "20–35 km del mar"];
  const rel = p.relieve ?? {};
  const urb = p.urbano ?? {};
  cont.innerHTML = `
    <header class="zona-cab">
      <p class="eyebrow">${esc(p.provincia)}, ${esc(p.departamento)} · ${franjas[p.franja] ?? ""}</p>
      <h2>${esc(p.distrito || p.id)} <small class="id">${esc(p.id)}</small></h2>
      <div class="chips">
        <span class="chip" style="--c:${reg.color}">${reg.nombre}</span>
        <span class="chip neutro">Clase ${rg.clase}</span>
        <span class="chip neutro">ISO 9223 ${esc(p.clase_iso9223)}</span>
        <span class="chip neutro">${esc(p.clase_urbana)}</span>
      </div>
    </header>
    <section class="ambiente">
      <dl>
        <dt>Niebla / garúa</dt><dd>${n2(p.indice_niebla)} <small>índice</small></dd>
        <dt>Cloruros en el aire</dt><dd>${n0(p.deposicion_cl_mg_m2_d)} <small>mg/m²·d</small></dd>
        <dt>Temperatura media</dt><dd>${n1(Number(a.t_media_c))} <small>°C</small></dd>
        <dt>Humedad relativa</dt><dd>${n0(Number(a.hr_media_pct))} <small>%</small></dd>
        <dt>Horas de niebla</dt><dd>${n1(Number(a.frac_horas_niebla) * 100)} <small>% del año</small></dd>
        <dt>Viento medio</dt><dd>${n1(Number(a.viento_medio_ms))} <small>m/s</small></dd>
        <dt>Elevación media</dt><dd>${n0(Number(rel.elev_media_m ?? 0))} <small>m</small></dd>
        <dt>En cinturón de niebla</dt><dd>${n0(Number(rel.frac_cinturon_niebla ?? 0) * 100)} <small>% del área</small></dd>
        <dt>Ladera al mar en el cinturón</dt><dd>${n0(Number(rel.frac_loma ?? 0) * 100)} <small>% del área</small></dd>
        <dt>Cresta entre mar y zona</dt><dd>${n0(Number(rel.barrera_m ?? 0))} <small>m</small></dd>
        <dt>Población 2022</dt><dd>${n0(p.poblacion)} <small>hab</small></dd>
        <dt>Densidad</dt><dd>${n0(Number(urb.densidad_hab_km2 ?? 0))} <small>hab/km²</small></dd>
        <dt>Concreto común</dt><dd>${n0(Number(p.vida_util_concreto_comun_anios ?? 0))} <small>años sin corrosión</small></dd>
        <dt>Vía principal</dt><dd>${n1(Number(urb.dist_via_principal_km ?? 0))} <small>km</small></dd>
      </dl>
      <p class="fuente">Norma aplicada: a/c ≤ ${n2(rg.a_c_max)}, cemento ≥ ${rg.cemento_min_kg} kg/m³,
        f′c ≥ ${rg.fc_min_mpa} MPa, recubrimiento ${rg.recubrimiento_mm} mm (${esc(rg.fuente)}).
        Clima: ${esc(a.fuente)}, celda ${esc(a.celda_era5)}${a.correccion_altitud_c ? `, temperatura corregida ${n1(Number(a.correccion_altitud_c))} °C por altitud` : ""}${a.celda_propia ? "" : " (celda vecina)"}.
        Concreto común = Tipo I, a/c 0,55, recubrimiento 40 mm, sin agente. Ciudad cercana: ${esc(urb.ciudad_cercana ?? "—")} (${n0(Number(urb.dist_ciudad_km ?? 0))} km).</p>
    </section>
    <nav class="pestanas" role="tablist" aria-label="Recetas">
      ${TIPOS.map(([k, nombre, desc], i) => `<button role="tab" id="tab-${k}" aria-selected="${i === 0}" data-tipo="${k}" title="${desc}">${nombre}</button>`).join("")}
    </nav>
    <p class="desc-pestana" id="desc-pestana">${TIPOS[0][2]}</p>
    <section class="receta" id="receta" role="tabpanel"></section>`;
  const caja = cont.querySelector<HTMLElement>("#receta")!;
  const desc = cont.querySelector<HTMLElement>("#desc-pestana")!;
  const pintar = (tipo: string) => {
    const r = tipo === "referencia" ? p.referencia_sin_agente! : (p.recetas as any)[tipo];
    caja.innerHTML = htmlReceta(r, meta.vida_objetivo ?? 50);
    desc.textContent = TIPOS.find(([k]) => k === tipo)![2];
    cont.querySelectorAll<HTMLButtonElement>(".pestanas button").forEach((b) => b.setAttribute("aria-selected", String(b.dataset.tipo === tipo)));
  };
  cont.querySelectorAll<HTMLButtonElement>(".pestanas button").forEach((b) => b.addEventListener("click", () => pintar(b.dataset.tipo!)));
  pintar("ideal");
  cont.scrollTop = 0;
}
