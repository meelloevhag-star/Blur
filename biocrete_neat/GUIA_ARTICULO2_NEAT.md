# BioCrete-NEAT · Módulo Micro para Artículo 2 (Neuroevolución de RNAs + Meta-Dataset CAB)

> **Separación estratégica recomendada:**
> - **Artículo 1 (`biocrete_markov/`):** Nivel **Macro / Estructural** — Cadena de Markov 5E no homogénea + viabilidad biológica ($\tau_{\text{bio}}$) + Fick/Monte Carlo + LCC vs. Life-365/*fib MC 34* + caracterización temprana y económica del consorcio comercial agrícola (*BAC 42* + *Bayfolan Soil* + *BioSpore*).
> - **Artículo 2 (`biocrete_neat/`):** Nivel **Micro / Material** — Meta-dataset experimental de literatura + **Neuroevolución (NEAT)** para predecir el cierre de fisuras (%) y la reducción de difusión ($\alpha$) **enfrentado contra tus propios ensayos experimentales de 28, 56 y 90 días** (EN 12390-8 y microscopía óptica en agua de mar Paita), cerrando el puente **Micro (NEAT) $\rightarrow$ Macro (BioCrete-Markov)**.

---

## 1. Cómo ejecutar el prototipo NEAT
```powershell
cd C:\Users\ecv_0\Desktop\Art\biocrete_neat
.\.venv\Scripts\python.exe entrenar_neat.py
```
Genera automáticamente en `resultados/`:
- `resumen_neat.json`: métricas de validación cruzada 5-fold (NEAT vs. Random Forest vs. Ridge) y topología exacta evolucionada.
- `predicciones_paita_neat_vs_markov.csv`: predicción *a priori* para tus mezclas de Paita comparada contra el umbral $\alpha_{\min}$ de `BioCrete-Markov`.
- `fig1_neat_convergencia_y_comparacion.png`: curva evolutiva de NEAT y dispersión Real vs. Predicho (5-fold CV).
- `fig2_neat_topologia_y_importancia.png`: diagrama visual de la **red neuronal mínima** y la importancia física de cada variable.

---

## 2. Cómo escalar el meta-dataset para publicación Q1/Q2
El archivo `datos/meta_dataset_cab.csv` arranca con **36 condiciones experimentales reales verificadas de 12 publicaciones con DOI**.  
Para el Artículo 2, solo añade nuevas filas al CSV conforme revises más estudios (meta recomendada: **100 a 200 registros**), más tus propias filas medidas a **28, 56 y 90 días** como **conjunto de prueba externo (*hold-out* independiente de Paita)** para demostrar que la red neuroevolucionada generaliza a un laboratorio real no visto.

---

## 3. Cómo defender NEAT ante el jurado en 30 segundos (Criterio Expositor)
1. **¿Por qué NEAT y no una red neuronal profunda elegida a mano?**  
   *"Porque en `config_neat.txt` la red empieza con **0 neuronas ocultas** (`num_hidden = 0`) y una penalización de parsimonia (Navaja de Occam). El algoritmo genético solo añade una neurona o conexión si reduce el error. Así evitamos inventar arquitecturas sobredimensionadas y podemos dibujar y explicar cada conexión de la red resultante."*
2. **¿Cómo sabemos que no memorizó los datos?**  
   *"Validamos con **validación cruzada 5-fold** (evaluando siempre en datos no vistos) y comparamos cara a cara contra una regresión lineal (Ridge) y Random Forest, además de medir la importancia por permutación de cada variable física."*
3. **¿Cómo se une con el Artículo 1?**  
   *"NEAT predice el comportamiento del material ($\alpha$ y cierre %) a partir de la mezcla y el ancho de fisura; luego ese $\alpha$ entra en **BioCrete-Markov** para ver cuántos años gana la estructura real en el litoral de Paita-Colán."*
