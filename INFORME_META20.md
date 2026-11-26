# Informe · ¿Es alcanzable un error < 20 puntos de cierre?

Datos: 2167 réplicas (Mousa 2022 y Cappellesso 2024). Resultados en `resultados/meta20_diagnostico.json` y `resultados/meta20_neat.json`; figura en `resultados/fig_meta20_calibracion.png`.

## Veredicto
**Sí, es alcanzable, pero no con un solo modelo ni sin datos locales.**

| Situación | Mejor error medio | ¿< 20? |
|---|---|---|
| Piso de ruido (irreducible con estas variables) | 9–10 pp | — |
| Mismo laboratorio | 12,5 pp (Random Forest) | ✅ |
| Laboratorio nuevo **sin** ensayos locales | ≈ 20 pp (**NEAT**) | ⚠️ en el límite |
| Laboratorio nuevo con **10–20** probetas locales | 14,7–17,7 pp (Random Forest) | ✅ |
| Laboratorio nuevo con 40 probetas locales | 13,6–15,1 pp (Random Forest) | ✅ (< 15 en un sentido) |
| Estudio nuevo de la literatura (sin calibrar) | 30–33 pp | ❌ |

## Hallazgos
1. **Piso de ruido (E1).** Hay 9–10 pp que ningún modelo puede eliminar con las variables actuales; entre zonas de una misma probeta, la variación ya es de 7,8 pp. La meta de 20 es físicamente posible; bajar de 10 exige medir mejor o añadir variables.
2. **NEAT es el mejor punto de partida en contextos nuevos.** Sin ningún dato local queda en ≈ 20 pp, frente a 25–39 pp de los árboles. Pero **se estanca en ≈ 18 pp**: su parsimonia le impide aprovechar los datos locales.
3. **Random Forest es el mejor calibrador local.** Arranca muy mal (25–39 pp), pero baja de 20 pp con 10–20 probetas locales y llega a unos 15 pp con 20–40.
4. **El NEAT cinético (E3) no funcionó**: 20 pp dentro del laboratorio y 31 pp entre laboratorios, peor que el NEAT normal. Una sola velocidad de cierre k por mezcla no describe los datos; Cappellesso satura en el 100 % y las edades no se solapan.
5. **El desacuerdo entre redes NEAT (E4) no mide el error.** La correlación duda–error es de −0,1 y la cobertura de los intervalos del 80 % queda en el 9–45 %. Las redes NEAT no "saben" cuándo se equivocan por comparación entre semillas.

## Recomendaciones para el núcleo del sistema
1. **Modelo híbrido NEAT → árboles.** NEAT da la predicción de partida en una zona nueva y un modelo de árboles aprende el residuo con los ensayos locales. Es el siguiente experimento: combina los ~20 pp iniciales de NEAT con la caída a ~15 pp de los árboles.
2. **Incertidumbre con predicción conforme agrupada**, no con el desacuerdo entre redes: da cobertura garantizada, se ajusta con los ensayos locales y se combina con la distancia al dominio conocido.
3. **Plan de ensayos locales:** **20 probetas o fisuras por zona nueva** como mínimo para garantizar < 20 pp; 40 para acercarse a 15.
4. **Para bajar del piso de 10 pp:** variables nuevas (humedad, ciclos de mojado/secado, dosis de esporas, causa de la fisura) y un protocolo de medición homogéneo. Es tarea de los agentes de zona, materiales y curador.
5. **La cinética no se descarta**, pero necesita datos con edades que se solapen y un modelo de dos fases. Queda en espera hasta tener esos datos.
