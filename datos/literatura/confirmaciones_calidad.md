# Confirmaciones de calidad (documento leído completo)

Con metadatos el tier es provisional (máximo T2). Esta lista registra los documentos leídos completos y por qué se les fijó el tier con `python -m hefesto.agentes.repositorios confirmar <id> <tier> [--campo si] [--grado DOC]`. Solo se nombran los autores que figuran en el texto leído.

**SS+** = T0 (completo, tangible, trazable, cualitativo y cuantitativo, con respaldo de organizaciones) **y** aplicado en un prototipo o en una estructura real en servicio.

## SS+ (11)

| # | Documento | Ámbito | Por qué es T0 y aplicado |
|---|---|---|---|
| 1 | Davies et al. (2018), *Large Scale Application of Self-Healing Concrete: Design, Construction, and Testing*, Frontiers in Materials, 10.3389/fmats.2018.00051 | global (Reino Unido) | Ensayo a escala real en la obra de la autopista A465 Heads of the Valleys, en curso, con cuatro tecnologías de autorreparación (incluida bacteriana).<br>Tablas de mezcla, ancho de fisura (microscopio óptico, DEMEC y DIC), permeabilidad y calendario de seguimiento hasta los 231 días.<br>Financiado por EPSRC (proyecto Materials for Life) y Costain. CC BY. |
| 2 | Al-Tabbaa, Litina, Giannaros, Kanellopoulos y Souza (2019), *First UK field application and performance of microcapsule-based self-healing concrete*, Construction and Building Materials, 10.1016/j.conbuildmat.2019.02.178 | global (Reino Unido) | El mismo ensayo de la A465, para microcápsulas.<br>Cierre de ancho de fisura en campo, CWH = (wi − wh)/wi, junto con la permeabilidad al aire (kT) en campo y en laboratorio y la mezcla C40/50 tabulada.<br>Versión aceptada en el repositorio de la Universidad de Hertfordshire. |
| 3 | Jakubovskis y Boris (2022), *The Construction of a Footbridge Prototype with Biological Self-Healing Concrete: A Field Study*, Materials, 10.3390/ma15238585 | global (Lituania) | Primer prototipo de pasarela con vigas de concreto autorreparable bacteriano.<br>Mezcla tabulada (CEM I 52,5 R; agente en arcilla expandida, 270 kg/m³) y razón de cierre h = (wi − wt)/wi a 28 y 98 días, con 24–30 puntos por fisura.<br>Financiado por el Consejo de Investigación de Lituania (S-MIP-20-32). CC BY.<br>El cierre en campo aún se está midiendo: la mezcla del prototipo es la misma que se ensayó. |
| 4 | Othmen, Bonnet y Schoefs (2018), *Statistical investigation of different analysis methods for chloride profiles within a real structure in a marine environment*, Ocean Engineering, 10.1016/j.oceaneng.2018.03.040 | global | Viga real de 28 años en zona de salpicaduras; muchos perfiles de cloruros medidos.<br>Cs y D por la segunda ley de Fick, con sus coeficientes de variación (44 % y 61 %).<br>Es justo el dato que usa `ModeloCloruros`. |
| 5 | Clerc, Schoefs, Oumouni, Othmen y Bonnet (2024), *Modeling of Chloride Spatial Variability in a Reinforced Concrete Wharf from Onsite Measurements*, 10.1061/ajrua6.rueng-1214 | global | 37 perfiles de cloruros in situ en una viga de un muelle real, con análisis geoestadístico de Csa y Da. Versión en HAL (Nantes Université). |
| 6 | *I-129 Missouri River Bridge Deck Condition Assessment Using Non-Destructive Testing*, informe patrocinado por el Iowa Department of Transportation (OpenAlex W7113577787) | global (EE. UU.) | Puente real.<br>Ensayos no destructivos (IR, GPR, eco de impacto, potencial de media celda), núcleos con cloruros a lo largo del espesor y predicción de vida útil. |
| 7 | Liu et al. (2020), *Chloride Distribution and Steel Corrosion in a Concrete Bridge after Long-Term Exposure to Natural Marine Environment*, Materials, 10.3390/ma13173900 | global (China) | Puente real de unos 30 años en Shenzhen.<br>Perfiles de cloruros (titulación potenciométrica) en tablero y pila, Csa y D por zona, efecto del ancho de fisura (0,1–0,2 mm) y datos ambientales del 2000 al 2015.<br>Financiado por la NSFC y Guangdong. CC BY. |
| 8 | Wall, H. (2013), *Service Life Assessment of Harbor Structures – Case studies of chloride ingress into concrete structures and sheet piling corrosion rates*, tesis doctoral, LTH, Universidad de Lund | global (Suecia) | Casos de estructuras portuarias reales.<br>Recopila 3 artículos de revista y 3 de congreso.<br>Financiada por Skanska, SBUF y el consorcio VBT. Grado DOC (leído). |
| 9 | Sandberg, P. (1998), *Chloride initiated reinforcement corrosion in marine concrete*, tesis doctoral, LTH, Universidad de Lund | global (Suecia) | Estación de exposición en campo y columna de un puente real.<br>Umbrales de cloruro, perfiles ajustados a Fick y predicción de vida útil. Grado DOC (leído). |
| 10 | Lindvall, A. (2003), *Environmental actions on concrete exposed in marine and road environments and its response*, tesis doctoral, Chalmers | global (Suecia) | Estudios de campo en ambiente marino (probetas idénticas sumergidas en distintos lugares) y en carreteras, con la exposición cuantificada. Grado DOC (leído). |
| 11 | Khani, S. (2024), *Chloride exposure and ingress into concrete under severe winter conditions*, tesis doctoral, Universidad Laval (Canadá), HAL tel-05532436 | global (Canadá) | Experimentos de campo y estación meteorológica: sales de deshielo reales y penetración en el concreto. Grado DOC (leído). |

## Leídos que no llegan a SS+

| Documento | Tier | Motivo |
|---|---|---|
| Mors y Jonkers (2019), RILEM Technical Letters, 10.21809/rilemtechlett.2019.93 | T2 (S) | Demostradores reales (Chemelot, Groningen Forum).<br>Los autores dicen que no pudieron demostrar el cierre en campo porque casi no hubo fisuras; en campo solo se midió absorción con tubo Karsten. |
| OSTI 1235560, ensayo de campo de biomineralización en pozo | T2 (S) | Sella el cemento de un pozo, no concreto estructural. |
| Morán Córdova (2023, UCV) | T1 (S) | Inspección completa de 64 estructuras en Colán, sin ensayos de laboratorio ni respaldo de organizaciones. |
| UCV 72746, *Lysinibacillus sphaericus* (Piura) | T1 (S) | w0 y % de sellado por probeta (Tabla 6). Solo laboratorio y 14 días. |
| UCV 134208, bioconcreto en Piura | T2 (B) | El sellado de la Tabla 22 no tiene w0. La Tabla 16 contradice al texto. |
| UCV 174160, quitosano y agua de mar | T3 (C) | No es autorreparable.<br>Una probeta por edad, fechas de rotura imposibles y cargas en kg que no corresponden a los kN. |

## No se pudieron leer (sin canal abierto; no se fuerza)
- Ghent (biblio.ugent.be): ahora pide iniciar sesión.
- Cardiff ORCA y Bath OPUS: devuelven una página web en lugar del PDF.
- SINTEF COIN, *Shore Approach, 26 years…*: NVA marca el archivo como abierto, pero su API da 403.
- Aplicación en canales de riego en Ecuador (OpenAlex W2344742069): acceso cerrado.
