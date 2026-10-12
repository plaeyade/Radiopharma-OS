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
