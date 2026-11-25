import { crearFuente } from "./api";
import { CAPAS, AGENTES, clase, type Capa } from "./capas";
import { htmlZona, HORIZONTE, recetaEnPalabras, TIPOS, VIDA_DISENO, veredicto, vista, type EstadoFicha, type Modo, type Tipo } from "./nodos";
import { crearVisor, type Visor } from "./visor";
import { crearGlobo } from "./globo";
import { crearHud } from "./hud";
import { crearRecorrido } from "./recorrido";
import { crearMapa } from "./mapa";
import { crearMaqueta, type Maqueta } from "./maqueta3d";
import { iniciarLuz } from "./luz";
import { iniciarPortada } from "./portada";
import type { PropsZona, Zona } from "./tipos";

const $ = <T extends HTMLElement = HTMLElement>(s: string, r: ParentNode = document) => r.querySelector<T>(s)!;
const fuente = crearFuente();
const n0 = (x: number) => Math.round(x).toLocaleString("es-PE");
const sinTildes = (s: string) => s.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();
const guardar = (k: string, v: string) => { try { localStorage.setItem(k, v); } catch { /* sin almacenamiento */ } };
const leer = (k: string) => { try { return localStorage.getItem(k); } catch { return null; } };

// ---------------- tema: oscuro por defecto (mapa de cobertura), el visitante puede cambiarlo ----------------
function ponerTema(t: string) { document.documentElement.dataset.theme = t; guardar("atlas-tema", t); }
ponerTema(leer("atlas-tema") ?? "dark");

const movil = matchMedia("(max-width: 760px)");
function marcarMovil() { document.body.classList.toggle("movil", movil.matches); }
marcarMovil();
movil.addEventListener("change", marcarMovil);

async function iniciar() {
  const col = await fuente.zonas();
  const props = col.features.map((f) => f.properties);
  const porId = new Map(props.map((p) => [p.id, p]));
  // portada: se muestra al entrar, salvo enlace directo a una zona
  const portada = $("#portada");
  $("#pc-zonas").textContent = props.length.toLocaleString("es-PE");
  $("#pc-ensayos").textContent = (col.metadata.n_ensayos ?? 0).toLocaleString("es-PE");
  $("#pc-clima").textContent = String(col.metadata.celdas_era5 ?? "—");
  const conEnlace = location.hash.length > 1;
  if (conEnlace) portada.hidden = true;
  else { portada.focus({ preventScroll: true }); }
  // globo de entrada (Meridian Earth): la costa encendida con los centroides de las celdas
  const globo = conEnlace ? null : crearGlobo($<HTMLCanvasElement>("#portada-globo"),
    props.filter((_, i) => i % 3 === 0).map((p) => [p.lat, p.lon] as [number, number]));
  let alEntrarMapa = () => {};
  iniciarPortada(portada, () => { alEntrarMapa(); $<HTMLInputElement>("#buscar").focus({ preventScroll: true }); },
    async () => { await globo?.centrarPeru(); });
  $("#volver-portada").addEventListener("click", () => { portada.classList.remove("saliendo"); portada.hidden = false; portada.focus(); });

  const m = await crearMapa($("#mapa"), col);
  document.body.classList.add("listo");
  const hud = crearHud(m.mapa, props);
  m.alPasar((p) => hud.celda(p));
  // al salir de la portada el mapa entra desde el globo: de zoom 5 a la costa
  alEntrarMapa = () => {
    if (matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    m.mapa.setView([-10, -76], 5, { animate: false });
    m.encuadrar([[-18.4, -81.4], [-3.4, -70.2]]);
  };
  iniciarLuz();
  $("#btn-tema").addEventListener("click", () => {
    ponerTema(document.documentElement.dataset.theme === "dark" ? "light" : "dark");
    m.repintarTema();
  });

  // ---------------- capas: menú "Ver" agrupado + leyenda con histograma ----------------
  const ORDEN = ["regimen", ...CAPAS.map((c) => c.id).filter((i) => i !== "regimen")];
  let capa: Capa = CAPAS.find((c) => c.id === leer("atlas-capa")) ?? CAPAS.find((c) => c.id === "regimen")!;
  let filtro: number | null = null;
  const btnCapa = $<HTMLButtonElement>("#btn-capa"), menu = $("#menu-capas");
  const grupos = ["Ambiente", "Concreto", "Personas"];
  menu.innerHTML = grupos.map((g) => `<div class="menu-grupo" role="group" aria-label="${g}"><p>${g}</p>${ORDEN.map((id) => CAPAS.find((c) => c.id === id)!)
    .filter((c) => c.grupo === g).map((c) => `<button type="button" role="menuitemradio" data-capa="${c.id}" aria-checked="${c.id === capa.id}">${c.nombre}</button>`).join("")}</div>`).join("");
  function abrirMenu(si: boolean) { menu.hidden = !si; btnCapa.setAttribute("aria-expanded", String(si)); if (si) menu.querySelector<HTMLElement>("[aria-checked='true']")?.focus(); }
  btnCapa.addEventListener("click", () => abrirMenu(menu.hidden));
  document.addEventListener("click", (e) => { if (!menu.hidden && !(e.target as HTMLElement).closest("#menu-capas, #btn-capa")) abrirMenu(false); });
  menu.addEventListener("keydown", (e) => { if (e.key === "Escape") { abrirMenu(false); btnCapa.focus(); } });
  function elegirCapa(id: string, recordar = true) {
    capa = CAPAS.find((c) => c.id === id) ?? capa;
    if (recordar) guardar("atlas-capa", capa.id);
    menu.querySelectorAll<HTMLElement>("[data-capa]").forEach((x) => x.setAttribute("aria-checked", String(x.dataset.capa === capa.id)));
    filtro = null;
    m.ponerCapa(capa);
    leyenda();
  }
  menu.addEventListener("click", (e) => {
    const b = (e.target as HTMLElement).closest<HTMLButtonElement>("[data-capa]");
    if (!b) return;
    abrirMenu(false);
    elegirCapa(b.dataset.capa!);
  });
  function leyenda() {
    btnCapa.querySelector("span")!.textContent = capa.nombre;
    const cuenta = capa.colores.map(() => 0);
    props.forEach((p) => cuenta[clase(capa, capa.valor(p))]++);
    const max = Math.max(...cuenta);
    $("#leyenda-titulo").textContent = capa.pregunta;
    $("#leyenda-lista").innerHTML = capa.colores.map((c, i) => cuenta[i] ? `<li><button type="button" data-clase="${i}" aria-pressed="${filtro === i}">
      <span class="muestra" style="background:${c}"></span><span class="ley-txt">${capa.etiquetas[i]}</span>
      <span class="ley-hist"><span style="--p:${(cuenta[i] / max * 100).toFixed(0)}%;background:${c}"></span></span><span class="ley-n">${cuenta[i]}</span></button></li>` : "").join("");
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
    if (!prev || p.anillo < prev.anillo) indice.set(k, p);
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

  // ---------------- ficha de zona en nodos ----------------
  let maqueta: Maqueta | null = null;
  let visor: Visor | null = null;
  let actual: PropsZona | null = null;
  const est: EstadoFicha = { modo: "interior", tipo: "ideal", abierto: null };
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
    est.abierto = null;
    est.modo = actual.frente_marino && actual.frente && actual.clase_urbana !== "deshabitado" ? "frente" : "interior";
    pintarFicha();
    cont.removeAttribute("aria-busy");
    $(".hoja-scroll").scrollTop = 0;
    const t = await fuente.terreno(id, ligera.detalle!);
    if (actual?.id !== id) return;
    const canvas = $<HTMLCanvasElement>("#maqueta", cont);
    maqueta?.destruir();
    maqueta = t ? crearMaqueta(canvas) : null;
    if (maqueta && t) maqueta.mostrar(t);
    else { $(".maqueta-sin", cont).hidden = false; canvas.hidden = true; }
  }

  /** Repinta solo la vía de nodos (la maqueta 3D se conserva). */
  function pintarFicha(soloVia = false) {
    if (!actual) return;
    const html = htmlZona(actual, est);
    if (soloVia && cont.querySelector(".via")) {
      const tmp = document.createElement("div");
      tmp.innerHTML = html;
      cont.querySelector(".via")!.replaceWith(tmp.querySelector(".via")!);
      cont.querySelector(".etiqueta-reg")!.replaceWith(tmp.querySelector(".etiqueta-reg")!);
      const modo = tmp.querySelector(".modo");
      if (modo) cont.querySelector(".modo")?.replaceWith(modo);
    } else cont.innerHTML = html;
    $("[data-comparar]", cont).setAttribute("aria-pressed", String(fijadas.includes(actual.id)));
    montarVisor();
  }
  function montarVisor() {
    visor?.destruir(); visor = null;
    const el = cont.querySelector<HTMLElement>("#visor");
    if (!el || !actual || est.abierto !== "tiempo") return;
    const v = vista(actual, est.modo), r = v.recetas[est.tipo];
    if (!v.fick_comun || !r.fick) { el.innerHTML = `<p class="nota">Este cálculo necesita datos regenerados del atlas.</p>`; return; }
    visor = crearVisor(el, { f: v.fick_comun, d: v.comun! }, { f: r.fick, d: r.durabilidad }, TIPOS.find(([k]) => k === est.tipo)![1], HORIZONTE, VIDA_DISENO);
  }

  cont.addEventListener("click", async (e) => {
    const t = e.target as HTMLElement;
    const cab = t.closest<HTMLElement>(".nodo-cab");
    if (cab) {
      const id = cab.closest<HTMLElement>("[data-nodo]")!.dataset.nodo!;
      est.abierto = est.abierto === id ? null : id;
      cont.querySelectorAll<HTMLElement>("[data-nodo]").forEach((n) => {
        const on = n.dataset.nodo === est.abierto;
        n.classList.toggle("abierto", on);
        n.querySelector(".nodo-cab")!.setAttribute("aria-expanded", String(on));
        (n.querySelector(".nodo-cuerpo") as HTMLElement).hidden = !on;
      });
      montarVisor();
      if (est.abierto) requestAnimationFrame(() => cab.scrollIntoView({ block: "nearest", behavior: "smooth" }));
      return;
    }
    const tar = t.closest<HTMLElement>("[data-tipo]");
    if (tar && actual) { est.tipo = tar.dataset.tipo as Tipo; pintarFicha(true); return; }
    const modo = t.closest<HTMLElement>("[data-modo]");
    if (modo && actual) { est.modo = modo.dataset.modo as Modo; pintarFicha(true); return; }
    const info = t.closest<HTMLElement>("[data-info]");
    if (info) { const p = info.parentElement!.nextElementSibling as HTMLElement; p.hidden = !p.hidden; info.setAttribute("aria-expanded", String(!p.hidden)); return; }
    if (t.closest("[data-cerrar]")) { hoja.classList.remove("con-zona"); ponerHoja("asomada"); m.seleccionar(null); actual = null; maqueta?.destruir(); maqueta = null; visor?.destruir(); return; }
    if (t.closest("[data-girar]")) return maqueta?.girar();
    if (t.closest("[data-soplar]")) { const b = t.closest("[data-soplar]")!; b.setAttribute("aria-pressed", String(b.getAttribute("aria-pressed") !== "true")); return maqueta?.soplar(); }
    if (t.closest("[data-comparar]") && actual) return alternarComparacion(actual.id);
    if (t.closest("[data-copiar]") && actual) {
      const r = vista(actual, est.modo).recetas[est.tipo], d = r.dosificacion;
      const txt = `${actual.distrito} (${actual.id}) · ${recetaEnPalabras(r)}\nCemento ${d.cemento_tipo}\t${d.cemento_kg} kg\nAgua\t${d.agua_kg} kg\nArena\t${d.arena_kg} kg\nPiedra\t${d.piedra_kg} kg\nSuperplastificante\t${d.superplastificante_kg} kg\nCristalizante\t${d.cristalino_kg} kg\nAgente\t${d.agente_kg} kg`;
      try { await navigator.clipboard.writeText(txt); aviso("Dosificación copiada"); } catch { aviso("No se pudo copiar: selecciona la tabla y cópiala"); }
    }
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
      ${fila("Concreto común", (p) => veredicto(p.durabilidad_comun).txt)}
      ${fila("Receta ideal", (p) => recetaEnPalabras(p.recetas!.ideal))}
      ${fila("Vida útil con la receta", (p) => veredicto(p.recetas!.ideal.durabilidad).txt)}
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
  $("#modelo").textContent = `${props.length.toLocaleString("es-PE")} celdas hexagonales de 10 km entre Tumbes y Tacna. Modelo v${col.metadata.modelo_version}, entrenado con ${col.metadata.cv_modelo ? "los ensayos de Blur" : "Blur"}: acierta el cierre de fisura con un error medio de ±${String(col.metadata.cv_modelo?.conjunto?.MAE_pct ?? "").replace(".", ",")} puntos.`;

  const inicial = location.hash.slice(1);
  if (inicial && porId.has(inicial)) abrir(inicial, true);
  else if (!movil.matches) abrir(props.filter((p) => p.distrito === "Atiquipa").sort((a, b) => b.frac_loma - a.frac_loma)[0]?.id ?? props[0].id, false);

  // ---------------- recorrido Tumbes → Tacna (ECLIPSE) ----------------
  const capaAntes = () => capa.id;
  let volverA = capaAntes();
  const rec = crearRecorrido($("#recorrido"), props, {
    encuadrar: (b) => m.encuadrar(b),
    ponerCapa: (id) => elegirCapa(id, false),
    abrir: (id) => abrir(id),
    alCerrar: () => { elegirCapa(volverA, false); $("#btn-recorrido").focus(); },
  });
  $("#btn-recorrido").addEventListener("click", () => {
    volverA = capaAntes();
    hoja.classList.remove("con-zona"); ponerHoja("asomada");
    rec.abrir();
  });

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
