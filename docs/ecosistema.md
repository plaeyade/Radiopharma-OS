# Ecosistema: radiopharma-os y repos hermanos

radiopharma-os es el **gemelo digital de producción**: planeación de corridas, EOB/EOS, rendimientos, control de calidad, liberación, métricas y trazabilidad (ALCOA+). No contiene datos de una instalación concreta.

| Repo | Rol | Qué intercambia con radiopharma-os |
|---|---|---|
| GAMMA AI (maestro) | Clínica, pacientes, estudios, dosimetría, literatura | Demanda de dosis por radiofármaco → plan de producción |
| `plaeyade/Cyclotron-SIM` | Modelo CAD/físico del ciclotrón | `termino_fuente.json` (contrato `cyclotron-sim/termino_fuente@1`): energía, corrientes, doble haz, n/p, puertos |
| `plaeyade/Zumaya-AI` | Proyecto de instalación | Presupuesto operativo del blindaje: corriente máxima y µA·h/semana autorizados en la licencia |
| `plaeyade/RadShieldMx` | Cálculo analítico de blindajes | Casos de validación contra MC (Cyclotron-SIM) y proyectos (Zumaya-AI) |

## F90

`pipelines/ecosistema.py` lee el contrato del ciclotrón y verifica un plan semanal contra el presupuesto del blindaje. El número y la duración de las corridas son libres siempre que se cumplan dos límites: la corriente instantánea no excede la de diseño, y los µA·h/semana no exceden los autorizados. También reporta los neutrones por semana para trazabilidad de activación.

## Fases que salieron de este repo

- F86–F89 (blindajes Zumaya) viven en `Zumaya-AI/blindaje`.
- F81–F85 (integración KIUBE) quedan aquí y también en `Cyclotron-SIM/rpos_fases`.
