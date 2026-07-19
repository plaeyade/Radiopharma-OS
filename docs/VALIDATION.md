# Validación física del Yield Engine — ¹⁸O(p,n)¹⁸F

**Fecha:** 2026-07-17 · **Motor:** Yield Engine v0.1.0 · **Stopping:** CATIMA/ATIMA (pycatima 1.981)

## 1. Datos de entrada

| Dataset | Fuente | Versión |
|---|---|---|
| σ(E) ¹⁸O(p,n)¹⁸F | IAEA-NDS Medical Portal, ajuste Padé a 534 puntos EXFOR (χ²=4.6) | May-2021 |
| T½ ¹⁸F = 109.77(5) min | IAEA LiveChart / DDEP | 2021 |
| S(E) protones en H₂O / O₂ | CATIMA/ATIMA (GSI) | catima 1.7 |

## 2. Rendimiento a saturación, blanco gaseoso ¹⁸O (100 %)

Referencia: **Hess et al., Radiochim. Acta 89 (2001) 357–362** (EXFOR D4095), Tabla 4.

| E (MeV) | Motor (MBq/µA) | Hess 2001 (MBq/µA) | Desviación |
|---|---|---|---|
| 6.0 | 2343 | 2209 | +6.1 % |
| 10.0 | 6713 | 6871 | −2.3 % |
| 14.0 | 10601 | 11004 | −3.7 % |
| 18.0 | 13091 | 13454 | −2.7 % |
| 20.0 | 13847 | 14228 | −2.7 % |

**Desviación máxima 6.1 %**, dentro de la incertidumbre experimental de las
secciones eficaces (7–18 % según Hess). Criterio de aceptación del MVP (<8 %): **cumplido**.

## 3. Verificación del stopping power (Bethe-Bloch)

| E (MeV) | ATIMA (MeV·cm²/g) | Bethe-Bloch analítico | Estado |
|---|---|---|---|
| 10.0 | 47.0 | ≈ 45.7 | OK (+2.8 %) |
| 18.0 | 28.8 | — | rango CSDA 0.344 g/cm² ≈ NIST PSTAR |

## 4. Caso típico de producción (H₂¹⁸O líquido)

Parámetros: 16.5 MeV · 37 µA · 60 min · enriquecimiento 99.5 %.

| Magnitud | Valor |
|---|---|
| Rendimiento a saturación | 9.34 GBq/µA |
| Factor de saturación (60 min) | 0.3154 |
| **Actividad EOB** | **108.9 ± 8.1 GBq (≈ 2.94 Ci)** |
| Incertidumbre relativa combinada | 7.4 % |

Coherente con el rango industrial de ciclotrones de 16–18 MeV (2–4 Ci EOB/h).

## 5. Validación ¹¹C — ¹⁴N(p,α)¹¹C en blanco N₂

Datos: σ(E) IAEA-NDS Medical Portal (May-2021, 76 puntos, pico 249 mb @ 7.5 MeV);
T½ ¹¹C = 20.364(14) min (LiveChart/DDEP); S(E) ATIMA para N₂.

Referencia: rendimientos a saturación calculados por la propia IAEA a partir
de la misma σ(E) recomendada (columna GBq/µA de la tabla de rendimientos).

| E (MeV) | Motor (GBq/µA) | IAEA (GBq/µA) | Desviación |
|---|---|---|---|
| 8.0 | 1.68 | 1.76 | −4.4 % |
| 10.0 | 2.66 | 2.71 | −1.8 % |
| 12.0 | 4.00 | 4.08 | −2.0 % |
| 16.0 | 7.37 | 7.47 | −1.3 % |
| 20.0 | 9.74 | 9.84 | −1.0 % |

**Desviación máxima 4.4 %** — criterio del MVP (<8 %): **cumplido**.

Caso típico (16 MeV, 30 µA, 30 min): **EOB = 141.5 ± 13.9 GBq** — coherente
con producciones industriales de ¹¹C (100–150 GBq EOB).

## 6. Validación ¹⁵O y ⁶⁸Ga

Datos: σ(E) IAEA-NDS (May-2021): ¹⁵N(p,n)¹⁵O 388 puntos (pico 192 mb),
⁶⁸Zn(p,n)⁶⁸Ga 60 puntos (pico 877 mb). T½: ¹⁵O = 122.24(16) s,
⁶⁸Ga = 67.71(9) min. S(E) ATIMA para ¹⁵N₂ y ⁶⁸Zn.

Referencia: rendimientos a saturación de la propia IAEA (columna GBq/µA,
convertida de MBq/µA en la tabla de ⁶⁸Ga).

| Reacción | E (MeV) | Motor | IAEA | Desviación |
|---|---|---|---|---|
| ¹⁵N(p,n)¹⁵O | 8.0 | 1.62 GBq/µA | 1.68 | −3.5 % |
| ¹⁵N(p,n)¹⁵O | 16.0 | 5.87 | 6.00 | −2.1 % |
| ¹⁵N(p,n)¹⁵O | 20.0 | 7.62 | 7.73 | −1.4 % |
| ⁶⁸Zn(p,n)⁶⁸Ga | 8.0 | 1.86 GBq/µA | 1.94 | −4.0 % |
| ⁶⁸Zn(p,n)⁶⁸Ga | 16.0 | 14.56 | 15.00 | −2.9 % |
| ⁶⁸Zn(p,n)⁶⁸Ga | 20.0 | 17.00 | 17.50 | −2.9 % |

Nota física: se detectó que el stopping power másico de ¹⁴N₂ y ¹⁵N₂ difiere
~7 % (efecto de masa molar por gramo); el blanco ¹⁵N₂ usa su propio material
ATIMA — corrección incorporada en v0.3.0.

## 7. Burnup Engine

Modelo analítico verificado por límites: k→0 recupera A_sat·I·(1−e^{−λt});
λ=k usa la forma límite A_sat·I·λt·e^{−λt}. Caso típico ¹⁸F (37 µA, spot
1 cm², σ_b=500 mb): k=1.15×10⁻¹⁰ s⁻¹, depleción 4×10⁻⁷, pérdida EOB 0.002 %
— confirma que el quemado global por lote es despreciable en ciclotrones
médicos; el efecto local (pico de Bragg) queda para la versión 2D-FEM.

## 8. Propagación de incertidumbres

Componentes (1σ, cuadratura): σ(E) evaluada IAEA (4–25 % según energía,
ponderada por el integrando) + stopping 3 % + corriente 1 %.

## 9. Trazabilidad

Cada respuesta del API incluye `dataset_id` y `stopping_source`; el CSV de
secciones eficaces lleva SHA-256 registrado en `data/datasets.json`.
