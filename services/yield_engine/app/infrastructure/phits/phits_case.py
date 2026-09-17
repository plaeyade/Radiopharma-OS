# -*- coding: utf-8 -*-
"""Generador de casos PHITS para el búnker — Fase 33.

PHITS (Particle and Heavy Ion Transport code System, JAERI/QST) requiere
LICENCIA (gratuita, con formulario): el binario NO está instalado en el
entorno. Este módulo:

1. Genera el input deck COMPLETO del búnker (misma geometría declarada
   tipo OIEA que el caso Geant4 de Fase 32) con fuente de neutrones de
   espectro TALYS real (nspec*.tot) y [T-Track] mesh tally — listo para
   correr el día que llegue la licencia.
2. Reporta el estado honesto del runtime: `pendiente_licencia` mientras
   no exista el ejecutable (nunca simula su salida).

Qué aportará PHITS cuando esté: tally de malla nativo con reducción de
varianza implícita (weight windows), validación cruzada independiente del
tally Geant4, y mejor tratamiento de neutrones térmicos en concreto.
"""
from __future__ import annotations

import os
import shutil
from dataclasses import dataclass
from pathlib import Path

ESTADO_PENDIENTE = "pendiente_licencia_phits"


def phits_status() -> dict:
    """Estado honesto del runtime PHITS (nunca simula su salida)."""
    exe = os.environ.get("PHITS_CMD") or shutil.which("phits")
    if exe:
        return {"estado": "disponible", "ejecutable": exe}
    return {
        "estado": ESTADO_PENDIENTE,
        "ejecutable": None,
        "que_falta": ("licencia PHITS (JAERI/QST — gratuita con formulario "
                      "institucional) + binario + bibliotecas de datos JENDL"),
        "que_aporta": ("tally de malla nativo con weight-windows (mejor "
                       "estadística en muros gruesos), validación cruzada "
                       "del tally Geant4 del búnker (Fase 32)"),
        "deck_listo": "generador implementado — phits_case.build_phits_case()",
    }


_DECK = """[ T i t l e ]
Bunker ciclotron no autoblindado (geometria declarada tipo OIEA) - Radiopharma OS Fase 33
Fuente: espectro TALYS real {SPEC} | generado por phits_case.py - no editar a mano

[ P a r a m e t e r s ]
   icntl  = 0
   maxcas = {NCAS}
   maxbch = 10
   seed   = {SEED}
   Emin(1) = 1.0e-9

[ S o u r c e ]
<source> = 1
   s-type = 1
   proj   = neutron
   dir    = iso
   x0 = 0.0   y0 = 0.0   z0 = 0.0
   e-type = 2
{SPEC_LINES}

[ M a t e r i a l ]
* Concreto ordinario (composicion declarada pendiente de la real de la
  instalacion - baritado vs ordinario cambia el blindaje)
MAT[1]
 H  -0.006  O  -0.500  Si -0.320  Ca -0.080  Al -0.040  Fe -0.020  Na -0.020  Mg -0.014

[ S u r f a c e ]
* bloque exterior de concreto 12 x 10 x 6 m (cm en PHITS)
 10 RPP -600.0 600.0 -500.0 500.0 -300.0 300.0
* boveda interior 6 x 6 x 4 m
 20 RPP -300.0 300.0 -300.0 300.0 -200.0 200.0
* laberinto tramo 1 (corredor en +X, 1.2 m ancho)
 30 RPP 300.0 600.0 -300.0 -180.0 -200.0 -80.0
* laberinto tramo 2 (cambio de direccion +Y)
 40 RPP 600.0 720.0 -180.0 220.0 -200.0 -80.0
* mundo
 90 RPP -1100.0 1100.0 -1100.0 1100.0 -600.0 600.0

[ C e l l ]
 101  -1  2.35  +10 -20 -30 -40      $ concreto (muros, menos huecos)
 201   0        +20                  $ aire boveda
 202   0        +30                  $ aire laberinto 1
 203   0        +40                  $ aire laberinto 2
 901   0        -90 +10              $ aire exterior
 999  -1        +90                  $ fuera del mundo

[ T - T r a c k ]
  mesh   = xyz
  x-type = 2
    nx = 60
    xmin = -600.0   xmax = 600.0
  y-type = 2
    ny = 50
    ymin = -500.0   ymax = 500.0
  z-type = 2
    nz = 30
    zmin = -300.0   zmax = 300.0
  part   = neutron
  unit   = 1        $ 1/cm2/source
  axis   = eng
  file   = ttrack_bunker.out

[ E n d ]
"""


@dataclass(frozen=True)
class PhitsBunkerCase:
    """Configuración registrable del deck PHITS (19.24)."""
    spectrum_file: str           # nspec*.tot REAL de TALYS
    n_histories: int = 100_000
    seed: int = 20260918
    geometria: str = ("declarada tipo OIEA (bóveda 6x6x4 m, muros 2,0 m, "
                      "laberinto con cambio de dirección) — pendiente de "
                      "plano real y composición del concreto")


def _spectrum_lines(spectrum_file: str) -> str:
    """Espectro TALYS (E MeV, xs) → bloque e-type=2 de PHITS."""
    e, xs = [], []
    with open(spectrum_file) as fh:
        for line in fh:
            if line.startswith("#") or not line.strip():
                continue
            c = line.split()
            e.append(float(c[0]))
            xs.append(float(c[1]))
    if len(e) < 2:
        raise ValueError("espectro insuficiente")
    lines = ["    ne = %d" % len(e)]
    for i in range(0, len(e), 4):
        chunk_e = " ".join(f"{v:.4e}" for v in e[i:i + 4])
        chunk_x = " ".join(f"{v:.4e}" for v in xs[i:i + 4])
        lines.append(f"      e  = {chunk_e}")
        lines.append(f"      d  = {chunk_x}")
    return "\n".join(lines)


def build_phits_case(case_dir: str | Path, case: PhitsBunkerCase) -> Path:
    """Escribe bunker_phits.inp + case.json (deck listo para la licencia)."""
    case_dir = Path(case_dir)
    case_dir.mkdir(parents=True, exist_ok=True)
    deck = _DECK.replace("{SPEC}", case.spectrum_file) \
                .replace("{NCAS}", str(case.n_histories)) \
                .replace("{SEED}", str(case.seed)) \
                .replace("{SPEC_LINES}", _spectrum_lines(case.spectrum_file))
    (case_dir / "bunker_phits.inp").write_text(deck)
    import json
    (case_dir / "case.json").write_text(json.dumps(case.__dict__, indent=2))
    return case_dir / "bunker_phits.inp"
