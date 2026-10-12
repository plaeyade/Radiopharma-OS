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
