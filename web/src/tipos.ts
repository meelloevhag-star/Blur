export interface Dosificacion {
  cemento_tipo: string; cemento_kg: number; agua_kg: number; a_c: number; arena_kg: number; piedra_kg: number;
  tmn_mm: number; aire_pct: number; superplastificante_kg: number; cristalino_kg: number; agente_kg: number;
  fc_estimado_mpa: number; metodo: string;
}
export interface Receta {
  agente: string; agente_nombre: string; cepa: string; portador: string; nutriente: string; dosis_agente: string;
  curado_humedo_previo: boolean; dosificacion: Dosificacion;
  prediccion: { cierre_pct: number; cierre_ic95_pct: [number, number]; n_datos_combinacion: number };
  vida_util_anios: number; cumple_anios: number; recubrimiento_mm: number; durabilidad: Durabilidad; fick?: Fick;
  viabilidad: { costo_m3_pen: number; partidas_pen: Record<string, number>; planta_cemento: string;
    dist_planta_km: number; disponibilidad: number; proveedor_agente: string };
  en_dominio: boolean; avisos: string[]; origen: Record<string, string>;
}
/** Propiedades del GeoJSON ligero (pintar el mapa) + las del detalle (ficha). */
export interface PropsZona {
  id: string; departamento: string; provincia: string; distrito: string;
  anillo: number; q: number; r: number; frente_marino: boolean; dist_mar_min_km?: number;
  lat: number; lon: number; dist_mar_km: number; regimen: string; detalle?: string;
  indice_niebla: number; deposicion_cl_mg_m2_d: number; clase_iso9223: string;
  elevacion_media_m: number | null; frac_loma: number; poblacion: number; clase_urbana: string;
  severidad: number; prioridad: number; vida_util_concreto_comun_anios: number; comun_cumple_anios: number; ideal_cumple_anios: number;
  ideal_cierre_pct: number; ideal_vida_anios: number; ideal_costo_m3: number; ideal_disponibilidad: number;
  economica_costo_m3: number; ideal_agente: string; ideal_cemento: string; ideal_a_c: number;
  ambiente?: Record<string, any>; relieve?: Record<string, number> | null; urbano?: Record<string, any> | null;
  reglas?: { clase: string; a_c_max: number; cemento_min_kg: number; fc_min_mpa: number; recubrimiento_mm: number; fuente: string };
  recetas?: { ideal: Receta; economica: Receta; disponible: Receta };
  referencia_sin_agente?: Receta;
  fick_comun?: Fick; durabilidad_comun?: Durabilidad; aviso?: string | null;
  /** la misma celda evaluada para una obra a < 500 m del mar (solo celdas con orilla) */
  frente?: Frente | null;
}
export interface Frente {
  regimen: string; dist_mar_km: number; vida_util_concreto_comun_anios: number; fick_comun: Fick; durabilidad_comun: Durabilidad; aviso: string | null;
  indice_niebla: number; deposicion_cl_mg_m2_d: number; clase_iso9223: string;
  reglas: PropsZona["reglas"]; recetas: { ideal: Receta; economica: Receta; disponible: Receta };
}
/** C(x, t) = cs·(1 − erf((x − Δx) / (2·√(D·(t0/t)^n·t)))): valores medios, solo para dibujar */
export interface Fick { cs: number; d_m2_s: number; n: number; t0_anios: number; c_crit: number; recubrimiento_mm: number; dx_mm?: number }
/** Verificación probabilista fib B34: probabilidad de despasivación por edad (Pf ≤ 10 % ⇔ β ≥ 1,3). */
export interface Durabilidad { pf: Record<"25" | "50" | "75" | "100", number>; t10_anios: number; cumple_anios: number; beta_50: number }
export type Zona = GeoJSON.Feature<GeoJSON.Polygon, PropsZona>;
export interface Coleccion extends GeoJSON.FeatureCollection<GeoJSON.Polygon, PropsZona> { metadata: Record<string, any> }
export interface Terreno {
  nu: number; nv: number; u_km: [number, number]; v_km: [number, number]; h: number[];
  /** contorno de la celda en km locales (u a lo largo de la costa, v tierra adentro) */
  celda: [number, number][]; dist_mar_km: number; tam_km: number;
}
