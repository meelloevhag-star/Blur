import type { PropsZona } from "./tipos";

export interface Capa {
  id: string; nombre: string; leyenda: string; unidad: string;
  valor(p: PropsZona): number; cortes: number[]; colores: string[]; etiquetas?: string[];
}

// Rampas legibles en ambos temas (validadas sobre el fondo marino del mapa).
const VIDA = ["#b5482f", "#d98a3d", "#e8c15a", "#8fbf7a", "#3f8f7a"];
const COSTO = ["#3f8f7a", "#8fbf7a", "#e8c15a", "#d98a3d", "#b5482f"];
const NIEBLA = ["#e9edf0", "#c3d3dc", "#8fb0c2", "#5b88a3", "#2f5f7e"];

const ORDEN_REG = ["salpicadura", "niebla_salina", "niebla_orografica", "atmosferico_marino", "seco"];
const RELIEVE = ["#e9e4d4", "#cdbf98", "#a8946a", "#7d6a4a", "#4f4231"];
const URBANO = ["#f1ede6", "#d8c3a5", "#c08b5c", "#97502f", "#5f2a1c"];

export const CAPAS: Capa[] = [
  { id: "regimen", nombre: "Régimen de exposición", leyenda: "Cómo llega el cloruro al concreto en cada franja",
    unidad: "", valor: (p) => ORDEN_REG.indexOf(p.regimen), cortes: [1, 2, 3, 4],
    colores: ["#2f5f7e", "#5b88a3", "#3f8f7a", "#8fb0c2", "#d9c9a8"],
    etiquetas: ["Mareas y salpicadura (XS3)", "Niebla salina / garúa (XS2)", "Niebla orográfica · lomas y cerros (XS2)",
      "Atmosférico marino (XS1)", "Costa seca (XC)"] },
  { id: "prioridad", nombre: "Prioridad · población expuesta",
    leyenda: "Personas que viven donde el concreto común se deteriora antes: dónde rinde más el autorreparable",
    unidad: "personas", valor: (p) => p.prioridad, cortes: [1000, 10000, 50000, 200000], colores: URBANO },
  { id: "urbano", nombre: "Población y zonas urbanas", leyenda: "Grado de urbanización (ONU-Eurostat) con WorldPop 2022 (Censo 2017)",
    unidad: "", valor: (p) => ["deshabitado", "rural", "periurbano", "urbano"].indexOf(p.clase_urbana), cortes: [1, 2, 3],
    colores: ["#f1ede6", "#d8c3a5", "#c08b5c", "#5f2a1c"],
    etiquetas: ["Deshabitado (< 25 hab/km²)", "Rural (25–300)", "Periurbano (300–1 500)", "Urbano (≥ 1 500 hab/km²)"] },
  { id: "relieve", nombre: "Relieve · elevación", leyenda: "Elevación media de la zona (Copernicus DEM 90 m)",
    unidad: "m", valor: (p) => p.elevacion_media_m ?? 0, cortes: [50, 200, 500, 1000], colores: RELIEVE },
  { id: "cloruros", nombre: "Cloruros en el aire", leyenda: "Deposición estimada de cloruros (mg/m²·día, clases ISO 9223)",
    unidad: "mg/m²·d", valor: (p) => p.deposicion_cl_mg_m2_d, cortes: [3, 15, 60, 300], colores: NIEBLA },
  { id: "ganancia", nombre: "Mezcla ideal · años que gana la autorreparación",
    leyenda: "Vida útil de la receta ideal menos la misma mezcla con la fisura sin sellar",
    unidad: "años", valor: (p) => p.ganancia_autorreparacion_anios, cortes: [10, 30, 60, 100], colores: VIDA },
  { id: "cierre", nombre: "Mezcla ideal · cierre de fisura", leyenda: "Cierre predicho a 90 días de una fisura de 0,3 mm",
    unidad: "%", valor: (p) => p.ideal_cierre_pct, cortes: [40, 50, 60, 70], colores: VIDA },
  { id: "costo", nombre: "Viabilidad · costo", leyenda: "Costo por m³ de la receta más económica que llega a 50 años",
    unidad: "S/ por m³", valor: (p) => p.economica_costo_m3, cortes: [500, 520, 540, 560], colores: COSTO },
  { id: "disponibilidad", nombre: "Viabilidad · disponibilidad", leyenda: "Facilidad de conseguir los insumos de la receta ideal (0–1)",
    unidad: "", valor: (p) => p.ideal_disponibilidad, cortes: [0.1, 0.12, 0.15, 0.2], colores: [...VIDA] },
  { id: "niebla", nombre: "Niebla · garúa y niebla orográfica", leyenda: "Índice de niebla (ERA5 + laderas al mar entre 300 y 1 000 m), 0–1",
    unidad: "", valor: (p) => p.indice_niebla, cortes: [0.2, 0.35, 0.5, 0.65], colores: NIEBLA },
];

export const REGIMENES: Record<string, { nombre: string; color: string; corto: string }> = {
  salpicadura: { nombre: "Mareas y salpicadura", corto: "Salpicadura", color: "#2f5f7e" },
  niebla_salina: { nombre: "Niebla salina / garúa", corto: "Niebla salina", color: "#5b88a3" },
  niebla_orografica: { nombre: "Niebla orográfica (lomas y cerros)", corto: "Loma / cerro con niebla", color: "#3f8f7a" },
  atmosferico_marino: { nombre: "Atmosférico marino", corto: "Atmosférico", color: "#8fb0c2" },
  seco: { nombre: "Costa seca", corto: "Seco", color: "#d9c9a8" },
};

export function color(capa: Capa, v: number): string {
  let i = 0;
  while (i < capa.cortes.length && v >= capa.cortes[i]) i++;
  return capa.colores[i];
}

export function etiquetasLeyenda(capa: Capa): string[] {
  if (capa.etiquetas) return capa.etiquetas;
  const f = (x: number) => (capa.unidad === "" ? x.toFixed(2) : String(x));
  const c = capa.cortes;
  return [`< ${f(c[0])}`, ...c.slice(0, -1).map((x, i) => `${f(x)}–${f(c[i + 1])}`), `≥ ${f(c[c.length - 1])}`];
}
