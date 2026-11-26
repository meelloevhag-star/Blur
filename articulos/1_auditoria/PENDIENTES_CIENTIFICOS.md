# Pendientes científicos (revisión de código F1)

Hallazgos de la revisión de código de la Fase 1. No son errores de cálculo, pero un revisor de revista los señalaría. Se resuelven en la **Fase 3** (modelos ampliados) y se reflejan en el texto en las Fases 4–5.

| # | Severidad | Hallazgo | Dónde | Acción prevista |
|---|---|---|---|---|
| 1 | Alta | El modelo final que produce la **Tabla V** y la **topología de la Fig. 2** se entrena con λ_p = 1,2e-4 (el que obtuvo R² = 0,366 en CV), no con el λ_p = 8e-4 del titular R² = 0,540. | `entrenar_neat.py` (entrenamiento final) | F3: entrenar el modelo final con el λ_p seleccionado y regenerar la Tabla V y la Fig. 2. Si no, declararlo en el texto. |
| 2 | Alta | El panel izquierdo de la **Fig. 1** (convergencia) es del modelo final con λ = 1,2e-4; el panel derecho (real vs. predicho) es de la CV con λ = 8e-4. | `graficar_resultados` | F3: usar la misma configuración en ambos paneles. |
| 3 | Media | **Sesgo de selección**: λ_p se eligió viendo el R² de CV en las mismas particiones (n = 36). El 0,540 no es una estimación insesgada, y la ventaja sobre Ridge (0,523) es mínima. | Metodología II-C | F3: CV anidada para elegir λ_p; en el texto, reportar los dos λ como exploratorios. |
| 4 | Media | **KFold por fila** sobre un meta-dataset multi-estudio: filas del mismo estudio caen en entrenamiento y prueba (fuga leve que favorece a los tres modelos). | `evaluar_validacion_cruzada` | F3: `GroupKFold` por la columna `estudio`. |
| 5 | Baja | La **Tabla V** da filas idénticas para a/c 0,68 y 0,45: la red final (2 conexiones) ignora el a/c. | Tabla V | F3/F4: declarar la limitación o usar un modelo que capture el a/c. |
| 6 | Baja | Mousa: la normalización min-max usa todo el conjunto antes de la CV (fuga leve), a diferencia de los límites físicos fijos que declara el artículo. | `procesar_zenodo_y_entrenar.py` | F3: límites físicos fijos. |
| 7 | Baja | Los tests verifican los JSON guardados, no re-ejecutan el entrenamiento. | `tests/` | F3: test lento opcional que re-entrena y compara. |
| 8 | Info | No se reporta el cierre % sobre el meta-dataset (NEAT R² = 0,047, RF 0,039, Ridge 0,164). | Resultados | F5: reportarlo en la versión revista. |
