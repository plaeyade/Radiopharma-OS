#!/usr/bin/env python3
"""Prueba teórica REAL del Physics Twin (sin ciclotrón operativo).

Ejecuta cálculos reales del código de producción del Yield Engine —
integración numérica de σ(E) recomendada por la IAEA con stopping powers
ATIMA/pycatima — y los contrasta con las tablas de referencia del
IAEA-NDS Medical Portal (May-2021). Reporta además el estado HONESTO de
los runtimes científicos externos (TALYS / OpenGATE-Geant4 / Elmer):
presentes como integración real, no disponibles en este entorno (se
declara, nunca se simula).

Uso:
  PYTHONPATH=services/yield_engine python3 scripts/prueba_teorica_fisica.py
"""
from __future__ import annotations

import json
import math
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]
                       / "services" / "yield_engine"))

from app.domain import monte_carlo
from app.infrastructure.gate.gate_case import MonteCarloTargetCase
from app.infrastructure.gate.gate_runner import GateRunner
from app.infrastructure.elmer.elmer_runner import ElmerRunner
from app.main import DATA_DIR
from app.application.production_service import ProductionService
from app.infrastructure.repositories.local_reaction_data import (
    LocalReactionDataProvider)
from app.infrastructure.stopping.factory import build_stopping_provider

# Referencias canónicas:
# - F-18: expectativa validada del propio repo (test_yield_engine):
#   saturación ≈ 9,5 GBq/µA a 16,5 MeV en blanco líquido H2-18O.
# - C-11: tabla IAEA-NDS Medical Portal (May-2021), saturación GBq/µA
#   (misma σ(E) recomendada que usa el motor).
IAEA_C11 = {8.0: 1.76, 10.0: 2.71, 12.0: 4.08, 16.0: 7.47,
            20.0: 9.84}                                       # 14N(p,a)11C
F18_SAT_165_REF = 9.5  # GBq/µA a 16,5 MeV (referencia canónica del repo)

service = ProductionService(
    stopping=build_stopping_provider(DATA_DIR / "stopping"),
    rxn=LocalReactionDataProvider(DATA_DIR))

informe = {"generado_en": datetime.now(timezone.utc).isoformat(),
           "tipo": "prueba_teorica_fisica",
           "nota": ("cálculos reales del motor; referencias IAEA-NDS "
                    "Medical Portal May-2021; sin ciclotrón operativo no "
                    "existen datos reales de haz — esto NO los sustituye"),
           "secciones": {}}


def sec(nombre, datos):
    informe["secciones"][nombre] = datos
    print(f"\n== {nombre} ==")


# ---- 1. F-18: curva de saturación real + referencia canónica 16,5 MeV ----
filas_f18 = []
for e in (8.0, 12.0, 16.0, 16.5, 18.0):
    r = service.compute(reaction_id="o18_p_n_f18", target_id="h2_18o",
                        beam_energy_mev=e, current_ua=1.0,
                        irradiation_time_min=600.0)
    got = r.saturation_yield_mbq_ua / 1000.0
    filas_f18.append({"e_mev": e, "motor_gbq_ua": round(got, 3)})
    print(f"  E={e:>4} MeV  motor={got:6.3f} GBq/µA")
ref = next(f for f in filas_f18 if f["e_mev"] == 16.5)["motor_gbq_ua"]
desv = (ref - F18_SAT_165_REF) / F18_SAT_165_REF * 100.0
monotona = all(a["motor_gbq_ua"] <= b["motor_gbq_ua"]
               for a, b in zip(filas_f18, filas_f18[1:]))
print(f"  referencia canónica 16,5 MeV ≈ {F18_SAT_165_REF} GBq/µA → "
      f"desv={desv:+.1f}%  monótona={monotona}")
sec("rendimiento_saturacion_o18_p_n_f18", {
    "filas": filas_f18, "referencia_canonica_16_5": F18_SAT_165_REF,
    "desviacion_pct": round(desv, 1), "curva_monotona": monotona,
    "metodo": "integración numérica real σ(E)×(dE/dx)^-1 (ATIMA)"})

# ---- 2. C-11 vs tabla IAEA-NDS Medical Portal (May-2021) ----
filas = []
for e, refc in IAEA_C11.items():
    r = service.compute(reaction_id="n14_p_a_c11", target_id="n2_gas",
                        beam_energy_mev=e, current_ua=1.0,
                        irradiation_time_min=600.0)
    got = r.saturation_yield_mbq_ua / 1000.0
    desvc = (got - refc) / refc * 100.0
    filas.append({"e_mev": e, "motor_gbq_ua": round(got, 3),
                  "iaea_gbq_ua": refc, "desviacion_pct": round(desvc, 1)})
    print(f"  E={e:>4} MeV  motor={got:6.3f}  IAEA={refc:5.2f}  "
          f"desv={desvc:+.1f}%")
sec("rendimiento_saturacion_n14_p_a_c11", {
    "filas": filas,
    "desviacion_max_pct": max(abs(f['desviacion_pct']) for f in filas),
    "metodo": "integración numérica real σ(E)×(dE/dx)^-1 (ATIMA)"})

# ---- 3. Caso operativo F-18: EOB/EOS con decaimiento real ----
res = service.compute(reaction_id="o18_p_n_f18", target_id="h2_18o",
                      beam_energy_mev=16.5, current_ua=37.0,
                      irradiation_time_min=60.0)
sec("caso_operativo_f18", {
    "eob_gbq": res.eob_activity_gbq,
    "parametros": {"E": 16.5, "I_uA": 37.0, "t_min": 60.0},
    "nota": "EOB real del motor; EOS = EOB·2^(-Δt/109,77 min)"})
print(f"  EOB = {res.eob_activity_gbq:.3f} GBq  "
      f"(factor saturación {res.saturation_factor:.4f})")

# ---- 4. Interfaz Monte Carlo: validación y comparación real ----
caso = MonteCarloTargetCase()
incumplimientos = monte_carlo.validar_caso(caso)
conv = monte_carlo.comparar_con_determinista(
    edep_mev_per_history=13.2, current_ua=37.0,
    beam_power_determinista_w=610.5)
sec("monte_carlo_interfaz", {
    "validacion_caso_incumplimientos": incumplimientos,
    "comparacion_mc_vs_determinista": conv,
    "nota": ("la interfaz MC valida y compara con aritmética real; el "
             "transporte de historias requiere OpenGATE/Geant4 (ver "
             "estado de runtimes)")})
print(f"  caso válido: {not incumplimientos}; "
      f"potencia MC equivalente={conv['power_mc_w']:.1f} W vs "
      f"determinista={conv['power_determinista_w']} W "
      f"({conv['desviacion_pct']:+.1f}%)")

# ---- 5. Estado HONESTO de los runtimes científicos ----
def _estado_talys():
    # carga por ruta de archivo: el paquete "app" del Yield Engine ya
    # está en sys.modules y colisionaría con el de nuclear_data_service
    import importlib.util
    ruta = (Path(__file__).resolve().parents[1]
            / "services" / "nuclear_data_service" / "app"
            / "infrastructure" / "talys" / "talys_runner.py")
    spec = importlib.util.spec_from_file_location("talys_runner", ruta)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.TalysRunner().available()


runtimes = {
    "TALYS": {"integracion": "services/nuclear_data_service/app/"
                             "infrastructure/talys/talys_runner.py",
              "disponible": _estado_talys(),
              "motivo_no_disponible": "requiere compilación Fortran "
                                      "(gfortran) — sin root en sandbox"},
    "OpenGATE_Geant4": {"integracion": "services/yield_engine/app/"
                                       "infrastructure/gate/",
                        "disponible": GateRunner().check(),
                        "motivo_no_disponible": "wheel ~1 GB + datos Geant4;"
                                                " red del sandbox ~15 KB/s"},
    "ElmerFEM": {"integracion": "services/yield_engine/app/infrastructure/"
                                "elmer/elmer_runner.py",
                 "disponible": ElmerRunner().available(),
                 "motivo_no_disponible": "paquete apt sin root en sandbox"},
}
for k, v in runtimes.items():
    print(f"  {k}: integrado=SI  disponible_ahora={v['disponible']}  "
          f"({v['motivo_no_disponible']})")
sec("runtimes_cientificos", runtimes)

out = Path("out/prueba_teorica_fisica.json")
out.parent.mkdir(exist_ok=True)
out.write_text(json.dumps(informe, ensure_ascii=False, indent=2))
print(f"\nInforme JSON: {out}")
