/**
 * Plano técnico de la receta (NEST + technical-wireframe-info-layout): corte de una losa con la cara
 * expuesta, la cota del recubrimiento y la barra de acero; al lado, la mezcla "explotada" en capas
 * proporcionales a su volumen por m³, con rótulos unidos por líneas de referencia.
 */
import type { Receta } from "./tipos";

const n0 = (x: number) => Math.round(x).toLocaleString("es-PE");
const n1 = (x: number) => x.toLocaleString("es-PE", { maximumFractionDigits: 1 });

export function htmlPlano(r: Receta, cara: string): string {
  const d = r.dosificacion;
  const W = 340, H = 196;
  // corte de losa (izquierda): 0–120 mm de profundidad dibujados en 0–150 px
  const X0 = 14, X1 = 150, Y0 = 34, ESC = 1.05;                     // px por mm
  const rec = r.recubrimiento_mm, yb = Y0 + rec * ESC;
  const barras = [36, 66, 96, 126].map((x) => `<circle cx="${X0 + x}" cy="${yb + 6}" r="6" class="pl-acero"/>`).join("");
  // mezcla explotada (derecha): volumen aparente por componente
  const capas: [string, number, string][] = [
    [`cemento ${d.cemento_tipo}`, d.cemento_kg / 3.0, `${n0(d.cemento_kg)} kg`],
    ["agua", d.agua_kg / 1.0, `${n0(d.agua_kg)} kg`],
    ["arena", d.arena_kg / 2.62, `${n0(d.arena_kg)} kg`],
    [`piedra ${d.tmn_mm <= 12.5 ? "½″" : "¾″"}`, d.piedra_kg / 2.68, `${n0(d.piedra_kg)} kg`],
    ...(d.superplastificante_kg + d.cristalino_kg > 0 ? [["aditivos", 30, `${n1(d.superplastificante_kg + d.cristalino_kg)} kg`] as [string, number, string]] : []),
    ...(d.agente_kg > 0 ? [["agente", 30, `${n1(d.agente_kg)} kg`] as [string, number, string]] : []),
  ];
  const total = capas.reduce((s, c) => s + c[1], 0);
  const XA = 196, XB = 232, alto = H - 40;
  let y = 18;
  const bloques = capas.map(([et, v, kg], i) => {
    const h = Math.max(7, (v / total) * (alto - capas.length * 4));
    const yy = y; y += h + 4;
    const ym = yy + h / 2;
    return `<rect x="${XA}" y="${yy.toFixed(1)}" width="${XB - XA}" height="${h.toFixed(1)}" class="pl-capa c${i}"/>
      <path d="M${XB} ${ym.toFixed(1)} H${XB + 12}" class="pl-ref"/>
      <text x="${XB + 15}" y="${(ym + 3).toFixed(1)}" class="pl-txt">${et.toUpperCase()}</text>
      <text x="${W - 4}" y="${(ym + 3).toFixed(1)}" class="pl-txt pl-num" text-anchor="end">${kg}</text>`;
  }).join("");
  return `<figure class="plano" aria-label="Plano técnico: corte con ${rec} mm de recubrimiento y mezcla por m³">
    <svg viewBox="0 0 ${W} ${H}" role="img">
      <defs><pattern id="pl-rayado" width="6" height="6" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
        <line x1="0" y1="0" x2="0" y2="6" class="pl-rayas"/></pattern></defs>
      <text x="${X0}" y="14" class="pl-txt">CORTE · ${cara.split(" · ").pop()!.toUpperCase()}</text>
      <path d="M${X0} ${Y0 - 8} q 12 -6 24 0 t 24 0 t 24 0 t 24 0 t 24 0 t 16 0" class="pl-ola"/>
      <rect x="${X0}" y="${Y0}" width="${X1 - X0}" height="${H - Y0 - 22}" class="pl-losa"/>
      <rect x="${X0}" y="${Y0}" width="${X1 - X0}" height="${H - Y0 - 22}" fill="url(#pl-rayado)"/>
      ${barras}
      <path d="M${X1 + 8} ${Y0} V${yb}" class="pl-cota"/><path d="M${X1 + 4} ${Y0} H${X1 + 12} M${X1 + 4} ${yb} H${X1 + 12}" class="pl-cota"/>
      <text x="${X1 + 14}" y="${(Y0 + yb) / 2 + 3}" class="pl-txt pl-num">${rec} mm</text>
      <text x="${X0}" y="${H - 8}" class="pl-txt">ACERO A ${rec} mm · a/c ${d.a_c.toFixed(2)}</text>
      <text x="${XA}" y="10" class="pl-txt">MEZCLA POR m³</text>
      ${bloques}
    </svg></figure>`;
}
