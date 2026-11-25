import type { Fick } from "./tipos";

const SEG_ANIO = 365.25 * 24 * 3600;

/** Función error (Abramowitz y Stegun 7.1.26, error < 1,5e-7). */
export function erf(x: number): number {
  const s = Math.sign(x), a = Math.abs(x);
  const t = 1 / (1 + 0.3275911 * a);
  const y = 1 - (((((1.061405429 * t - 1.453152027) * t) + 1.421413741) * t - 0.284496736) * t + 0.254829592) * t * Math.exp(-a * a);
  return s * y;
}

/** Cloruro (% masa de cemento) a la profundidad x_mm al cabo de t años: segunda ley de Fick con envejecimiento (fib B34). */
export function cloruro(f: Fick, x_mm: number, t: number): number {
  if (t <= 0) return 0;
  const D = f.d_m2_s * Math.pow(f.t0_anios / t, f.n);
  const x = Math.max(x_mm - (f.dx_mm ?? 0), 0);
  return f.cs * (1 - erf((x / 1000) / (2 * Math.sqrt(D * t * SEG_ANIO))));
}

/** Primer año entero en que el perfil medio alcanza C_crit en el acero (igual que durabilidad.inicio_medio); null si no llega. */
export function anioInicio(f: Fick, hasta = 150): number | null {
  if (f.cs <= f.c_crit) return null;
  for (let t = 1; t <= hasta; t++) if (cloruro(f, f.recubrimiento_mm, t) >= f.c_crit) return t;
  return null;
}
