import type { PropsZona } from "./tipos";

export type Grupo = "Ambiente" | "Concreto" | "Personas";
export interface Capa {
  id: string; nombre: string; pregunta: string; unidad?: string; grupo: Grupo;
  valor(p: PropsZona): number;
  cortes: number[]; colores: string[]; etiquetas: string[];
  formato(v: number): string;
}

const n0 = (v: number) => Math.round(v).toLocaleString("es-PE");
const rangos = (c: number[], u: string, f = n0) =>
  [`menos de ${f(c[0])} ${u}`, ...c.slice(0, -1).map((x, i) => `${f(x)} a ${f(c[i + 1])} ${u}`), `${f(c[c.length - 1])} ${u} o más`];

export const AGENTES: Record<string, { nombre: string; corto: string; color: string }> = {
  basilisk: { nombre: "Agente bacteriano comercial en granulado", corto: "Bacteriano comercial", color: "#0e7a63" },
  lwa_bacterias: { nombre: "Bacterias en arcilla expandida con lactato", corto: "Bacterias en arcilla", color: "#6aa84f" },
  hidrogel_bacterias: { nombre: "Bacterias encapsuladas en hidrogel", corto: "Bacterias en hidrogel", color: "#9cc5a1" },
  cristalino: { nombre: "Aditivo cristalizante", corto: "Cristalizante", color: "#3b6f8f" },
  consorcio_agricola: { nombre: "Consorcio agrícola con lactato", corto: "Consorcio agrícola", color: "#b08a3e" },
  ninguno: { nombre: "Sin agente", corto: "Sin agente", color: "#9aa3a0" },
};
const ORDEN_AG = ["basilisk", "lwa_bacterias", "cristalino", "hidrogel_bacterias", "consorcio_agricola"];

export const REGIMENES: Record<string, { nombre: string; explicacion: string; color: string }> = {
  salpicadura: { nombre: "Primera línea de mar", color: "#1f4e6b",
    explicacion: "Olas, mareas y salpicadura llevan sal directo al concreto." },
  niebla_salina: { nombre: "Niebla salina", color: "#4f86a6",
    explicacion: "La garúa moja el concreto y deja sal del mar varias veces por semana." },
  niebla_orografica: { nombre: "Loma o cerro con neblina", color: "#2f8a6e",
    explicacion: "Ladera que mira al mar dentro de la franja de nubes (300–1 000 m): neblina buena parte del año." },
  atmosferico_marino: { nombre: "Brisa marina", color: "#92b4c4",
    explicacion: "El viento trae algo de sal, pero la superficie pasa más tiempo seca." },
  seco: { nombre: "Costa seca", color: "#d8c8a4", explicacion: "Lejos del mar o detrás de cerros: poca sal y poca humedad." },
};
const ORDEN_REG = ["salpicadura", "niebla_salina", "niebla_orografica", "atmosferico_marino", "seco"];
const URB = ["deshabitado", "rural", "periurbano", "urbano"];

const SEC = ["#e6efe9", "#b9d6c6", "#7fb39b", "#3f8a6e", "#145c46"];        // verde loma
const AZUL = ["#e5eef2", "#b5cfdb", "#7eaac0", "#467f9e", "#1f4e6b"];       // sal
const TIERRA = ["#efe7d4", "#d9c39a", "#b99868", "#8c6b44", "#5a4329"];     // relieve
const CALOR = ["#f3e6d6", "#e9bf93", "#d48b5b", "#ae5634", "#6e2c1c"];      // urgencia / costo

export const CAPAS: Capa[] = [
  { id: "receta", grupo: "Concreto", nombre: "Qué concreto usar", pregunta: "Agente autorreparador de la receta ideal",
    valor: (p) => ORDEN_AG.indexOf(p.ideal_agente), cortes: [1, 2, 3, 4],
    colores: ORDEN_AG.map((a) => AGENTES[a].color), etiquetas: ORDEN_AG.map((a) => AGENTES[a].corto),
    formato: (v) => AGENTES[ORDEN_AG[v]]?.corto ?? "—" },
  { id: "regimen", grupo: "Ambiente", nombre: "Exposición", pregunta: "Cómo le llega la sal al concreto",
    valor: (p) => ORDEN_REG.indexOf(p.regimen), cortes: [1, 2, 3, 4],
    colores: ORDEN_REG.map((r) => REGIMENES[r].color), etiquetas: ORDEN_REG.map((r) => REGIMENES[r].nombre),
    formato: (v) => REGIMENES[ORDEN_REG[v]]?.nombre ?? "—" },
  { id: "niebla", grupo: "Ambiente", nombre: "Neblina", pregunta: "Cuánta neblina y garúa recibe (0 a 1)",
    valor: (p) => p.indice_niebla, cortes: [0.25, 0.45, 0.65, 0.85], colores: SEC,
    etiquetas: ["Casi nunca", "Poca", "Frecuente", "Muy frecuente", "Casi permanente"],
    formato: (v) => v.toFixed(2).replace(".", ",") },
  { id: "cloruros", grupo: "Ambiente", nombre: "Sal en el aire", pregunta: "Cloruros que se depositan por día",
    valor: (p) => p.deposicion_cl_mg_m2_d, cortes: [3, 15, 60, 300], colores: AZUL,
    etiquetas: rangos([3, 15, 60, 300], "mg/m²·d"), formato: (v) => `${n0(v)} mg/m²·d` },
  { id: "relieve", grupo: "Ambiente", nombre: "Relieve", pregunta: "Altura media del terreno",
    valor: (p) => p.elevacion_media_m ?? 0, cortes: [100, 300, 600, 1000], colores: TIERRA,
    etiquetas: rangos([100, 300, 600, 1000], "m"), formato: (v) => `${n0(v)} m` },
  { id: "poblacion", grupo: "Personas", nombre: "Ciudades", pregunta: "Grado de urbanización (WorldPop 2022, Censo 2017)",
    valor: (p) => URB.indexOf(p.clase_urbana), cortes: [1, 2, 3], colores: ["#efe9de", "#d5c2a3", "#b07f58", "#6e3b24"],
    etiquetas: ["Deshabitado", "Rural", "Periurbano", "Urbano"], formato: (v) => ["Deshabitado", "Rural", "Periurbano", "Urbano"][v] ?? "—" },
  { id: "prioridad", grupo: "Personas", nombre: "Dónde rinde más", pregunta: "Personas que viven donde el concreto común se deteriora antes",
    valor: (p) => p.prioridad, cortes: [1000, 10000, 50000, 200000], colores: CALOR,
    etiquetas: rangos([1000, 10000, 50000, 200000], "personas"), formato: (v) => `${n0(v)} personas` },
  { id: "vida", grupo: "Concreto", nombre: "Concreto común", pregunta: "¿Cuántos años de diseño cumple el concreto de hoy? (Tipo I, a/c 0,55, 40 mm; fib B34, β ≥ 1,3)",
    valor: (p) => p.comun_cumple_anios, cortes: [25, 50, 75, 100], colores: [...CALOR].reverse(),
    etiquetas: ["No llega a 25 años", "Cumple 25", "Cumple 50", "Cumple 75", "Cumple 100"],
    formato: (v) => v ? `cumple ${v} años` : "no llega a 25 años" },
  { id: "costo", grupo: "Concreto", nombre: "Costo", pregunta: "Costo por m³ de la receta más económica",
    valor: (p) => p.economica_costo_m3, cortes: [500, 520, 540, 560], colores: ["#145c46", "#3f8a6e", "#d9c39a", "#d48b5b", "#ae5634"],
    etiquetas: rangos([500, 520, 540, 560], "S/ por m³"), formato: (v) => `S/ ${n0(v)} por m³` },
];

export function clase(capa: Capa, v: number): number {
  let i = 0;
  while (i < capa.cortes.length && v >= capa.cortes[i]) i++;
  return i;
}
export const color = (capa: Capa, v: number) => capa.colores[clase(capa, v)] ?? "#999";
