#!/usr/bin/env python3
"""Prueba teórica REAL del Physics Twin (sin ciclotrón operativo).

Ejecuta cálculos reales del código de producción del Yield Engine —
integración numérica de σ(E) recomendada por la IAEA con stopping powers
ATIMA/pycatima — y los contrasta con las tablas de referencia del
IAEA-NDS Medical Portal (May-2021). Además ejecuta los runtimes
científicos externos cuando están disponibles en el entorno
(TALYS / OpenGATE-Geant4 / ElmerFEM): cálculo real de σ(E) con TALYS,
transporte Monte Carlo real con Geant4 y caso FEM real con ElmerSolver.
Si alguno no está disponible se declara honestamente — nunca se simula.

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

# ---- 5. Runtimes científicos: ejecución REAL si están disponibles ----
def _cargar_talys_runner():
    # carga por ruta de archivo: el paquete "app" del Yield Engine ya
    # está en sys.modules y colisionaría con el de nuclear_data_service
    import importlib.util
    ruta = (Path(__file__).resolve().parents[1]
            / "services" / "nuclear_data_service" / "app"
            / "infrastructure" / "talys" / "talys_runner.py")
    spec = importlib.util.spec_from_file_location("talys_runner", ruta)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


runtimes: dict = {}

# 5a. TALYS real: sigma(E) 18O(p,n)18F vs dataset IAEA-2021 del repo
_talys_mod = _cargar_talys_runner()
_trunner = _talys_mod.TalysRunner()
talys_info: dict = {"integracion": "services/nuclear_data_service/app/"
                                   "infrastructure/talys/talys_runner.py",
                    "disponible": _trunner.available()}
if _trunner.available():
    try:
        workdir = Path("out/talys_f18")
        inp = _talys_mod.build_input("p", "o", 18, 8.0, 18.0, 0.5)
        rp = _trunner.run(workdir, inp, "rp009018.tot")
        puntos = _talys_mod.parse_rp_tot(rp)
        ref = []
        for line in (DATA_DIR / "cross_sections" / "o18_p_n_f18"
                     / "o18_p_n_f18_iaea2021.csv").read_text().splitlines():
            s = line.strip().strip('"')
            if not s or s.startswith("#") or s.startswith("energy"):
                continue
            e_str, sig_str, *_ = s.split(",")
            ref.append((float(e_str), float(sig_str)))
        sig_por_e = dict(puntos)
        desvs = []
        for e_ref, s_ref in ref:
            if not 8.0 <= e_ref <= 18.0:
                continue
            es = sorted(sig_por_e)
            e1 = max(x for x in es if x <= e_ref)
            e2 = min(x for x in es if x >= e_ref)
            sig = sig_por_e[e1] if e1 == e2 else (
                sig_por_e[e1] + (sig_por_e[e2] - sig_por_e[e1])
                * (e_ref - e1) / (e2 - e1))
            desvs.append(abs(sig - s_ref) / s_ref * 100)
        media = round(sum(desvs) / len(desvs), 1)
        talys_info.update({
            "ejecucion": "real",
            "puntos_sigma": len(puntos),
            "rango_mev": [puntos[0][0], puntos[-1][0]],
            "desviacion_media_abs_vs_iaea2021_pct": media,
            "referencia": "data/cross_sections/o18_p_n_f18/"
                          "o18_p_n_f18_iaea2021.csv (IAEA-NDS, Pade fit "
                          "a 534 puntos EXFOR)",
            "nota": ("desviacion tipica del modelo optico por defecto de "
                     "TALYS frente a datos evaluados; la cadena "
                     "determinista usa sigma(E) IAEA directamente")})
        print(f"  TALYS real: {len(puntos)} puntos sigma(E), desv. media "
              f"vs IAEA-2021 = {media}%")
    except Exception as exc:  # fallo real, reportado honestamente
        talys_info.update({"ejecucion": "fallo_real", "detalle": str(exc)})
        print(f"  TALYS disponible pero fallo: {exc}")
else:
    talys_info["motivo_no_disponible"] = "binario no encontrado (TALYS_CMD/PATH)"
    print("  TALYS: no disponible (declarado)")
runtimes["TALYS"] = talys_info

# 5b. OpenGATE/Geant4 real: transporte MC de protones 16 MeV en agua
_grunner = GateRunner()
gate_info: dict = {"integracion": "services/yield_engine/app/"
                                  "infrastructure/gate/",
                   "disponible": _grunner.check()}
if _grunner.check():
    try:
        import subprocess
        gate_dir = Path("out/gate_mc")
        gate_dir.mkdir(parents=True, exist_ok=True)
        sim_script = Path(__file__).with_name("gate_sim_minima.py")
        proc = subprocess.run(
            [sys.executable, str(sim_script), str(gate_dir.resolve())],
            capture_output=True, text=True, timeout=600)
        if proc.returncode != 0:
            raise RuntimeError(f"GATE rc={proc.returncode}: "
                               f"{proc.stderr[-400:]}")
        resultado = json.loads((gate_dir / "resultado_mc.json").read_text())
        gate_info.update({"ejecucion": "real", **resultado,
                          "nota": "transporte Geant4 real; edep medida con "
                                  "DoseActor, sin surrogate ni ajuste"})
        print(f"  GATE real: edep={resultado['edep_total_mev']:.1f} MeV "
              f"vs {resultado['edep_esperada_mev']:.1f} MeV "
              f"({resultado['desviacion_pct']:+.2f}%)")
    except Exception as exc:
        gate_info.update({"ejecucion": "fallo_real", "detalle": str(exc)})
        print(f"  OpenGATE disponible pero fallo: {exc}")
else:
    gate_info["motivo_no_disponible"] = ("opengate no importable "
                                         "(OPENGATE_PYTHON/PATH)")
    print("  OpenGATE: no disponible (declarado)")
runtimes["OpenGATE_Geant4"] = gate_info

# 5c. ElmerFEM real: caso termico del blanco con ElmerSolver
_erunner = ElmerRunner()
elmer_info: dict = {"integracion": "services/yield_engine/app/"
                                   "infrastructure/elmer/",
                    "disponible": _erunner.available()}
if _erunner.available():
    try:
        from app.infrastructure.elmer.elmer_case import (
            ElmerThermalCase, build_case)
        case_dir = Path("out/elmer_termico")
        caso_fem = ElmerThermalCase(
            beam_power_w=610.5, spot_radius_cm=1.5,
            target_thickness_cm=0.9, conductivity_w_cm_k=0.006,
            film_coeff_w_cm2_k=0.5, coolant_temp_k=293.15,
            beam_sigma_cm=0.5)
        build_case(case_dir, caso_fem)
        escalares = _erunner.run(case_dir)
        elmer_info.update({"ejecucion": "real",
                           "t_max_k": escalares[0],
                           "t_mean_k": escalares[1],
                           "caso": "blanco 610,5 W, haz gaussiano "
                                   "sigma=0,5 cm, conveccion h=0,5 W/cm2K"})
        print(f"  Elmer real: T_max={escalares[0]:.1f} K "
              f"T_mean={escalares[1]:.1f} K")
    except Exception as exc:
        elmer_info.update({"ejecucion": "fallo_real", "detalle": str(exc)})
        print(f"  Elmer disponible pero fallo: {exc}")
else:
    elmer_info["motivo_no_disponible"] = ("ElmerSolver no encontrado "
                                          "(ELMER_CMD/PATH)")
    print("  ElmerFEM: no disponible (declarado)")
runtimes["ElmerFEM"] = elmer_info
sec("runtimes_cientificos", runtimes)

out = Path("out/prueba_teorica_fisica.json")
out.parent.mkdir(exist_ok=True)
out.write_text(json.dumps(informe, ensure_ascii=False, indent=2))
print(f"\nInforme JSON: {out}")
