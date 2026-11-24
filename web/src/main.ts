import { crearFuente } from "./api";
import { CAPAS, REGIMENES, color, etiquetasLeyenda, type Capa } from "./capas";
import { mostrarZona } from "./panel";
import type { Coleccion, PropsZona } from "./tipos";

declare const L: typeof import("leaflet");

const fuente = crearFuente();
const $ = <T extends HTMLElement>(s: string) => document.querySelector<T>(s)!;

function leerCapa(): string {
  try { return localStorage.getItem("atlas-capa") ?? "regimen"; } catch { return "regimen"; }
}
function guardarCapa(id: string) {
  try { localStorage.setItem("atlas-capa", id); } catch { /* sin almacenamiento */ }
}

async function iniciar() {
  const mapa = L.map("mapa", { zoomControl: true, attributionControl: true, preferCanvas: false, minZoom: 4 })
    .setView([-11.5, -77.5], 5);
  mapa.attributionControl.setPrefix(false).addAttribution("Natural Earth · ERA5/Open-Meteo · datos Blur");

  const estilos = getComputedStyle(document.documentElement);
  const tok = (n: string) => estilos.getPropertyValue(n).trim();
  try {
    const deptos = await (await fetch("departamentos_per.geojson")).json();
    L.geoJSON(deptos, { interactive: false, style: { color: tok("--linea"), weight: 0.8, fillColor: tok("--tierra"), fillOpacity: 1 } }).addTo(mapa);
  } catch { /* el mapa funciona sin el fondo */ }

  const col: Coleccion = await fuente.zonas();
  const meta = col.metadata;
  let capa: Capa = CAPAS.find((c) => c.id === leerCapa()) ?? CAPAS[0];
  let seleccion: L.Path | null = null;

  const estilo = (f?: GeoJSON.Feature<GeoJSON.Polygon, PropsZona>) => ({
    color: tok("--borde-zona"), weight: 0.5, fillOpacity: 0.85,
    fillColor: f ? color(capa, capa.valor(f.properties)) : "#999",
  });
  const capaZonas = L.geoJSON(col as any, {
    style: estilo as any,
    onEachFeature: (f: any, l: any) => {
      const p = f.properties as PropsZona;
      l.bindTooltip(`<strong>${p.departamento}</strong> · ${REGIMENES[p.regimen]?.corto ?? p.regimen}<br>${capa.nombre}: ${fmt(capa, capa.valor(p))}`, { sticky: true });
      l.on("click", async () => {
        if (seleccion) capaZonas.resetStyle(seleccion as any);
        seleccion = l;
        l.setStyle({ weight: 2.5, color: tok("--acento") });
        l.bringToFront();
        const z = await fuente.zona(p.id);
        mostrarZona($("#detalle"), z, meta);
        $("#panel").classList.add("con-zona");
        try { history.replaceState(null, "", `#${p.id}`); } catch { /* ignorar */ }
      });
      l.on("mouseover", () => l.setTooltipContent(`<strong>${p.departamento}</strong> · ${REGIMENES[p.regimen]?.corto ?? p.regimen}<br>${capa.nombre}: ${fmt(capa, capa.valor(p))}`));
    },
  }).addTo(mapa);
  mapa.fitBounds(capaZonas.getBounds(), { padding: [10, 10] });

  // selector de capas
  const sel = $<HTMLSelectElement>("#capa");
  sel.innerHTML = CAPAS.map((c) => `<option value="${c.id}">${c.nombre}</option>`).join("");
  sel.value = capa.id;
  const pintarLeyenda = () => {
    $("#leyenda-titulo").textContent = capa.leyenda;
    const et = etiquetasLeyenda(capa);
    $("#leyenda-escala").innerHTML = capa.colores.map((c, i) =>
      `<li><span class="muestra" style="background:${c}"></span>${et[i]}${capa.unidad && !capa.etiquetas && i === et.length - 1 ? ` ${capa.unidad}` : ""}</li>`).join("");
  };
  sel.addEventListener("change", () => {
    capa = CAPAS.find((c) => c.id === sel.value)!;
    guardarCapa(capa.id);
    capaZonas.setStyle(estilo as any);
    if (seleccion) (seleccion as any).setStyle({ weight: 2.5, color: tok("--acento") });
    pintarLeyenda();
  });
  pintarLeyenda();

  // resumen del modelo
  const cv = meta.cv_modelo;
  $("#modelo").innerHTML = `Modelo v${meta.modelo_version}: R² agrupado ${cv.conjunto.R2.toLocaleString("es-PE")}
    (XGBoost ${cv.xgb.R2.toLocaleString("es-PE")}, NEAT ${cv.neat.R2.toLocaleString("es-PE")}),
    error medio ±${cv.conjunto.MAE_pct.toLocaleString("es-PE")} puntos de cierre.
    Difusión de cloruros: ${meta.durabilidad.drcm.n} ensayos RCM (R² log ${meta.durabilidad.drcm.r2_log.toLocaleString("es-PE")}).
    ${meta.zonas_con_clima_propio} de ${meta.zonas} zonas con clima propio.`;
  const conteo: Record<string, number> = {};
  col.features.forEach((f) => (conteo[f.properties.regimen] = (conteo[f.properties.regimen] ?? 0) + 1));
  $("#regimenes").innerHTML = Object.entries(REGIMENES).map(([k, r]) =>
    `<li><span class="muestra" style="background:${r.color}"></span>${r.nombre}<span class="num">${conteo[k] ?? 0}</span></li>`).join("");

  // abrir la zona del enlace o una de Paita por defecto
  const inicial = location.hash.slice(1) || col.features.find((f) => f.properties.departamento === "Piura" && f.properties.franja === 0 && Math.abs((f.geometry.coordinates[0][0][1]) + 5.08) < 0.15)?.properties.id;
  capaZonas.eachLayer((l: any) => { if (l.feature.properties.id === inicial) l.fire("click"); });

  iniciarAportes();
}

function fmt(c: Capa, v: number) {
  if (c.id === "regimen") return c.etiquetas![v];
  if (c.id === "ganancia") return `+${Math.round(v)} años`;
  if (c.id === "cloruros") return `${Math.round(v)} mg/m²·d`;
  if (c.id === "costo") return `S/ ${Math.round(v)}/m³`;
  if (c.unidad === "%") return `${Math.round(v)} %`;
  return v.toFixed(2);
}

const COLUMNAS = ["autor_aporte", "institucion", "tipo_fuente", "doi_o_url", "norma_ensayo", "fecha_ensayo", "id_probeta",
  "a_c", "nivel_proteccion", "ambiente_marino", "usa_lactato", "curado_previo", "w0_mm", "edad_dias", "wt_mm", "cierre_pct",
  "notas", "portador", "tiene_bacterias", "cepa", "dosis_bacteria", "nutriente", "nutriente_dosis_kg_m3", "tipo_cemento",
  "adicion_mineral", "agregado_tmn_mm", "lat", "lon", "temperatura_c", "humedad_relativa_pct", "regimen_exposicion"];

function iniciarAportes() {
  const form = $<HTMLFormElement>("#form-aporte");
  const salida = $<HTMLTextAreaElement>("#csv-aporte");
  const estado = $("#estado-aporte");
  const conApi = fuente.modo === "api";
  $("#clave-fila").hidden = !conApi;
  $<HTMLButtonElement>("#enviar").textContent = conApi ? "Enviar a la API" : "Generar fila CSV";
  form.addEventListener("submit", async (ev) => {
    ev.preventDefault();
    const datos = new FormData(form);
    const fila = COLUMNAS.map((c) => {
      const v = String(datos.get(c) ?? "").trim();
      return /[",\n]/.test(v) ? `"${v.replace(/"/g, '""')}"` : v;
    });
    const csv = `${COLUMNAS.join(",")}\n${fila.join(",")}\n`;
    salida.value = csv;
    salida.hidden = false;
    if (conApi && fuente.enviarAportes) {
      try {
        const r = await fuente.enviarAportes(csv, String(datos.get("clave") ?? ""));
        estado.textContent = r.error ? `No se envió: ${r.error}` :
          r.aceptadas ? `Aceptada. ${r.siguiente_paso}.` : `Rechazada: ${r.rechazadas?.[0]?.motivos?.join("; ")}`;
      } catch (e) {
        estado.textContent = `No se pudo conectar con la API: ${(e as Error).message}`;
      }
    } else {
      estado.textContent = "Fila lista. Cópiala y agrégala a un CSV con esta cabecera, o envíala a la API cuando esté en línea.";
    }
  });
  $<HTMLButtonElement>("#copiar").addEventListener("click", async () => {
    try { await navigator.clipboard.writeText(salida.value); estado.textContent = "Copiado."; }
    catch { salida.select(); estado.textContent = "Selecciona el texto y cópialo."; }
  });
}

iniciar().catch((e) => {
  $("#detalle").innerHTML = `<p class="error">No se pudo cargar el atlas: ${String((e as Error).message)}</p>`;
});
