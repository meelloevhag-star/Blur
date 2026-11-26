# Machine learning para hormigón autorreparable: referencias

Las referencias se identificaron en el catálogo (búsqueda en Europe PMC y OpenAlex del 2026-11-24) y en una búsqueda complementaria en OpenAlex con las consultas "machine learning / gene expression programming / artificial neural network / gradient boosting self-healing concrete". Los metadatos bibliográficos se tomaron de Crossref y, para [7], de OpenAlex.

Los métodos listados salen del **resumen** (OpenAlex). No se leyó el texto completo, así que deben confirmarse antes de citarlos en detalle.

1. Zhuang, X., & Zhou, S. (2019). The prediction of self-healing capacity of bacteria-based concrete using machine learning approaches. *Computers, Materials & Continua*, 59(1), 57–77. https://doi.org/10.32604/cmc.2019.04589
   - Métodos según el resumen: ANN, árbol de decisión, gradient boosting, SVR, regresión.
   - Hormigón con bacterias. Está en el catálogo.
2. Huang, X., Sresakoolchai, J., Qin, X., Ho, Y. F., & Kaewunruen, S. (2022). Self-healing performance assessment of bacterial-based concrete using machine learning approaches. *Materials*, 15(13), 4436. https://doi.org/10.3390/ma15134436
   - Métodos según el resumen: random forest, árbol de decisión, gradient boosting, SVR.
   - Está en el catálogo (PMC9267731).
3. Pessoa, C. L. E., Peres Silva, V. H., & Stefani, R. (2024). Prediction of the self-healing properties of concrete modified with bacteria and fibers using machine learning. *Asian Journal of Civil Engineering*, 25(2), 1801–1810. https://doi.org/10.1007/s42107-023-00878-w
   - Métodos según el resumen: random forest, SVM, regresión.
   - Está en el catálogo. Crossref da el año de volumen 2024; la publicación en línea es de 2023.
4. Tian, Q., Lu, Y., Zhou, J., Song, S., Yang, L., Cheng, T., et al. (2024). Exploring the viability of AI-aided genetic algorithms in estimating the crack repair rate of self-healing concrete. *Reviews on Advanced Materials Science*, 63(1), 20230179. https://doi.org/10.1515/rams-2023-0179
   - Métodos según el resumen: GEP y MEP (programación genética).
5. Lou, Y., Wang, H., Amin, M. N., Arifeen, S. U., Dodo, Y., Althoey, F., et al. (2024). Predicting the crack repair rate of self-healing concrete using soft-computing tools. *Materials Today Communications*, 38, 108043. https://doi.org/10.1016/j.mtcomm.2024.108043
   - Métodos: "soft computing". OpenAlex no tiene el resumen, así que el método concreto no está verificado.
6. Omar, O., Dhasmana, H., Noorvand, H., & Hassan, M. (2026/2027). Gaussian noise–augmented machine learning models for predicting the healing performance of self-healing concrete. *Journal of Materials in Civil Engineering*, 39(2), 04026574. https://doi.org/10.1061/JMCEE7.MTENG-22801
   - Métodos según el resumen: LSTM, gradient boosting, SVR; su depósito Zenodo (10.5281/zenodo.18509859) incluye un modelo GRU.
   - Los datos están en `raw/zenodo_18509859_ml_shc/` (Final_SHC.csv, 1552 filas).
   - Crossref asigna 2027 como año de volumen.
7. Khosravi, H., Kiani, P., Bahram, M., & Lezgy-Nazargah, M. (2025). Prediction of crack repair percentage in self-healing concrete using machine learning. *Scientific Reports*, 16, 533. https://doi.org/10.1038/s41598-025-30158-3
   - Métodos según el resumen: ANN con algoritmo genético.
   - Volumen y página tomados de OpenAlex; Crossref no respondió.

Relacionados que no son modelos de cierre en hormigón bacteriano:
- 10.3390/ma14154068 (cicatrización autógena, ML, 2021).
- 10.1016/j.asej.2021.04.008 (GEP para la resistencia del hormigón bacteriano, 2021).
- 10.1038/s41598-025-96971-y (random forest + Kuhn-Tucker; está incluido en el meta-dataset v2, aunque recomiendo descartar sus filas por calidad de los datos).
