# Contrato para el agente del producto final

Esquema formal: [`hefesto/esquema/contrato_salida.json`](../hefesto/esquema/contrato_salida.json).

## Reglas
1. **El cierre no es vida útil.** `MotorBioCrete.predecir` da el **% de cierre de fisura a una edad de ensayo**, entre 3 y 480 días. Nunca conviertas ese número en años.
2. **Si `cierre_pct` es `null`, no hay predicción**: la edad pedida está fuera de lo medido. Muestra el `motivo`. No extrapoles.
3. **`confiable = false`** significa extrapolación: una combinación o un ancho sin datos. Muéstralo con aviso.
4. **Los años salen solo de `hefesto.durabilidad.vida_util`:**
   - `vida_util(...)` da el inicio de la corrosión por cloruros con 10 % de probabilidad (criterio de diseño de la fib);
   - `cierre_requerido(..., objetivo=25 | 40)` da el % de cierre mínimo para llegar a ese objetivo.
5. **Topes:**
   - si el resultado supera el horizonte, la salida dice `"cumple 40 años"`, con `anios = null`. **No inventes la cifra.**
   - un objetivo de más de 100 años se rechaza: ninguna norma lo pide (EN 1990: 50 años para edificios y 100 para puentes; BS 6349-1: 50 años para puertos).
6. **Régimen seco:** `estado = "fuera_de_alcance"`. Ahí gobierna la carbonatación y este modelo no da cifra.
7. **Muestra siempre el error:** ±20 puntos en el cierre sin calibrar. La vida útil depende de supuestos provisionales (ver `resultados/sensibilidad_vida.json`).

## Vida útil de diseño por uso (`hefesto/durabilidad/normas.py`)
| Uso | Años | Fuente |
|---|---|---|
| Pavimento | 25 | EN 1990 cat. 2 |
| Vivienda, edificio, tanque | 50 | EN 1990 cat. 4; práctica E.060 |
| Puerto | 50 | BS 6349-1-1 |
| Puente, túnel, obra hidráulica | 100 | EN 1990 cat. 5 |

## Datos listos para usar
`resultados/vida_zonas.csv` tiene una fila por cada una de las 384 zonas, con estas columnas:
- régimen y depósito de cloruros;
- mezcla recomendada (cemento, a/b y recubrimiento);
- años sin fisura y con la fisura sin reparar (texto ya acotado);
- cierre requerido para 25 y 40 años;
- cierre predicho por NEAT;
- veredicto.

## Por qué antes salían 150 años
- `VIDA_MAX = 150` saturaba el resultado.
- El régimen seco daba 150 de forma automática.
- La reparación se contaba dos veces y al cuadrado.
- El envejecimiento de la difusión no tenía tope: con α = 0,65 salían 4 364 años, que bajan a 152 al congelar la difusión a los 25 años.
