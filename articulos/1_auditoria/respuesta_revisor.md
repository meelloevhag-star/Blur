# Respuesta al revisor (revisión mayor)

Agradecemos la revisión. Aceptamos los problemas mayores y reorientamos el manuscrito como **auditoría de reproducibilidad**. El título ahora es: *¿Generalizan los modelos de aprendizaje automático para concreto autocurativo bacteriano?*.

Todas las cifras salen de `biocrete_neat/resultados/revision/resumen_revision.json`, que genera `biocrete_neat/analisis_revision.py`.

| # | Observación | Respuesta y cambio | Dónde |
|---|---|---|---|
| 1 | Ambiente marino confundido con la fuente | Aceptada. Nueva tabla de confusión fuente × variable y validación leave-one-source-out: todos los modelos dan R² negativo (entre -1.35 y -0.26). El texto ya no atribuye efectos al ambiente marino; declara que no son identificables. | Tabla de confusión; Resultados: variables confundidas y desempeño |
| 2 | Prueba de aprendizaje continuo asimétrica | Aceptada. Ahora es una prueba secuencial en la que modelo congelado, NEAT reanudado y NEAT desde cero se evalúan sobre los mismos grupos retenidos, con 10 semillas. Congelado: -0.37. Actualizado: 0.34. Caliente vs. frío no significativo (p = 0.32 y 0.70). Ya no se presenta como "aprendizaje continuo demostrado". La cosecha mensual y los aportes de terceros figuran como infraestructura, no como resultados. | Métodos: protocolos; Resultados: actualización secuencial |
| 3 | Predicciones de Paita inválidas | Aceptada. Bootstrap por grupos, comprobación de rango dentro de los datos marinos y avisos explícitos. Salen del IEEE; en la revista quedan solo como ilustración, con la advertencia de no usarlas para diseño. | Discusión (revista) |
| 4 | Afirmaciones estadísticas exageradas | Aceptada. GroupKFold repetido 5 × 5, ajuste anidado de los 4 modelos (rejillas declaradas), rejilla λ ∈ {2, 8, 16}×10⁻⁴ y prueba de Nadeau–Bengio. RF (0.674) y XGBoost (0.664) no difieren; NEAT (0.406) y Ridge (0.405) quedan por debajo. | Métodos; tabla de R² |
| 5 | Conclusión de fuga no robusta | Aceptada. Ambos protocolos se ejecutan con el mismo código, semillas y modelos. Cierre multi-estudio: 0.49 por filas frente a ≤ -0.09 por estudio. El 0,540 previo se retira. | Tabla de R²; Fig. 1; calidad del meta-dataset |
| 6 | Explicabilidad sobre otro modelo | Aceptada. SHAP fuera de muestra y permutación sobre el NEAT final con el λ elegido. Se declara qué entradas usa la red. | Resultados: qué aprenden los modelos |
| 7 | α sin documentar y referencias faltantes | Aceptada. Auditoría campo a campo del meta-dataset v1: las 13 filas verificables tenían errores. Se reconstruye α v2 con una regla explícita (28 condiciones, 7 estudios); su R² agrupado es ≤ 0.05. Las referencias se verificaron en Crossref. | Tabla de auditoría; calidad del meta-dataset |
| 8 | Literatura de ML escasa | Aceptada. Se añaden 6 trabajos de ML en autorreparación (verificados en Crossref) y se discute el riesgo de fuga en esa literatura. | Introducción; Discusión |

**Menores:**
- Rango completo de la penetración de cloruros (revista) y eliminación del "68 %" sin cita.
- Aditivo cristalino como variable propia.
- Recorte al 100 % declarado.
- Barras de error en las figuras.
- Highlights moderados.

Las declaraciones CRediT, de conflictos de intereses y de uso de IA quedan marcadas [Confirmar] para los autores.

## Segunda ronda (revisión menor)

| Observación | Cambio |
|---|---|
| El R² por laboratorio no era "media de ambos sentidos" | Ahora se reporta **por sentido** (Mousa→Cappellesso / Cappellesso→Mousa). Se añade MAE frente a una referencia que predice la media del laboratorio de entrenamiento (`analisis_revision.loso_detalle`, clave `replicas.fuente_detalle`). |
| R² < 0 entre laboratorios es extrapolación sin soporte común | Se declara explícitamente: no hay rango de edad común. La afirmación "aprenden el contexto del laboratorio" se sustituye. Resultado nuevo: NEAT reduce el error absoluto un 48 % y un 36 % frente a la referencia, más que los árboles en ambos sentidos. Ridge solo lo hace en un sentido. |
| Conclusión (2) "R² ≤ 0" contradice α = 0,053 | Ahora dice "R² agrupado ≤ 0,05". |
| Conclusión (3) no se cumple en α | Se añade: "en α ningún protocolo muestra señal". |
| El resumen citaba solo el lote 2 | Ahora cita los lotes 2 y 3. |
| Especulación sobre otra literatura | Se reformula como hipótesis no verificada. |
| SHAP en modelos sin validez predictiva | Se declara que esas importancias carecen de validez predictiva. |
| 78 % de Paita en el texto | Eliminado: no se reportan predicciones para Paita. |
| Menores | Se declaran las 40 generaciones de la prueba secuencial; "redes de 0 a 1 neuronas ocultas"; la carta cita secciones por nombre. |
