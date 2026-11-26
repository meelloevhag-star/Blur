# Cómo predicen otros trabajos (redes neuronales, NEAT y aprendizaje automático)

Búsqueda del 26-11-2026. Solo se resume lo que dice cada fuente; las cifras son las que publican sus autores, no se verificaron aquí. Esta tabla la amplía el agente LITERATURA.

| Trabajo | Qué predice | Algoritmo | Entradas | Cómo valida | Lo que reportan |
|---|---|---|---|---|---|
| [Self-Healing Performance Assessment of Bacterial-Based Concrete Using ML (Materials 2022)](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC9267731/) | Autorreparación de concreto bacteriano | Varios modelos de ML; el mejor es Gradient Boosting | Dosis de bacteria, ancho inicial de fisura, tiempo de curado | R², RMSE y validación cruzada de 10 particiones por fila | R² ≈ 0,96 |
| [Modeling Self-Healing of Concrete Using Hybrid GA–ANN (Materials 2017)](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC5459209/) | Ancho de fisura tras la autorreparación autógena | Red neuronal con pesos iniciales elegidos por algoritmo genético | Base de datos de autorreparación compilada de la literatura | Partición entrenamiento y prueba | "Precisión adecuada" |
| [Prediction of Healing Performance of Autogenous Healing Concrete Using ML (Materials 2021)](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC8348520/) | Autorreparación autógena | Comparación de varios modelos de ML | Mezcla, fisura y edad | Particiones aleatorias | — |
| [Alkali-resistant bacteria with polymer fibers (De Gruyter 2023)](https://www.degruyterbrill.com/document/doi/10.1515/rams-2023-0179/pdf) | Autorreparación | Programación genética (GEP y MEP) | 1 007 registros de la literatura: cemento, arena, agua, curado, bacteria y fibra | Particiones aleatorias | — |
| [Chloride diffusion with SCMs (Materials 2023)](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC9920323/) | Coeficiente de difusión de cloruros | ANN, ELM, SVM y ANFIS | Mezcla con adiciones | Particiones aleatorias | SVM fue el mejor |
| [Concrete chloride resistance, comprehensive dataset (Sci. Rep. 2023)](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC10497559/) | Coeficiente de migración de cloruros | Varios modelos de ML, con una web de predicción | Mezcla | Particiones aleatorias | — |
| [Strength and durability through DL and ANN (Front. Struct. Civ. Eng. 2024)](https://journal.hep.com.cn/fsce/EN/10.1007/s11709-024-1124-9) | Migración de cloruros y resistencia | Aprendizaje profundo y ANN | Mezcla | Particiones aleatorias | Precisión > 0,85 |

## Qué cambia en Hefesto
- **Nadie valida con otro laboratorio.** Todos los trabajos mezclan filas o estudios en particiones aleatorias. El artículo 1 de Hefesto mostró que con esa forma de validar la precisión se infla. El banco de Hefesto mide también por probeta y entre laboratorios, que es el uso real: predecir un concreto nuevo en un lugar nuevo.
- **No encontramos NEAT aplicado a concreto.** NEAT (Stanley y Miikkulainen, 2002) evoluciona a la vez la topología y los pesos. Lo más cercano en la literatura es la red cuyos pesos iniciales elige un algoritmo genético (GA–ANN), que no evoluciona la topología.
- **Matrices de predicción:** cada red de Hefesto se puede exportar como matrices de pesos por capa (`RedMatricial.matrices()`). Así se ve qué entradas usa y con qué peso, a diferencia de los ensambles de árboles.
