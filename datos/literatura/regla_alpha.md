# Regla de cálculo de `alpha_equiv` (meta-dataset v2)

## Definición

`alpha_equiv` es la **reducción fraccional, en [0, 1], de una propiedad de transporte** de la probeta **con bacterias** tras la cicatrización. Se aplica a una de estas propiedades: caudal o coeficiente de permeabilidad al agua, absorción capilar o sorptividad, o penetración, migración o difusión de cloruros.

## Regla primaria (`alpha_equiv`, `alpha_base = referencia`)

```
alpha_equiv = 1 − P_bact,cicatrizada / P_ref,cicatrizada
```

- `P_bact,cicatrizada` es la propiedad de la serie con bacterias después del periodo de cicatrización.
- `P_ref,cicatrizada` es la misma propiedad, medida con el mismo método, en la **referencia comparable sin bacterias**. La referencia debe tener la misma matriz o una equivalente, la misma condición de cicatrización y exposición, la misma edad y el mismo ancho de fisura (nominal o rango declarado).
  - Si la fuente tiene varias referencias sin bacterias, se usa el mortero u hormigón **simple**, no el control abiótico con nutrientes, salvo que la fuente solo ofrezca este último. La elección queda anotada en `nota`.
- Si la fuente da directamente "X % de reducción respecto a la referencia sin bacterias", entonces alpha = X/100.
- Si la fuente expresa ambas series como fracción de un **mismo valor inicial común**, se usa `alpha = 1 − f_bact / f_ref`. Ejemplo: Palin et al. 2017, donde las permeabilidades tras la cicatrización se expresan como % de la permeabilidad inicial media de la serie 1h.
- Las filas de referencia sin bacterias tienen `alpha_equiv` vacío (`no_aplica` para esa fila).
- **Valores negativos.** Si el cálculo da un valor < 0 (la serie con bacterias transporta más que la referencia), `alpha_equiv` queda vacío. El valor bruto se anota en `nota`. No se recorta a 0.
- **Sin relleno.** No se calcula alpha si la fuente no reporta los valores necesarios. Tampoco se estima desde figuras ni se convierte desde otra propiedad.

## Línea base alternativa (`alpha_estado_inicial`, columna aparte)

```
alpha_estado_inicial = 1 − P_misma_probeta,cicatrizada / P_misma_probeta,fisurada_inicial
```

Esta es la "eficiencia de sellado" o el "healing ratio de permeabilidad" que muchos estudios publican, por ejemplo con RILEM o con el ensayo de caudal de Van Mullem. Incluye la cicatrización autógena, así que **no se mezcla** con `alpha_equiv`. Valores fuera de [0, 1] quedan vacíos y anotados.

## Columnas asociadas

| Columna | Valores | Significado |
|---|---|---|
| `alpha_base` | `referencia` | Hay `alpha_equiv` (regla primaria) |
| | `estado_inicial` | Solo hay `alpha_estado_inicial` |
| | `no_aplica` | No hay ningún alpha (no reportado, fila de referencia o valor inválido) |
| `alpha_propiedad` | `permeabilidad_agua`, `absorcion_capilar`, `cloruros_penetracion`, `cloruros_difusion`, vacío | Propiedad de transporte usada |

## Consecuencias para las filas del meta original

Los `alpha_equiv` del CSV original (v1) no documentan cómo se calcularon. Donde la fuente era accesible no coincidían con valores publicados (ver `verificacion_meta_original.csv`). Por eso:

- En v2 solo se conserva un alpha si se pudo recalcular con esta regla.
- En los demás casos queda vacío. El valor v1 se cita en `nota` como "alpha_v1 (no verificable)".
