#!/usr/bin/env python3
"""Demo E2E Fase 7: los 3 runtimes científicos reales SERVIDOS por la
plataforma vía HTTP (no funciones locales — servicios vivos).

Requiere los 8 servicios levantados con el entorno de runtimes
(ver docs/runtimes_cientificos.md):
  TALYS_CMD, ELMER_CMD, OPENGATE_PYTHON + G4* datasets, LD_LIBRARY_PATH.

Ejecuta contra HTTP real:
  1. NDS  :8001 /api/v1/talys/status y /cross-sections/compare/o18_p_n_f18
            → TALYS corre de verdad dentro del servicio (primera llamada
              tarda ~1 min: cálculo real; luego queda cacheado versionado).
  2. YE   :8002 /api/v1/elmer/status y /elmer/thermal/compare
            → pipeline yield→burnup→ElmerSolver real, cota conservadora.
  3. YE   :8002 /api/v1/mc/status y /mc/target (n_histories acotado)
            → OpenGATE/Geant4 real, métricas estadísticas 19.20 y
              comparación independiente con el determinista (19.14) —
              review_required honesto si la validación lo exige.

Escribe evidencia en out/demo_runtimes_e2e.json. Nada se simula: si un
servicio o runtime no responde, se registra el fallo real y exit != 0.

Uso:  python3 scripts/demo_runtimes_e2e.py [host]
"""
from __future__ import annotations

import json
import sys
import time
import urllib.request
import urllib.error
from pathlib import Path

HOST = sys.argv[1] if len(sys.argv) > 1 else "localhost"
NDS = f"http://{HOST}:8001/api/v1"
YE = f"http://{HOST}:8002/api/v1"


def _get(url: str, timeout: int = 240) -> dict:
    t0 = time.perf_counter()
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            return {"ok": True, "latencia_s": round(time.perf_counter() - t0, 1),
                    "datos": json.loads(r.read())}
    except Exception as exc:
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}


def _post(url: str, payload: dict, timeout: int = 480) -> dict:
    t0 = time.perf_counter()
    req = urllib.request.Request(
        url, data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return {"ok": True, "latencia_s": round(time.perf_counter() - t0, 1),
                    "datos": json.loads(r.read())}
    except urllib.error.HTTPError as exc:
        cuerpo = exc.read().decode(errors="replace")[:300]
        return {"ok": False, "error": f"HTTP {exc.code}: {cuerpo}"}
    except Exception as exc:
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}


def main() -> int:
    evidencia: dict = {"tipo": "demo_runtimes_e2e_fase7", "host": HOST,
                       "pasos": {}}
    fallos = 0

    def paso(nombre: str, resultado: dict) -> None:
        nonlocal fallos
        evidencia["pasos"][nombre] = resultado
        if not resultado.get("ok"):
            fallos += 1
            print(f"  {nombre}: FALLO REAL — {resultado['error']}")
        else:
            print(f"  {nombre}: OK ({resultado['latencia_s']} s)")

    print("== 1. TALYS servido por NDS ==")
    paso("talys_status", _get(f"{NDS}/talys/status"))
    paso("talys_compare_real",
         _get(f"{NDS}/cross-sections/compare/o18_p_n_f18"))
    if evidencia["pasos"]["talys_compare_real"].get("ok"):
        d = evidencia["pasos"]["talys_compare_real"]["datos"]
        print(f"     IAEA pico {d['iaea']['peak_sigma_mb']} mb @ "
              f"{d['iaea']['peak_energy_mev']} MeV | TALYS pico "
              f"{d['talys']['peak_sigma_mb']} mb @ "
              f"{d['talys']['peak_energy_mev']} MeV | "
              f"n={d['n_compared']} rms={d['rms_rel_deviation']}")

    print("== 2. ElmerFEM servido por Yield Engine ==")
    paso("elmer_status", _get(f"{YE}/elmer/status"))
    paso("elmer_thermal_compare_real", _post(f"{YE}/elmer/thermal/compare", {
        "reaction_id": "o18_p_n_f18", "target_id": "h2_18o",
        "irradiation_time_min": 60, "beam_energy_mev": 16.5,
        "current_ua": 37.0}))
    if evidencia["pasos"]["elmer_thermal_compare_real"].get("ok"):
        d = evidencia["pasos"]["elmer_thermal_compare_real"]["datos"]
        print(f"     T_peak FEM={d['t_peak_fem_k']:.1f} K vs reducido "
              f"{d['t_peak_reduced_k']:.1f} K | cota conservadora: "
              f"{d['fem_conservative_bound_ok']}")

    print("== 3. OpenGATE/Geant4 servido por Yield Engine ==")
    paso("mc_status", _get(f"{YE}/mc/status"))
    paso("mc_target_real", _post(f"{YE}/mc/target", {
        "reaction_id": "o18_p_n_f18", "target_id": "h2_18o",
        "beam_energy_mev": 16.5, "current_ua": 37.0,
        "n_histories": 2000, "n_batches": 3,
        "operador": "demo-fase7", "motivo": "E2E runtime real"}))
    if evidencia["pasos"]["mc_target_real"].get("ok"):
        d = evidencia["pasos"]["mc_target_real"]["datos"]
        c = d["comparacion_determinista"]
        print(f"     edep={d['edep_mev_per_history']:.2f} MeV/hist | "
              f"MC {c['power_mc_w']:.1f} W vs det "
              f"{c['power_determinista_w']} W "
              f"({c['desviacion_pct']:+.2f}%) | review_required="
              f"{d['review_required']} (honesto)")

    out = Path("out/demo_runtimes_e2e.json")
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(evidencia, ensure_ascii=False, indent=2))
    print(f"\nEvidencia: {out}  |  fallos: {fallos}")
    return 0 if fallos == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
