import type { PropsZona } from "./tipos";

export type Agregado = "max" | "min" | "suma" | "moda" | "costa";
export interface Capa {
  id: string; nombre: string; pregunta: string; unidad?: string;
  valor(p: PropsZona): number;
  cortes: number[]; colores: string[]; etiquetas: string[];
  agregado: Agregado;            // cómo resumir las 6 franjas de un tramo en la cinta costera
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
  { id: "receta", nombre: "Qué concreto usar", pregunta: "Agente autorreparador de la receta ideal",
    valor: (p) => ORDEN_AG.indexOf(p.ideal_agente), cortes: [1, 2, 3, 4],
    colores: ORDEN_AG.map((a) => AGENTES[a].color), etiquetas: ORDEN_AG.map((a) => AGENTES[a].corto),
    agregado: "costa", formato: (v) => AGENTES[ORDEN_AG[v]]?.corto ?? "—" },
  { id: "regimen", nombre: "Exposición", pregunta: "Cómo le llega la sal al concreto",
    valor: (p) => ORDEN_REG.indexOf(p.regimen), cortes: [1, 2, 3, 4],
    colores: ORDEN_REG.map((r) => REGIMENES[r].color), etiquetas: ORDEN_REG.map((r) => REGIMENES[r].nombre),
    agregado: "moda", formato: (v) => REGIMENES[ORDEN_REG[v]]?.nombre ?? "—" },
  { id: "niebla", nombre: "Neblina", pregunta: "Cuánta neblina y garúa recibe (0 a 1)",
    valor: (p) => p.indice_niebla, cortes: [0.25, 0.45, 0.65, 0.85], colores: SEC,
    etiquetas: ["Casi nunca", "Poca", "Frecuente", "Muy frecuente", "Casi permanente"], agregado: "max",
    formato: (v) => v.toFixed(2).replace(".", ",") },
  { id: "cloruros", nombre: "Sal en el aire", pregunta: "Cloruros que se depositan por día",
    valor: (p) => p.deposicion_cl_mg_m2_d, cortes: [3, 15, 60, 300], colores: AZUL,
    etiquetas: rangos([3, 15, 60, 300], "mg/m²·d"), agregado: "costa", formato: (v) => `${n0(v)} mg/m²·d` },
  { id: "relieve", nombre: "Relieve", pregunta: "Altura media del terreno",
    valor: (p) => p.elevacion_media_m ?? 0, cortes: [100, 300, 600, 1000], colores: TIERRA,
    etiquetas: rangos([100, 300, 600, 1000], "m"), agregado: "max", formato: (v) => `${n0(v)} m` },
  { id: "poblacion", nombre: "Ciudades", pregunta: "Grado de urbanización (WorldPop 2022, Censo 2017)",
    valor: (p) => URB.indexOf(p.clase_urbana), cortes: [1, 2, 3], colores: ["#efe9de", "#d5c2a3", "#b07f58", "#6e3b24"],
    etiquetas: ["Deshabitado", "Rural", "Periurbano", "Urbano"], agregado: "max", formato: (v) => ["Deshabitado", "Rural", "Periurbano", "Urbano"][v] ?? "—" },
  { id: "prioridad", nombre: "Dónde rinde más", pregunta: "Personas que viven donde el concreto común se deteriora antes",
    valor: (p) => p.prioridad, cortes: [1000, 10000, 50000, 200000], colores: CALOR,
    etiquetas: rangos([1000, 10000, 50000, 200000], "personas"), agregado: "suma", formato: (v) => `${n0(v)} personas` },
  { id: "vida", nombre: "Concreto común", pregunta: "Años hasta la corrosión con el concreto de hoy (Tipo I, a/c 0,55)",
    valor: (p) => p.vida_util_concreto_comun_anios, cortes: [10, 25, 50, 100], colores: [...CALOR].reverse(),
    etiquetas: rangos([10, 25, 50, 100], "años"), agregado: "min", formato: (v) => v >= 150 ? "150 años o más" : `${n0(v)} años` },
  { id: "costo", nombre: "Costo", pregunta: "Costo por m³ de la receta más económica",
    valor: (p) => p.economica_costo_m3, cortes: [500, 520, 540, 560], colores: ["#145c46", "#3f8a6e", "#d9c39a", "#d48b5b", "#ae5634"],
    etiquetas: rangos([500, 520, 540, 560], "S/ por m³"), agregado: "min", formato: (v) => `S/ ${n0(v)} por m³` },
];

export function clase(capa: Capa, v: number): number {
  let i = 0;
  while (i < capa.cortes.length && v >= capa.cortes[i]) i++;
  return i;
}
export const color = (capa: Capa, v: number) => capa.colores[clase(capa, v)] ?? "#999";

export function resumirTramo(capa: Capa, zonas: PropsZona[]): number {
  const v = zonas.map((z) => capa.valor(z));
  switch (capa.agregado) {
    case "max": return Math.max(...v);
    case "min": return Math.min(...v);
    case "suma": return v.reduce((a, b) => a + b, 0);
    case "costa": return capa.valor(zonas.reduce((a, b) => (b.franja < a.franja ? b : a)));
    case "moda": {
      const c = new Map<number, number>();
      v.forEach((x) => c.set(x, (c.get(x) ?? 0) + 1));
      return [...c.entries()].sort((a, b) => b[1] - a[1])[0][0];
    }
  }
}
