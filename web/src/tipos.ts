export interface Dosificacion {
  cemento_tipo: string; cemento_kg: number; agua_kg: number; a_c: number; arena_kg: number; piedra_kg: number;
  tmn_mm: number; aire_pct: number; superplastificante_kg: number; cristalino_kg: number; agente_kg: number;
  fc_estimado_mpa: number; metodo: string;
}
export interface Receta {
  agente: string; agente_nombre: string; cepa: string; portador: string; nutriente: string; dosis_agente: string;
  curado_humedo_previo: boolean; dosificacion: Dosificacion;
  prediccion: { cierre_pct: number; cierre_ic95_pct: [number, number]; n_datos_combinacion: number };
  vida_util_anios: number; vida_util_sin_reparacion_anios: number;
  viabilidad: { costo_m3_pen: number; partidas_pen: Record<string, number>; planta_cemento: string;
    dist_planta_km: number; disponibilidad: number; proveedor_agente: string };
  en_dominio: boolean; avisos: string[]; origen: Record<string, string>;
}
/** Propiedades del GeoJSON ligero (pintar el mapa) + las del detalle (ficha). */
export interface PropsZona {
  id: string; departamento: string; provincia: string; distrito: string; franja: number; tramo: number;
  lat: number; lon: number; dist_mar_km: number; regimen: string; detalle?: string;
  indice_niebla: number; deposicion_cl_mg_m2_d: number; clase_iso9223: string;
  elevacion_media_m: number | null; frac_loma: number; poblacion: number; clase_urbana: string;
  severidad: number; prioridad: number; vida_util_concreto_comun_anios: number;
  ideal_cierre_pct: number; ideal_vida_anios: number; ideal_costo_m3: number; ideal_disponibilidad: number;
  economica_costo_m3: number; ideal_agente: string; ideal_cemento: string; ideal_a_c: number;
  ambiente?: Record<string, any>; relieve?: Record<string, number> | null; urbano?: Record<string, any> | null;
  reglas?: { clase: string; a_c_max: number; cemento_min_kg: number; fc_min_mpa: number; recubrimiento_mm: number; fuente: string };
  recetas?: { ideal: Receta; economica: Receta; disponible: Receta };
  referencia_sin_agente?: Receta;
}
export type Zona = GeoJSON.Feature<GeoJSON.Polygon, PropsZona>;
export interface Coleccion extends GeoJSON.FeatureCollection<GeoJSON.Polygon, PropsZona> { metadata: Record<string, any> }
export interface Terreno {
  nu: number; nv: number; u_km: [number, number]; v_km: [number, number]; h: number[];
  franjas: [number, string, number][];
}
