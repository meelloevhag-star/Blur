# Hefesto

**Neuroevolución para concreto autorreparable que no depende de mantenimiento continuo.** Hefesto aprende de los datos existentes de concreto autocurativo y responde, para un lugar y un uso concretos: *¿qué concreto aguanta estas condiciones y alcanza la vida útil que pide la norma, y con qué incertidumbre?*

> Antes se llamaba **Blur**. El artículo 1 (auditoría de reproducibilidad) está congelado en `articulos/1_auditoria/`. El mapa y las recetas con costos viven aparte, en el [BioCrete Atlas](https://github.com/meelloevhag-star/Blur-con-esteroides), que solo consume la salida de Hefesto.

## Cómo funciona
```
agentes de IA ──► datos/entrantes ──► curador ──► datos/aceptados ──► orquestador ──► motor (NEAT)
 (literatura,        (esquema único)                                     │               │
  universidades,                                                         ▼               ▼
  datasets, zona)                                          necesidades.md      cierre de fisura (3–480 d)
       ▲                                                   (qué falta) ──┐            │
       └─────────────────────────────────────────────────────────────────┘            ▼
                                                           durabilidad: ¿alcanza la vida útil de la norma
                                                           en este lugar? (cloruros, fib B34, P = 10 %)
```

| Pieza | Dónde | Qué hace |
|---|---|---|
| Motor | `hefesto/motor/` | **Un solo motor**, elegido en un banco de comparación (abajo). |
| Durabilidad | `hefesto/durabilidad/` | Las clases `Exposicion`, `Mezcla`, `ModeloCloruros` y `Diseno`. Calculan la vida útil frente a cloruros con el modelo de la fib (envejecimiento congelado a los 25 años y P = 10 %) y el cierre de fisura necesario para llegar a la norma. Nunca informan más que el horizonte pedido; más de 100 años se rechaza. |
| Agentes | `hefesto/agentes/` | Agentes de IA que sondean literatura (Scopus, OpenAlex), repositorios universitarios (RENATI, ALICIA, DSpace), datasets (Zenodo, Dryad) y datos de zona. Además, el curador y el orquestador. |
| Datos | `datos/` | 2 166 réplicas de cierre (Mousa 2022, Cappellesso 2024), literatura verificada, 581 ensayos RCM de cloruros, 384 zonas costeras con clima ERA5 y normas. |
| Artículos | `articulos/` | `1_auditoria/` (cerrado) y `2_hefesto/` (en curso). |

## El motor: por qué este y no otro
`python -m hefesto.motor.banco` compara 13 candidatos con los mismos datos y las mismas particiones, en cinco criterios: precisión, efectividad, capacidad de mejora, velocidad y simplicidad. Resultado (`resultados/banco_motores.json`):

| Modelo | MAE dentro del laboratorio (por probeta) | MAE en otro laboratorio | MAE con 10 probetas locales |
|---|---|---|---|
| Random Forest / XGBoost | **12,8** | 31,7–31,9 | 19,7–20,8 |
| MLP 32×16 (retropropagación) | 15,7 | 29,4 | 22,4 |
| NEAT con capa oculta / evolución larga | 17,0–17,8 | 21,9–24,2 | 19,5–19,9 |
| NEAT ×5 | 17,6 | **19,3** | 19,2 |
| **H3 = NEAT ×5 + corrección local (ganador)** | 17,6 | **19,3** | **18,7** |

Las cifras del banco salen de un conjunto de semillas. Promediando 5 conjuntos, el error de H3 entre laboratorios es de 19,8 y 21,2 puntos según la dirección, y con 10 probetas locales baja a 17,9–19,1 (`resultados/hibrido.json`). Los modelos más grandes aprenden mejor dentro de un laboratorio y fallan más al predecir otro. La razón está en los datos: variables como ambiente marino o tipo de protección **coinciden con el laboratorio**, así que una red que las usa aprende "qué laboratorio es" y no "qué concreto repara". Por eso el NEAT que se queda con la edad, el curado y el ancho generaliza mejor. Para que el motor distinga tipos de bacteria y condiciones del lugar, hacen falta ensayos que las varíen dentro de un mismo laboratorio. Eso es lo que buscan los agentes.

Cada red NEAT se compila a una `RedMatricial` (matrices de pesos por capa). Da exactamente lo mismo que neat-python y entrena **52 veces más rápido**. La comparación con la literatura está en [`docs/literatura_modelos.md`](docs/literatura_modelos.md).

## Uso
```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
```
```bash
.venv/bin/python -m hefesto.esquema.mapear && .venv/bin/python -m hefesto.agentes.curador && .venv/bin/python -m hefesto.agentes.orquestador
```
```bash
.venv/bin/python -m hefesto.motor.banco
```
```bash
.venv/bin/python -m hefesto.durabilidad.vida_zonas && .venv/bin/python -m hefesto.durabilidad.sensibilidad_vida
```
```bash
.venv/bin/python -m pytest -q
```

Contrato para quien consuma la salida (el Atlas u otro agente): [`docs/CONTRATO_PRODUCTO.md`](docs/CONTRATO_PRODUCTO.md).
