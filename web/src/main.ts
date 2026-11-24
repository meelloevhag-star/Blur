import { crearFuente } from "./api";
import { CAPAS, AGENTES, clase, type Capa } from "./capas";
import { htmlFicha, htmlPerfil, htmlReceta, recetaEnPalabras, TIPOS } from "./ficha";
import { crearMapa } from "./mapa";
import { crearMaqueta, type Maqueta } from "./maqueta3d";
import type { PropsZona, Zona } from "./tipos";

const $ = <T extends HTMLElement = HTMLElement>(s: string, r: ParentNode = document) => r.querySelector<T>(s)!;
const fuente = crearFuente();
const n0 = (x: number) => Math.round(x).toLocaleString("es-PE");
const sinTildes = (s: string) => s.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();
const guardar = (k: string, v: string) => { try { localStorage.setItem(k, v); } catch { /* sin almacenamiento */ } };
const leer = (k: string) => { try { return localStorage.getItem(k); } catch { return null; } };

const movil = matchMedia("(max-width: 760px)");
function marcarMovil() { document.body.classList.toggle("movil", movil.matches); }
marcarMovil();
movil.addEventListener("change", marcarMovil);

async function iniciar() {
  const col = await fuente.zonas();
  const props = col.features.map((f) => f.properties);
  const porId = new Map(props.map((p) => [p.id, p]));
  const m = await crearMapa($("#mapa"), col);
  document.body.classList.add("listo");

  // ---------------- capas (chips) + leyenda ----------------
  let capa: Capa = CAPAS.find((c) => c.id === leer("atlas-capa")) ?? CAPAS[0];
  let filtro: number | null = null;
  const chips = $("#chips");
  chips.innerHTML = CAPAS.map((c) => `<button type="button" role="radio" class="chip" data-capa="${c.id}" aria-checked="${c.id === capa.id}">${c.nombre}</button>`).join("");
  chips.addEventListener("click", (e) => {
    const b = (e.target as HTMLElement).closest<HTMLButtonElement>("[data-capa]");
    if (!b) return;
    capa = CAPAS.find((c) => c.id === b.dataset.capa)!;
    guardar("atlas-capa", capa.id);
    chips.querySelectorAll("[data-capa]").forEach((x) => x.setAttribute("aria-checked", String(x === b)));
    b.scrollIntoView({ inline: "center", block: "nearest", behavior: "smooth" });
    filtro = null;
    m.ponerCapa(capa);
    leyenda();
  });
  function leyenda() {
    const cuenta = capa.colores.map(() => 0);
    props.forEach((p) => cuenta[clase(capa, capa.valor(p))]++);
    $("#leyenda-titulo").textContent = capa.pregunta;
    $("#leyenda-lista").innerHTML = capa.colores.map((c, i) => cuenta[i] ? `<li><button type="button" data-clase="${i}" aria-pressed="${filtro === i}">
      <span class="muestra" style="background:${c}"></span><span class="ley-txt">${capa.etiquetas[i]}</span><span class="ley-n">${cuenta[i]}</span></button></li>` : "").join("");
  }
  $("#leyenda-lista").addEventListener("click", (e) => {
    const b = (e.target as HTMLElement).closest<HTMLButtonElement>("[data-clase]");
    if (!b) return;
    const i = Number(b.dataset.clase);
    filtro = filtro === i ? null : i;
    m.filtrarClase(filtro);
    leyenda();
  });
  m.ponerCapa(capa);
  leyenda();
  $("#btn-leyenda").addEventListener("click", () => {
    const l = $("#leyenda");
    const abierta = l.classList.toggle("abierta");
    $("#btn-leyenda").setAttribute("aria-expanded", String(abierta));
  });

  // ---------------- buscador ----------------
  const indice = new Map<string, PropsZona>();
  props.forEach((p) => {
    const k = `${p.distrito}|${p.provincia}`;
    const prev = indice.get(k);
    if (!prev || p.franja < prev.franja) indice.set(k, p);
  });
  const entradas = [...indice.values()].map((p) => ({ p, k: sinTildes(`${p.distrito} ${p.provincia} ${p.departamento}`) }));
  const input = $<HTMLInputElement>("#buscar"), lista = $("#resultados");
  let activos: PropsZona[] = [], cursor = -1;
  function pintarResultados() {
    lista.innerHTML = activos.map((p, i) => `<li role="option" id="res-${i}" aria-selected="${i === cursor}" data-zona="${p.id}">
      <strong>${p.distrito}</strong><span>${p.provincia}, ${p.departamento}</span></li>`).join("")
      || (input.value.trim() ? `<li class="vacio">No hay distritos costeros con ese nombre.</li>` : "");
    lista.hidden = !input.value.trim();
    input.setAttribute("aria-expanded", String(!lista.hidden));
    input.setAttribute("aria-activedescendant", cursor >= 0 ? `res-${cursor}` : "");
  }
  input.addEventListener("input", () => {
    const q = sinTildes(input.value.trim());
    activos = q ? entradas.filter((e) => e.k.includes(q)).sort((a, b) => Number(!a.k.startsWith(q)) - Number(!b.k.startsWith(q))).slice(0, 7).map((e) => e.p) : [];
    cursor = activos.length ? 0 : -1;
    pintarResultados();
  });
  input.addEventListener("keydown", (e) => {
    if (e.key === "ArrowDown") { cursor = Math.min(cursor + 1, activos.length - 1); pintarResultados(); e.preventDefault(); }
    else if (e.key === "ArrowUp") { cursor = Math.max(cursor - 1, 0); pintarResultados(); e.preventDefault(); }
    else if (e.key === "Enter" && activos[cursor]) { elegir(activos[cursor]); e.preventDefault(); }
    else if (e.key === "Escape") { input.value = ""; activos = []; pintarResultados(); }
  });
  lista.addEventListener("click", (e) => {
    const li = (e.target as HTMLElement).closest<HTMLElement>("[data-zona]");
    if (li) elegir(porId.get(li.dataset.zona!)!);
  });
  function elegir(p: PropsZona) { input.value = ""; activos = []; pintarResultados(); input.blur(); abrir(p.id); }

  // ---------------- hoja (cajón en escritorio, hoja deslizable en móvil) ----------------
  const hoja = $("#hoja"), cont = $("#ficha");
  let estadoHoja: "asomada" | "media" | "completa" = "media";
  function ponerHoja(e: typeof estadoHoja) { estadoHoja = e; hoja.dataset.estado = e; }
  ponerHoja("asomada");
  let y0 = 0, alto0 = 0, arrastrando = false;
  const asa = $("#asa");
  asa.addEventListener("pointerdown", (e) => { arrastrando = true; y0 = e.clientY; alto0 = hoja.getBoundingClientRect().height; asa.setPointerCapture(e.pointerId); hoja.classList.add("arrastrando"); });
  asa.addEventListener("pointermove", (e) => { if (arrastrando) hoja.style.height = `${Math.max(96, Math.min(innerHeight * 0.94, alto0 + (y0 - e.clientY)))}px`; });
  asa.addEventListener("pointerup", (e) => {
    if (!arrastrando) return;
    arrastrando = false; hoja.classList.remove("arrastrando");
    const h = hoja.getBoundingClientRect().height / innerHeight;
    hoja.style.height = "";
    if (Math.abs(e.clientY - y0) < 6) ponerHoja(estadoHoja === "asomada" ? "media" : estadoHoja === "media" ? "completa" : "asomada");
    else ponerHoja(h > 0.72 ? "completa" : h > 0.3 ? "media" : "asomada");
  });
  asa.addEventListener("keydown", (e) => {
    if (e.key === "ArrowUp") ponerHoja(estadoHoja === "asomada" ? "media" : "completa");
    if (e.key === "ArrowDown") ponerHoja(estadoHoja === "completa" ? "media" : "asomada");
  });

  // ---------------- ficha de zona ----------------
  let maqueta: Maqueta | null = null;
  let actual: PropsZona | null = null, tipo = "ideal";
  const fijadas: string[] = [];

  async function abrir(id: string, volar = true) {
    const ligera = porId.get(id);
    if (!ligera) return;
    m.seleccionar(id, volar);
    try { history.replaceState(null, "", `#${id}`); } catch { /* sin historial */ }
    hoja.classList.add("con-zona");
    if (estadoHoja === "asomada") ponerHoja("media");
    cont.setAttribute("aria-busy", "true");
    const z: Zona = await fuente.zona(id, ligera.detalle!);
    actual = { ...ligera, ...z.properties };
    pintarFicha();
    cont.removeAttribute("aria-busy");
    const t = await fuente.terreno(ligera.tramo, ligera.detalle!);
    if (actual?.id !== id) return;
    const canvas = $<HTMLCanvasElement>("#maqueta", cont);
    maqueta?.destruir();
    maqueta = t ? crearMaqueta(canvas) : null;
    if (maqueta && t) maqueta.mostrar(t, actual.franja);
    else { $(".maqueta-sin", cont).hidden = false; canvas.hidden = true; }
  }

  function pintarFicha() {
    if (!actual) return;
    cont.innerHTML = htmlFicha(actual, tipo);
    const delTramo = props.filter((p) => p.tramo === actual!.tramo);
    $("#perfil", cont).innerHTML = htmlPerfil(delTramo, actual.id);
    $("[data-comparar]", cont).setAttribute("aria-pressed", String(fijadas.includes(actual.id)));
    $(".hoja-scroll").scrollTop = 0;
  }

  cont.addEventListener("click", async (e) => {
    const t = e.target as HTMLElement;
    const seg = t.closest<HTMLButtonElement>("[data-tipo]");
    if (seg && actual) {
      tipo = seg.dataset.tipo!;
      cont.querySelectorAll("[data-tipo]").forEach((b) => b.setAttribute("aria-selected", String(b === seg)));
      $(".receta", cont).innerHTML = htmlReceta((actual.recetas as any)[tipo], actual);
      return;
    }
    const fr = t.closest<HTMLElement>("[data-zona]");
    if (fr) return abrir(fr.dataset.zona!, true);
    if (t.closest("[data-cerrar]")) { hoja.classList.remove("con-zona"); ponerHoja("asomada"); m.seleccionar(null); actual = null; maqueta?.destruir(); maqueta = null; return; }
    if (t.closest("[data-girar]")) return maqueta?.girar();
    if (t.closest("[data-soplar]")) { const b = t.closest("[data-soplar]")!; b.setAttribute("aria-pressed", String(b.getAttribute("aria-pressed") !== "true")); return maqueta?.soplar(); }
    if (t.closest("[data-comparar]") && actual) return alternarComparacion(actual.id);
    if (t.closest("[data-copiar]") && actual) {
      const r = (actual.recetas as any)[tipo], d = r.dosificacion;
      const txt = `${actual.distrito} (${actual.id}) · ${recetaEnPalabras(r)}\nCemento ${d.cemento_tipo}\t${d.cemento_kg} kg\nAgua\t${d.agua_kg} kg\nArena\t${d.arena_kg} kg\nPiedra\t${d.piedra_kg} kg\nSuperplastificante\t${d.superplastificante_kg} kg\nCristalizante\t${d.cristalino_kg} kg\nAgente\t${d.agente_kg} kg`;
      try { await navigator.clipboard.writeText(txt); aviso("Dosificación copiada"); } catch { aviso("No se pudo copiar: selecciona la tabla y cópiala"); }
    }
  });
  cont.addEventListener("keydown", (e) => {
    const fr = (e.target as HTMLElement).closest<HTMLElement>("[data-zona]");
    if (fr && (e.key === "Enter" || e.key === " ")) { e.preventDefault(); abrir(fr.dataset.zona!); }
  });
  m.alSeleccionar((p) => abrir(p.id));

  // ---------------- comparar ----------------
  function alternarComparacion(id: string) {
    const i = fijadas.indexOf(id);
    if (i >= 0) fijadas.splice(i, 1);
    else { if (fijadas.length >= 3) fijadas.shift(); fijadas.push(id); }
    $("[data-comparar]", cont)?.setAttribute("aria-pressed", String(fijadas.includes(id)));
    pintarBandeja();
  }
  function pintarBandeja() {
    const b = $("#bandeja");
    b.hidden = fijadas.length === 0;
    $("#bandeja-zonas").innerHTML = fijadas.map((id) => `<li><button type="button" data-ir="${id}">${porId.get(id)!.distrito}</button>
      <button type="button" class="quitar" data-quitar="${id}" aria-label="Quitar ${porId.get(id)!.distrito}">✕</button></li>`).join("");
    $<HTMLButtonElement>("#btn-comparar").disabled = fijadas.length < 2;
  }
  $("#bandeja").addEventListener("click", (e) => {
    const t = e.target as HTMLElement;
    const q = t.closest<HTMLElement>("[data-quitar]");
    if (q) return alternarComparacion(q.dataset.quitar!);
    const ir = t.closest<HTMLElement>("[data-ir]");
    if (ir) return abrir(ir.dataset.ir!);
    if (t.closest("#btn-comparar")) mostrarComparacion();
  });
  async function mostrarComparacion() {
    const zs = await Promise.all(fijadas.map(async (id) => ({ ...porId.get(id)!, ...(await fuente.zona(id, porId.get(id)!.detalle!)).properties })));
    const fila = (et: string, f: (p: PropsZona) => string) => `<tr><th scope="row">${et}</th>${zs.map((p) => `<td>${f(p)}</td>`).join("")}</tr>`;
    $("#tabla-comparar").innerHTML = `<thead><tr><th></th>${zs.map((p) => `<th scope="col">${p.distrito}<small>${p.provincia}</small></th>`).join("")}</tr></thead><tbody>
      ${fila("Exposición", (p) => CAPAS[1].formato(CAPAS[1].valor(p)))}
      ${fila("Neblina", (p) => p.indice_niebla.toFixed(2).replace(".", ","))}
      ${fila("Sal en el aire", (p) => `${n0(p.deposicion_cl_mg_m2_d)} mg/m²·d`)}
      ${fila("Altura media", (p) => `${n0(p.elevacion_media_m ?? 0)} m`)}
      ${fila("Concreto común", (p) => p.vida_util_concreto_comun_anios >= 150 ? "150+ años" : `${n0(p.vida_util_concreto_comun_anios)} años`)}
      ${fila("Receta ideal", (p) => recetaEnPalabras(p.recetas!.ideal))}
      ${fila("Vida útil con la receta", (p) => p.recetas!.ideal.vida_util_anios >= 150 ? "150+ años" : `${n0(p.recetas!.ideal.vida_util_anios)} años`)}
      ${fila("Costo ideal", (p) => `S/ ${n0(p.recetas!.ideal.viabilidad.costo_m3_pen)} por m³`)}
      ${fila("Opción económica", (p) => `S/ ${n0(p.recetas!.economica.viabilidad.costo_m3_pen)}: ${AGENTES[p.recetas!.economica.agente]?.corto}`)}
      ${fila("Población", (p) => `${n0(p.poblacion)} hab.`)}</tbody>`;
    $<HTMLDialogElement>("#dlg-comparar").showModal();
  }
  document.querySelectorAll<HTMLElement>("[data-cerrar-dlg]").forEach((b) => b.addEventListener("click", () => (b.closest("dialog") as HTMLDialogElement).close()));

  // ---------------- atajos de inicio ----------------
  $("#atajos").addEventListener("click", (e) => {
    const b = (e.target as HTMLElement).closest<HTMLElement>("[data-buscar]");
    if (!b) return;
    const q = sinTildes(b.dataset.buscar!);
    const p = entradas.find((x) => x.k.startsWith(q))?.p;
    if (p) abrir(p.id);
  });
  $("#modelo").textContent = `${props.length.toLocaleString("es-PE")} zonas de 10 km entre Tumbes y Tacna. Modelo v${col.metadata.modelo_version}, entrenado con ${col.metadata.cv_modelo ? "los ensayos de Blur" : "Blur"}: acierta el cierre de fisura con un error medio de ±${String(col.metadata.cv_modelo?.conjunto?.MAE_pct ?? "").replace(".", ",")} puntos.`;

  const inicial = location.hash.slice(1);
  if (inicial && porId.has(inicial)) abrir(inicial, true);
  else if (!movil.matches) abrir(props.find((p) => p.distrito === "Atiquipa" && p.franja === 3)?.id ?? props[0].id, false);

  iniciarAportes();
}

let temporizador = 0;
function aviso(t: string) {
  const a = $("#aviso");
  a.textContent = t; a.hidden = false;
  clearTimeout(temporizador);
  temporizador = window.setTimeout(() => (a.hidden = true), 2600);
}

const COLUMNAS = ["autor_aporte", "institucion", "tipo_fuente", "doi_o_url", "norma_ensayo", "fecha_ensayo", "id_probeta",
  "a_c", "nivel_proteccion", "ambiente_marino", "usa_lactato", "curado_previo", "w0_mm", "edad_dias", "wt_mm", "cierre_pct",
  "notas", "portador", "tiene_bacterias", "cepa", "dosis_bacteria", "nutriente", "nutriente_dosis_kg_m3", "tipo_cemento",
  "adicion_mineral", "agregado_tmn_mm", "lat", "lon", "temperatura_c", "humedad_relativa_pct", "regimen_exposicion"];
function iniciarAportes() {
  const dlg = $<HTMLDialogElement>("#dlg-aporte"), form = $<HTMLFormElement>("#form-aporte");
  $("#btn-aportar").addEventListener("click", () => dlg.showModal());
  const salida = $<HTMLTextAreaElement>("#csv-aporte"), estado = $("#estado-aporte");
  $("#clave-fila").hidden = fuente.modo !== "api";
  form.addEventListener("submit", async (ev) => {
    ev.preventDefault();
    const d = new FormData(form);
    const fila = COLUMNAS.map((c) => { const v = String(d.get(c) ?? "").trim(); return /[",\n]/.test(v) ? `"${v.replace(/"/g, '""')}"` : v; });
    const csv = `${COLUMNAS.join(",")}\n${fila.join(",")}\n`;
    salida.value = csv; salida.hidden = false;
    if (fuente.enviarAportes) {
      try {
        const r = await fuente.enviarAportes(csv, String(d.get("clave") ?? ""));
        estado.textContent = r.error ? `No se envió: ${r.error}` : r.aceptadas ? "Ensayo recibido. Entrará al modelo en la próxima actualización." : `Revisa: ${r.rechazadas?.[0]?.motivos?.join("; ")}`;
      } catch (e) { estado.textContent = `No se pudo conectar con el servidor: ${(e as Error).message}`; }
    } else estado.textContent = "Fila lista. Cópiala y súmala a un CSV con esta cabecera para enviarla al proyecto.";
  });
  $("#copiar-aporte").addEventListener("click", async () => {
    try { await navigator.clipboard.writeText(salida.value); estado.textContent = "Fila copiada."; }
    catch { salida.select(); estado.textContent = "Selecciona el texto y cópialo."; }
  });
}

iniciar().catch((e) => {
  $("#ficha").innerHTML = `<p class="error">No se pudo cargar el atlas: ${String((e as Error).message)}. Recarga la página.</p>`;
});
