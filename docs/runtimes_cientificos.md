# Runtimes científicos — instalación y operación (Fase 6, v0.72.0)

Los tres motores externos del Physics Twin están **integrados y probados con
ejecución real**. La plataforma funciona sin ellos (503/estado honesto), pero
con ellos la cadena completa — determinista IAEA + TALYS + Monte Carlo + FEM —
es operativa.

## Estado probado (batería `scripts/prueba_teorica_fisica.py`)

| Motor | Versión | Prueba real | Resultado |
|---|---|---|---|
| TALYS | 2.2 | σ(E) ¹⁸O(p,n)¹⁸F, 8–18 MeV | 21 puntos; desv. media 23,6 % vs IAEA-2021 (modelo óptico por defecto) |
| OpenGATE/Geant4 | 10.1.1 | 2000 protones 16 MeV en agua, DoseActor | edep 31 980,9 MeV vs 32 000,0 (−0,06 %) |
| ElmerFEM | 26.2 | HeatSolver axisimétrico, blanco 610,5 W gaussiano σ=0,5 cm | `ALL DONE`; T_max/T_mean vía SaveScalars |

## Localización de binarios (entorno de desarrollo/sandbox)

- Persistentes: `/mnt/agents/work/sci/` (TALYS + estructura + ElmerSolver + libs)
  y `/mnt/agents/work/sci_runtime/` (fuentes de restauración: wheels GATE,
  datasets Geant4, artefactos Elmer, toolchain).
- Ejecutables: el mount persistente no permite bit de ejecución → los binarios
  se copian a `/tmp/sci/bin/` en cada sesión (wrappers incluidos):

```sh
mkdir -p /tmp/sci/bin
cp /mnt/agents/work/sci/talys/bin/talys /tmp/sci/bin/talys.bin
cp /mnt/agents/work/sci/elmer_build/fem/src/ElmerSolver /tmp/sci/bin/ElmerSolver.bin
chmod +x /tmp/sci/bin/*
printf '#!/bin/sh\nexport TALYSDIR=/mnt/agents/work/sci/talys\nexec /tmp/sci/bin/talys.bin "$@"\n' > /tmp/sci/bin/talys
printf '#!/bin/sh\nexport LD_LIBRARY_PATH=/mnt/agents/work/sci/elmer_build/lib\nexport ELMER_HOME=/mnt/agents/work/sci/elmer_build/fem/src\nexec /tmp/sci/bin/ElmerSolver.bin "$@"\n' > /tmp/sci/bin/ElmerSolver
chmod +x /tmp/sci/bin/talys /tmp/sci/bin/ElmerSolver
```

OpenGATE se reconstruye 100 % offline desde las ruedas persistidas:

```sh
sh /mnt/agents/work/restore_persistent.sh   # idempotente; ALL_DONE al final
```

## Activación para servicios y batería

```sh
export TALYS_CMD=/tmp/sci/bin/talys
export ELMER_CMD=/tmp/sci/bin/ElmerSolver
# GATE: python con opengate importable (GateRunner usa OPENGATE_PYTHON o PATH)
GD=/tmp/gatepy/opengate_core/geant4_data
export GATEONRTD=1 GLIBC_TUNABLES="glibc.rtld.optional_static_tls=2000000"
export PYTHONPATH="/tmp/gatepy:$PYTHONPATH"
export LD_LIBRARY_PATH=/tmp/gatepy/opengate_core.libs
export G4LEDATA=$GD/G4EMLOW8.8 G4LEVELGAMMADATA=$GD/PhotonEvaporation6.1.2 \
       G4RADIOACTIVEDATA=$GD/RadioactiveDecay6.1.2 G4PARTICLEXSDATA=$GD/G4PARTICLEXS4.2 \
       G4PIIDATA=$GD/G4PII1.3 G4ABLADATA=$GD/G4ABLA3.3 G4INCLDATA=$GD/G4INCL1.3 \
       G4SAIDXSDATA=$GD/G4SAIDDATA2.0 G4ENSDFSTATEDATA=$GD/G4ENSDFSTATE3.0
```

En producción (Dockerfile de cada servicio) las imágenes llevan los binarios
dentro — no se copian a /tmp; las variables apuntan a rutas de imagen.

## Disciplina honesta (canónica)

- Sin binario/dataset, el endpoint responde 503 `sin_runtime` — nunca se simula
  una salida TALYS/MC/FEM.
- La cadena determinista de rendimiento usa σ(E) **evaluada IAEA** (19.12:
  prioridad de datos experimentales/evaluados sobre modelos). TALYS es segunda
  fuente teórica documentada con su desviación, no sustituto.
- Sin ciclotrón operativo: validación teórica con referencias publicadas;
  calibración con haz real (19.16) diferida y nunca bloqueante.
