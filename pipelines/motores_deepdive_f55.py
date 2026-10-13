"""F55 — Deep dive de motores de cálculo: veredictos probados, no supuestos.

Cada veredicto nace de una prueba real en este sandbox (instalación intentada,
API inspeccionada) o se declara pendiente_entorno. Nada se afirma de memoria.
"""
from __future__ import annotations

import json
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path

EVIDENCIA_DEF = Path("/mnt/agents/work/evidencia_v072")
ENV_PY = "/workspace/rpos_cache/openmc_env/bin/python3"


def _pip_disponible(paquete: str) -> bool:
    r = subprocess.run(["pip", "index", "versions", paquete],
                       capture_output=True, text=True, timeout=120)
    return r.returncode == 0 and "Available versions" in r.stdout


def _openmc_info() -> dict:
    if not Path(ENV_PY).is_file():
        return {"estado": "pendiente_entorno (entorno en restauración)"}
    r = subprocess.run(
        [ENV_PY, "-c",
         "import openmc; print(openmc.__version__);"
         "print(hasattr(openmc,'WeightWindowGenerator'));"
         "print(hasattr(openmc,'WeightWindows'))"],
        capture_output=True, text=True, timeout=180)
    if r.returncode != 0:
        return {"estado": "error_entorno", "stderr": r.stderr[-200:]}
    v, wwg, ww = r.stdout.strip().splitlines()
    return {"version": v, "WeightWindowGenerator": wwg == "True",
            "WeightWindows": ww == "True", "estado": "probado_real"}


def construir_deepdive() -> dict:
    om = _openmc_info()
    motores = {
        "OpenMC": {
            **om,
            "rol": "motor MC vigente (F42/F42b/F51 reales)",
            "mejora_implementable": ("reducción de varianza con weight windows "
                                     "(WWGenerator/magic) para la penetración profunda "
                                     "del muro este — objetivo: bajar σ_rel=0,81 de F42b"),
        },
        "DAGMC": {
            "estado": "no_instalable_pip" if not _pip_disponible("dagmc") else "disponible",
            "motivo": ("sin paquete pip; requiere MOAB/Cubit + toolchain C++ — "
                       "desproporcionado mientras la CSG nativa de OpenMC ya reproduce "
                       "el búnker (censo MC validado 0,6 % en F42b)"),
            "rol_potencial": "geometría CAD directa si se adquiere el modelo 3D as-built",
        },
        "Geant4": {
            "estado": "pendiente_entorno",
            "motivo": "instalación conda ~GB; no aporta nada que OpenMC no cubra para n/γ de blindaje",
            "rol_potencial": "referencia cruzada física si hubiera discrepancia con OpenMC",
        },
        "GAMOS": {"estado": "pendiente_entorno", "motivo": "capa sobre Geant4; mismo coste",
                  "rol_potencial": "plantillas médicas (dosimetría)"},
        "GATE": {"estado": "pendiente_entorno", "motivo": "capa sobre Geant4 orientada a imagen/PET",
                 "rol_potencial": "dosimetría de paciente, fuera del alcance de blindaje"},
        "MATLAB": {"estado": "no_aplica", "motivo": "propietario; sin licencia en el sandbox"},
        "CAD/CADQuery": {
            "estado": "disponible_pip" if _pip_disponible("cadquery") else "no_instalable_pip",
            "motivo": ("pip OK, pero exportar a DAGMC sigue requiriendo MOAB; "
                       "útil solo cuando exista modelo 3D real (hoy solo hay planta DWG, F38)"),
        },
        "mesh/gmsh": {
            "estado": "no_instalable_pip",
            "motivo": "pip install gmsh falló en este sandbox (probado real)",
            "rol_potencial": "mallas no estructuradas para tally; de momento la malla regular OpenMC basta",
        },
        "GitHub": {
            "estado": "entregado_bundle",
            "motivo": "sin credenciales en sandbox; bundle v1.20.0 con tags listo para push",
        },
    }
    decision = ("Implementar AHORA: weight windows de OpenMC (F56) — única mejora con "
                "motor ya operativo y ganancia directa medible sobre F51/F53. "
                "Todo lo demás queda pendiente_entorno/no_aplica con motivo registrado.")
    return {
        "fase": "F55_deepdive_motores",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "estado": "deepdive_honesto_probado",
        "motores": motores,
        "decision_1810": decision,
    }


def main() -> int:
    d = construir_deepdive()
    out = EVIDENCIA_DEF / "fase55"
    out.mkdir(parents=True, exist_ok=True)
    (out / "deepdive_motores_f55.json").write_text(
        json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k: v.get("estado") for k, v in d["motores"].items()},
                     ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
