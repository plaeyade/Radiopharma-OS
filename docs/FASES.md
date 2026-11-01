# Índice de fases (2026-11-01)

RadioPharma OS queda dedicado a la **producción**: lotes, EOB/EOS, control de calidad, métricas
y la planta como gemelo digital. Las fases que modelaban la física de la máquina, el búnker o el
edificio Zumaya se movieron al repo que les corresponde. Su código, sus pruebas y su historial
siguen recuperables en la rama `archivo/pre-depuracion-2026-10-31`.

## Numeración duplicada

Dos líneas de trabajo numeraron en paralelo F81–F85 y F90:

- la **re-corrida v0.35 del gemelo KIUBE**, de física;
- el **MVP de planta**.

Con el traslado, cada número queda una sola vez en RadioPharma OS. La integración con los repos
hermanos ya no lleva número de fase: `pipelines/ecosistema.py`, antes `ecosistema_f90.py`.

| Fase | En RadioPharma OS | Trasladada a |
| --- | --- | --- |
| F63 CSG vs DAGMC | — | Cyclotron-SIM `machines/iba_kiube/gemelo_fisico/pipelines/comparacion_csg_dagmc_f63.py` |
| F64 simulacro de jornada | `simulacro_jornada_f64.py` | — |
| F65 pérdida por gas | — | Cyclotron-SIM `gemelo_fisico/pipelines/perdida_gas_f65.py` |
| F66 mapa de vacío TPMC | — | Cyclotron-SIM `…/mapa_vacio_f66.py` |
| F67 Molflow vs TPMC | — | Cyclotron-SIM `…/molflow_xval_f67.py` |
| F68 órbitas centrales | — | Cyclotron-SIM `…/orbitas_centrales_f68.py` |
| F69 recalibrado KEY22 | — | Cyclotron-SIM `…/orbitas_recal_f69.py` |
| F70 MC máquina + búnker | — | Cyclotron-SIM `…/mc_maquina_bunker_f70.py` |
| F71 comparación triple | — | Cyclotron-SIM `…/comparacion_triple_f71.py` |
| F72 activación del gemelo | — | Cyclotron-SIM `…/activacion_gemelo_f72.py` |
| F73 unidades de tallies | — | Cyclotron-SIM `…/revision_unidades_f73.py` |
| F74 vacío analítico | — | Cyclotron-SIM `…/vacio_chiggiato_f74.py` |
| F75 inventario FEM | — | Cyclotron-SIM `…/inventario_fem_f75.py` |
| F76 homologación H*(10) | — | Cyclotron-SIM `…/homologacion_h10_f76.py` |
| F77 mallas del gemelo | — | Cyclotron-SIM `…/mallas_gemelo_f77.py` |
| F78 exterior | — | Cyclotron-SIM `…/exterior_f70_f78.py` |
| F79 propiedades FEM | — | Cyclotron-SIM `…/propiedades_fem_f79.py` |
| F80 matriz de trazabilidad | `matriz_trazabilidad_f80.py` | — |
| F81 ingesta kiube v0.35 | — | Cyclotron-SIM `…/ingesta_kiube_v035_f81.py` |
| F81 plantas BIND | — | Zumaya-AI `rpos_fases_zumaya/plantas_bind_f81.py` |
| F82 vacío v0.35 | — | Cyclotron-SIM `…/vacio_v035_f82.py` |
| F82 blindajes Zumaya | — | Zumaya-AI `rpos_fases_zumaya/blindajes_zumaya_f82.py` (lee `fuentes/`) |
| F83 blindaje v0.35 | — | Cyclotron-SIM `…/blindaje_v035_f83.py` |
| F83 blindaje ciclotrón Zumaya | — | Zumaya-AI `rpos_fases_zumaya/blindaje_ciclotron_f83.py` (lee `fuentes/`) |
| F84 DWSIM | `dwsim_service_f84.py` | — |
| F84 Molflow v0.35 | — | Cyclotron-SIM `…/molflow_v035_f84.py` |
| F85 NRTL y utilidades | `nrtl_utilidades_f85.py` | — |
| F85 cierre de blindaje | — | Cyclotron-SIM `…/cierre_blindaje_f85.py` |
| F86–F89 | `utilidades_completas_f86`, `stae_f87`, `beme_f88`, `iil_f89` | — |
| F90 FFSAE | `ffsae_f90.py` | — |
| F90 ecosistema | `ecosistema.py` (sin número) | — |
| F91–F97 | `malme_f91` … `facility_f97` | — |

Los módulos de física `gas_stripping`, `vacuum_tpmc` y `orbita_central`, antes en
`services/yield_engine/app/domain`, viajaron con sus fases a `gemelo_fisico/app/domain`. También
`data/kiube/` y `tools/` (`kiube_camara_molflow.py`, `sellar_dagmc.cpp`). La evidencia sigue bajo
`RPOS_AGENTS_ROOT`, así que las fases de RadioPharma OS que la leen (erske_f94, madse_f92, la
matriz F80) siguen funcionando.
