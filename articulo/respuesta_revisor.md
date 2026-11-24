# Respuesta al revisor (revisión mayor)

Agradecemos la revisión. Aceptamos los problemas mayores y reorientamos el manuscrito como **auditoría de reproducibilidad**. El título ahora es: *¿Generalizan los modelos de aprendizaje automático para concreto autocurativo bacteriano?*.

Todas las cifras salen de `biocrete_neat/resultados/revision/resumen_revision.json`, que genera `biocrete_neat/analisis_revision.py`.

| # | Observación | Respuesta y cambio | Dónde |
|---|---|---|---|
| 1 | Ambiente marino confundido con la fuente | Aceptada. Nueva tabla de confusión fuente × variable y validación leave-one-source-out: todos los modelos dan R² negativo (entre -1.35 y -0.26). El texto ya no atribuye efectos al ambiente marino; declara que no son identificables. | Tabla II, §III-A, §III-B |
| 2 | Prueba de aprendizaje continuo asimétrica | Aceptada. Ahora es una prueba secuencial en la que modelo congelado, NEAT reanudado y NEAT desde cero se evalúan sobre los mismos grupos retenidos, con 10 semillas. Congelado: -0.37. Actualizado: 0.34. Caliente vs. frío no significativo (p = 0.32 y 0.70). Ya no se presenta como "aprendizaje continuo demostrado". La cosecha mensual y los aportes de terceros figuran como infraestructura, no como resultados. | §II-C, §III-E, Fig. 2 |
| 3 | Predicciones de Paita inválidas | Aceptada. Bootstrap por grupos, comprobación de rango dentro de los datos marinos y avisos explícitos. Salen del IEEE; en la revista quedan solo como ilustración, con la advertencia de no usarlas para diseño. | §IV (revista) |
| 4 | Afirmaciones estadísticas exageradas | Aceptada. GroupKFold repetido 5 × 5, ajuste anidado de los 4 modelos (rejillas declaradas), rejilla λ ∈ {2, 8, 16}×10⁻⁴ y prueba de Nadeau–Bengio. RF (0.674) y XGBoost (0.664) no difieren; NEAT (0.406) y Ridge (0.405) quedan por debajo. | §II-B/C, Tabla III |
| 5 | Conclusión de fuga no robusta | Aceptada. Ambos protocolos se ejecutan con el mismo código, semillas y modelos. Cierre multi-estudio: 0.49 por filas frente a ≤ -0.09 por estudio. El 0,540 previo se retira. | Tabla III, Fig. 1, §III-C |
| 6 | Explicabilidad sobre otro modelo | Aceptada. SHAP fuera de muestra y permutación sobre el NEAT final con el λ elegido. Se declara qué entradas usa la red. | §III-D |
| 7 | α sin documentar y referencias faltantes | Aceptada. Auditoría campo a campo del meta-dataset v1: las 13 filas verificables tenían errores. Se reconstruye α v2 con una regla explícita (28 condiciones, 7 estudios); su R² agrupado es ≤ 0.05. Las referencias se verificaron en Crossref. | Tabla IV, §III-C |
| 8 | Literatura de ML escasa | Aceptada. Se añaden 6 trabajos de ML en autorreparación (verificados en Crossref) y se discute el riesgo de fuga en esa literatura. | §I, §IV |

**Menores:**
- Rango completo de la penetración de cloruros (revista) y eliminación del "68 %" sin cita.
- Aditivo cristalino como variable propia.
- Recorte al 100 % declarado.
- Barras de error en las figuras.
- Highlights moderados.

Las declaraciones CRediT, de conflictos de intereses y de uso de IA quedan marcadas [Confirmar] para los autores.
