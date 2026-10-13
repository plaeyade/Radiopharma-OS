# CHANGELOG — Radiopharma OS

Todas las versiones siguen semver. Cada fase tiene commit, tag y evidencia en
`/mnt/agents/work/evidencia_v072/` + página de evidencia (`/mnt/agents/output/app/index.html`).

## [1.0.0] — 2026-09-19 — Fase 36: CAPEX real + cierre
- `cost_engine.py`: `CAPEX_CICLOTRONES` con cotización real de fabricante
  IBA Cyclone KIUBE 300 — paquete IntegraLab ONE completo, €3 435 000 DDP
  Villahermosa (doc. 2025/8499 ver. 03.04), `estado=cotizacion_real_fabricante`;
  alcance exacto registrado — no es el ciclotrón solo, nunca se reparte ni extrapola.
- GE PETtrace 840 (130 µA + 2× FASTlab 2, 3,2 MDD USD):
  `declarado_usuario_pendiente_documento`. Resto del catálogo: `pendiente_cotizacion`
  (nunca se estima CAPEX). Conversión MXN: `pendiente_fuente`.
- Nuevos accesores `capex_ciclotrones()` / `capex_ciclotron(id)`.
- Informe de cierre del proyecto: 4 fases restantes (37 HP vs BERT, 38 geometría DWG,
  39 cotizaciones restantes, 40 IQ/OQ + congelado GxP) + propuestas fuera de canónicos.
- Suite: 1133 passed + 2 skipped. Tests nuevos: 6 (`test_capex_fase36.py`).
- Commit `f71fa9a6`, tag `v1.0.0`, web `1f94b15`.

## [0.99.0] — 2026-09-18 — Fase 35: estadística real del búnker + PyVista 3D
- 6 lotes MC independientes × 60 000 historias (360 000 total, 4,5× F32), FTFP_BERT,
  semillas 20260918+k·131. σ_rel medio 12,0 %/voxel activo (9 323 voxels);
  φ medio muros 3,756×10⁵ n/cm²/s (−2,4 % vs F32 — convergencia dentro de la estadística).
- Co-60 = 2,76 MBq tras 2500 pulsos (Bateman, `flujo_mc_real`).
- PyVista 0.49.0 / VTK 9.7.0 instalados (pendiente de entorno cumplido):
  render 3D off-screen del tally combinado y del mapa σ_rel.
- G4NDL 4.7.1 íntegro (16 092 archivos) persistido; bootstrap auto-curativo de datasets.
- Fix `mesh_heatmap.a_pyvista()` (ejes 1-D). Suite: 1127 + 2 skip. Commit `73c91027`.

## [0.98.0] — 2026-09-17 — Fase 34: GDML + modelo de haz + renders Cycles
- Escritor GDML de blancos; modelo de haz para 12 ciclotrones (energías con fuente citada).
- Renders Blender Cycles de blanco irradiado F-18 y Cu-64 con datos reales trazables
  (E_media del nspec real: 3,504 MeV / 1,501 MeV; 990 W / 660 W).
- Suite: 1115 + 2 skip. Commits `9800e88c`→`37dadf03`, web `cb88eac`.

## [0.97.0] — Fase 33
- Commit `6835182a`.

## [0.96.0] — Fase 32
- Búnker OIEA: primera corrida MC de fluencia/activación (80k historias, FTFP_BERT).
- Commit `1b58ee79`.

## [0.95.0] — Fase 31
- Base de la línea de mellizos digitales de blindaje.

---

### Pendientes declarados (honestidad de plataforma)
- Licencia PHITS; MCNP/SCALE; perfil de haz real (memoria permanente ID 3:
  sin ciclotrón a corto plazo — solo validación teórica, nunca bloquear por haz);
  calibración 19.16 diferida; tarifas CFE; tipo de cambio MXN.
- Validación HP vs BERT diferida a Fase 37 (decisión del usuario).

## v1.2.0 — Fase 41 (fuera de canónicos, prioridad 1): OpenMC tercer código — entorno + smoke
- OpenMC 0.16.0 (conda-forge; DAGMC sí, MPI no) instalado y verificado; procedimiento reproducible en evidencia fase41/bootstrap41.sh.
- Datos ENDF/B-VIII.0-NNDC HDF5: 33 isótopos (hormigón NIST + aire) descargados, validados con h5py + IncidentNeutron (3 corruptos detectados y redescargados: Ca40, H1, Si30), cross_sections.xml generado.
- Smoke test real: fuente puntual 2 MeV en esfera de hormigón r=100 cm, 20 000 historias/10 lotes, malla 20³ — 4 844 voxels con flujo, fuga 0,01230 ± 0,00022; statepoint + resultados JSON + render en evidencia_v072/fase41/.
- Declarado: sin S(α,β) térmico (paridad con gas libre Geant4); persistencia del env en tarball: mejor esfuerzo (recreable vía bootstrap en ~10 min).

## v1.3.0-rc1 — Fase 42 (parcial): port del búnker OIEA a OpenMC CSG
- Nuevo módulo services/yield_engine/app/infrastructure/openmc/bunker_openmc.py: geometría CSG 1:1 del caso F32/F35 (world 22×22×12 m, bloque 12×10×6 m, bóveda 6×6×4 m, laberinto de 2 tramos), materiales NIST G4_CONCRETE/G4_AIR con fuente citada (Geant4 NIST manager), espectro TALYS real (nspec_o18.tot), malla 110×110×60 idéntica, tally flux track-length.
- Prueba de equivalencia geométrica: censo Monte Carlo de materiales (400k puntos) contra volúmenes analíticos + 5 tests (services/yield_engine/tests/test_bunker_openmc_fase42.py, 5/5 verde).
- Hallazgo honesto: la geometría F32 declara "muros 2,0 m" pero el grosor real es x=3,0 m (lado laberinto), y=2,0 m, losas z=1,0 m — documentado en el test.
- PENDIENTE (declarado): lote piloto OpenMC del búnker — el entorno OpenMC se pierde por reciclaje del almacenamiento efímero del sandbox (se reintenta en segundo plano: build directo en /mnt con always_copy). Los 33 h5 ENDF/B-VIII.0 y cross_sections.xml SÍ están persistidos.

## v1.4.0 — Fase 45 (fuera de canónicos): cine de activación por componente (didáctico)
- Nuevo módulo services/yield_engine/app/domain/cine_activacion.py: máscaras por componente del búnker (6 componentes, sin solape, volumen MC = analítico <1 %), actividad Bateman vectorizada por voxel (forma cerrada; verificada contra ActivationEngine.actividad_tras_pulsos con rel_tol 1e-9), predominancia por isótopo con enfriamiento.
- 6 tests nuevos (services/yield_engine/tests/test_cine_activacion_fase45.py) — todos verdes.
- Evidencia fase45/: 3 videos reales (irradiación 1→2500 pulsos; enfriamiento 1 h→5 años; corte móvil en X) sobre tally HP real F37 (160k historias) + resumen JSON + póster.
- Resultado declarado: al apagar domina ²⁴Na (1,31e10 Bq, Na mayoritario NIST); a 30 días y 5 años domina ¹⁵²Eu (2,16e8 Bq); ⁶⁰Co 9,61e6 Bq. Trazas Co/Eu 1 ppm declaradas pendientes de fuente (49.11); suavizado σ=1 voxel solo visual, declarado.

## v1.4.1 — Regresión total + dureza de suite
- Suite canónica completa en VERDE: 1200 passed + 2 skipped (1150 servicios + 50 pipelines), estilo Makefile (por servicio, PYTHONPATH local). Incluye los 11 tests nuevos de F42/F45.
- Dureza: imports de los tests F42/F45 migrados al estilo canónico por-servicio (app.*), sin acoplar servicios; __init__.py del paquete openmc añadido.
- scripts/suite_canonica.sh: runner reproducible de la suite completa (evidencia para F40 OQ).
- Dependencias restauradas tras reciclaje del sandbox: lockfile + SimpleITK 2.5.6 (wheel verificado por tamaño exacto).

## v1.5.0 — Fase 46: visor 3D web del búnker + corrección honesta F45
- Visor 3D (app/visor3d.html, three.js r152 local): 5 mapas reales 110×110×60 (flujo BERT/HP + actividad Eu-152/Co-60/Na-24), 3 planos de corte con sliders, umbral, geometría alambre, modo cine web (irradiación 1→2500 pulsos y enfriamiento 0→5 años vía factor Bateman escalar por isótopo) y panel de actividad por componente en vivo.
- Evidencia fase46/exportar_visor3d.py: export uint8 log10 + meta.json.
- CORRECCIÓN (ALCOA+, detectada en F46): los totales por isótopo de F45 sumaban sobre toda la malla incluyendo aire; isotopo_predominante() ahora enmascara al concreto. Totales corregidos al apagar: Na-24 3,29e9 Bq, Eu-152 5,43e7 Bq, Co-60 2,41e6 Bq. Conclusiones de predominancia sin cambio; videos y póster F45 regenerados. Tests 11/11 (máscara de concreto añadida).

## v1.6.0 — Fase 43: comparación triple de tallies (BERT / HP / OpenMC)
- Nuevo módulo `yield_engine/app/domain/comparacion_triple.py`: comparación N patas sobre unión de voxels, Δ por historia vs referencia, diferencia simétrica mediana, desglose por componente del búnker (máscaras F45).
- 7 tests nuevos (`test_comparacion_triple_fase43.py`), estilo canónico de servicio.
- Evidencia real: BERT 360k vs HP 160k. Unión 18 318 voxels; comunes 9 284; ratio HP/BERT por historia ≈ 1,95 en las 6 componentes (+95 %…+113 %) — hallazgo abierto declarado para F44.
- Corrección documental: el bloque «comparación» de F37 usaba totales sin normalizar por historias; F43 lo sustituye por comparación por historia.
- Pata OpenMC/ENDF-B-VIII.0: pendiente_entorno (sandbox recicla el entorno; librería de 33 isótopos persistida).

## v1.7.0 — Fase 44: informe de validación cruzada (hallazgo F43 resuelto)
- Evidencia `fase44/informe_validacion_cruzada_f44.json`: verificación lote a lote (σ_rel ≤ 0,4 %), metadatos comprobados (mismo runner/actor/G4NDL íntegro), resolución: ratio ≈2,0 es física (dispersión térmica S(α,β) de FTFP_BERT_HP), no metadatos.
- Implicación: pata HP como referencia para activación de concreto (capturas térmicas).
- Pata OpenMC y Co-60 con φ OpenMC: pendiente_entorno declarado. Evidencia parcial 2/3 patas para F40/OQ.

## v1.8.0 — Fase 47: comparador KIUBE vs PETtrace
- Nuevo módulo `yield_engine/app/domain/comparador_ciclotrones.py`: fichas declarativas con fuente citada por campo (49.11), pendiente_fuente honesto, métricas derivadas declaradas (GBq/µA·2h).
- Fuentes: IBA PR 2018 (KIUBE 300: 18 MeV, 300 µA, 1110 GBq F-18/2h), GE DOC0776419 rev6 (PETtrace 840–890: 16,5/8,4 MeV, 60–160 µA), Eberl 2012 (rutina 160 µA dual, ~900 GBq).
- 4 tests nuevos. Material didáctico, no recomendación operativa (18.10).

## v1.9.0 — Fase 48: surrogate sobre tallies reales
- Nuevo módulo `yield_engine/app/domain/surrogate_tally.py`: regresión log (φ̂_HP desde φ_BERT + media local 3³), entrenada solo con tallies reales F35/F37.
- Validación holdout espacial (z<30 train / z≥30 test): R²(log)=0,937, mediana simétrica 9,0 %. Limitaciones declaradas (métrica optimista por correlación espacial; gap térmico irreducible F44).
- 5 tests nuevos. Surrogate didáctico — no sustituye MC.

## v1.10.0 — Fase 49: dashboard de evidencia
- `dashboard.html` + `dashboard_data/` (copia ALCOA+ de los JSON de F43/F44/F45/F47/F48): línea de versiones, tallies del búnker, Δ por componente, activación al apagar, métricas del surrogate y comparador de ciclotrones.
- Frontend estático sin backend — no persiste nada (declarado).

## v1.11.0 — Fase 38: plano real del búnker (DWG BIND) vs caso simulado
- Plano DWG real (19,8 MB, AutoCAD 2018) convertido a DXF (ODA 27.9, Xvfb headless) y persistido en evidencia.
- Nuevo módulo `yield_engine/app/domain/plano_bunker.py`: geometría real medida sobre plano (±0,1 m, estados honestos) + checklist de cumplimiento vs caso F32. 5 tests.
- Hallazgos: envolvente 9,71×15,49 m; muro oeste 2,11 m ✓; laberinto sur con 2 cambios de dirección (supera F32); sala ~5,9×4,7 m pendiente de verificación; ALARA: RESIDUOS RADIACTIVOS/WGHS/SUMINISTRO comparten muro este.
- F35-F45 re-etiquetadas honestamente: válidas como caso OIEA declarado, no as-built. Re-simulación as-built: pendiente_entorno.

## v1.12.0 — Fase 42b: caso OpenMC con geometría real BIND
- `bunker_openmc.py`: variante `geometria="bind_real"` con la geometría medida del plano (F38); caso OIEA intacto (ALCOA+).
- Muro oeste 2,11 m medido; sala estimada con cara oeste corregida por test de coherencia; altura z provisional declarada pendiente_verificacion.
- 6 tests nuevos (11/11 con regresión F42). Corrida: pendiente_entorno.

## v1.13.0 — Fase 39: cotizaciones de blindaje (2,5 vs 3,5 g/cm³)
- Nuevo módulo `yield_engine/app/domain/cotizaciones_blindaje.py`: ambas cotizaciones reales registradas con documento citado; verificación aritmética ✓ (JPG suma exacta; PDF subtotal+IVA exacto).
- Derivados declarados: ratio ×2,02 (sesgo IVA declarado), ~2,36 M USD (TC 17,71), espesor ~0,71× a igualdad de densidad área.
- 5 tests. Material de decisión, no recomendación operativa (18.10).

## v1.14.0 — Fase 42: piloto OpenMC real completado
- Bug CSG corregido: planos de vacío compartidos con las celdas (lost particles eliminados).
- Corrida real: 10k×10, leakage 0,00743±0,00021, 62 393 voxels con flujo; mapas .npy persistidos.
- Declarado: segfault recurrente del binario conda con 40k o ciertas semillas → estadística completa pendiente_entorno.

## v1.15.0 — Fase 42: barrido estadístico OpenMC real (3×10k) + comparación triple real cerrada + ítems diferidos
- Barrido de 6 semillas: 3 OK (20261013/20261537/20261668), 3 segfault conda (rc=139/255) declaradas; combinado 30k historias: 89 382 voxels activos, mapas .npy y σ entre semillas persistidos.
- Comparación triple 100 % real (BERT 360k / HP 160k / OpenMC 30k): unión 97 832 voxels; OpenMC Δ=−0,989 con caveat de unidades declarado; cobertura espacial OpenMC≈HP≫BERT (termalización).
- Verificación de alzados: hallazgo negativo honesto — el DWG no contiene cortes; z=4,0 m sigue provisional pendiente_verificacion (registrado en F38).
- Ítems diferidos: Dockerfile reproducible (pendiente de build real — sin daemon) y PWA (manifest + service worker) en la página de evidencia.

## v1.16.0 — Fase 40: OQ con evidencia real (oq_parcial_honesto)
- pipelines/oq_fase40.py + 5 tests en verde; regresión qualification 4/4 (DQ+IQ+OQ base = calificado_dq_iq_oq).
- F38 parcial (sin alzados en el DWG — hallazgo negativo), F39 ejecutado, F42 parcial (3/6 semillas, segfaults declarados; triple real cerrada).
- PQ nunca declarada (14.9). Nada fabricado: cada ítem declara su limitación.

## v1.17.0 — Fase 42b: corrida real OpenMC sobre geometría BIND (30k)
- 3 semillas × 10k (las 3 semillas sanas conocidas; patrón segfault ya declarado) → 509 768 voxels con flujo, σ rel. entre semillas 0,81.
- Re-simulación as-built deja de ser pendiente_entorno; z=4,0 m sigue provisional (sin alzados en el DWG).

## v1.18.0 — Fase 51: blindaje as-built (método TVL, geometría BIND)
- Censo MC de materiales valida bind_real (0,6 % vs analítico).
- Transmisión real del muro este (1,70 m): T=0,0282±0,0022 → TVL empírico ≈1,10 m (caveats declarados).
- Módulo blindaje_asbuilt.py (5 tests): escenario T=1e-4 → 4,12 m @2,5 / 2,95 m @3,5 g/cm³ (empírico) vs 0,76/0,55 m (Biggs 2010, contraste citado); objetivo real pendiente de ICRP 74 (pendiente_fuente); 18.10.

## v1.19.0 — F53 dosis as-built citada + F52 S(α,β) infraestructura + persistencia entorno MC
- F53: módulo dosis_asbuilt.py — h*(10)=385 pSv·cm² (²⁵²Cf bare, ISO 8529-1 vía PNNL-19273 t.47), P=20 µSv/sem (NCRP 151), Q_NS=5.9412e11 n/s (F32). Escenario muro este: 8.21e5 µSv/sem sin blindaje extra → 4.61 TVL adicionales. Inconsistencia de normalización del tally de malla (~3.6 órdenes vs ancla geométrica 1/4πr²) declarada no_demostrable_normalizacion_tally; los cocientes (transmisión/TVL) no se ven afectados. 5 tests.
- F52: soporte S(α,β) en bunker_openmc (add_s_alpha_beta, fuente declarada 49.11); tsl-HinH2O de ENDF/B-VIII.0 descargada de NNDC con MD5 oficial verificado (ecd503d3f8214f703e95e17cc947062c). Conversión a HDF5 requiere NJOY con n-001_H_001.endf (descarga 310 MB incompleta); openmc 0.16 from_endf no exporta HDF5 usable. Estado pendiente_entorno_parcial_honesto con pasos exactos en estado_sab_f52.json. 3 tests; 14/14 verde con regresión F42/F42b.
- Persistencia: entorno OpenMC troceado (3×100 MB) en sci_runtime/openmc_env_store con md5 verificado + restore_openmc.sh idempotente.
- Tabla h*(E) AMB74/ICRP 74 no descargable públicamente → pendiente_fuente registrado.

## v1.20.0 — F54 informe regulatorio integrado
- pipelines/informe_regulatorio_f54.py: expediente as-built que integra SOLO evidencia real registrada de 8 fases (F38/F39/F40/F42/F42b/F51/F52/F53), append-only ALCOA+, fuentes heredadas (49.11), PQ no_declarada_nunca (14.9), recomendación ≠ decisión (18.10). Síntesis citada: T=0,0282, TVL empírico 1,10 m, 4,61 TVL adicionales requeridos. 9 hallazgos abiertos declarados sin cierre artificial. 4 tests.

## v1.21.0 — F55 deep dive motores + F56 weight windows
- F55 (pipelines/motores_deepdive_f55.py): evaluación probada en sandbox de OpenMC/DAGMC/Geant4/GAMOS/GATE/MATLAB/CADQuery/gmsh/GitHub con veredictos honestos (probado_real, no_instalable_pip, pendiente_entorno, no_aplica, entregado_bundle). Decisión 18.10: weight windows OpenMC como única mejora implementable inmediata. 3 tests.
- F56 (evidencia fase56): generación de weight windows MAGIC REAL sobre el búnker BIND (malla grosera 22×22×12, ww_seed20261013.h5 preservado); explosión de tracks con malla fina acotada y declarada; API 0.16 documentada por prueba. Aplicación de WW: segfault determinista del binario conda (mismo patrón F42) → generacion_ok_aplicacion_no_demostrable_entorno con camino de desbloqueo registrado. Métrica de éxito: σ_rel(T muro este) < 0,078.

## v1.22.0 — F57 toolchain CAD→DAGMC operativo
- DAGMC 3.2.4 + MOAB 5.6.0 instalados vía conda-forge (micromamba persistido); mbconvert/check_watertight/overlap_check/uwuw_preproc verificados. Cadena real: casco búnker BIND (STL con dims F38) → h5m con roundtrip verificado. make_watertight sobre STL crudo: fallo declarado (vértices duplicados; ruta correcta = STEP vía CADQuery/gmsh, en descarga). OpenMC↔DAGMC requiere build desde fuente → pendiente_entorno. CUBIT propietario → no_aplica.

## v1.23.0 — F52 CORRIDA S(α,β) REAL + CADQuery/gmsh operativos
- F52 COMPLETADO: H-1 extraído por rangos HTTP del zip NNDC (límite 100 MiB del montaje sorteado sin descargar 310 MB); conversión NJOY2016 real → c_H_in_H2O.h5 (293,6 K única temperatura — la de 511 MB multi-temperatura no cabe en el montaje; declarado); corrida OpenMC con S(α,β) 3×10k sobre BIND real: T muro este = 0,04145 ± 0,00224 vs 0,0282 sin S(α,β) → la termalización aumenta la penetración 47 %. Derivados honestos: TVL 1,10→1,23 m; dosis F53 8,2e5→1,21e6 µSv/sem; TVL adicionales 4,61→4,78. El blindaje sin S(α,β) era optimista.
- CADQuery 2.8.0 y gmsh 4.15.2 instalados y verificados (wheels con sha256/md5 verificados tras detectar corrupción por reanudación CDN); STEP as-built del búnker generado (fase57). Sellado make_watertight: causa exacta registrada (file set not found — requiere estructura de conjuntos DAGMC).
- Persistencia: env DAGMC+NJOY troceado con md5 en sci_runtime/dagmc_env_store; c_H_in_H2O.h5 en openmc_data/endfb80/h5.
