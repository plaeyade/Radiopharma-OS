"""Calificación DQ/IQ/OQ/PQ (Informe 14.9).

Cada componente del sistema debe superar las etapas de calificación:

  - **DQ** (Design Qualification): verificación del diseño — se
    documenta contra los documentos canónicos (Informe + EDS) y las
    referencias de capítulo presentes en el código;
  - **IQ** (Installation Qualification): verificación de instalación —
    versiones, dependencias, integridad de datos y artefactos;
  - **OQ** (Operational Qualification): verificación funcional — casos
    operativos definidos ejecutados contra los motores reales con
    resultados esperados conocidos;
  - **PQ** (Performance Qualification): verificación bajo condiciones
    reales — honestamente no iniciada (requiere entorno real).

Uso:  python pipelines/qualification.py [--out qualification.json]
Exit: 0 si DQ+IQ+OQ pasan; 1 en caso contrario. PQ nunca se declara.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import platform
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _ahora() -> str:
    return datetime.now(timezone.utc).isoformat()


def _run_py(servicio: str, codigo: str, timeout: int = 300) -> dict:
    proc = subprocess.run([sys.executable, "-c", codigo],
                          cwd=ROOT / "services" / servicio,
                          capture_output=True, text=True,
                          env={**os.environ, "PYTHONPATH": "."},
                          timeout=timeout)
    if proc.returncode != 0:
        lineas = proc.stderr.strip().splitlines()
        raise RuntimeError(f"{servicio}: "
                           f"{lineas[-1] if lineas else proc.returncode}")
    return json.loads(proc.stdout.strip().splitlines()[-1])


# --------------------------------------------------------------------- DQ
def dq() -> dict:
    """Verificación del diseño contra los documentos canónicos."""
    checks = []
    docs = {"Informe": "Informe_RadiopharmaOS_v2.0_Digital_Twins.docx",
            "EDS": "ESPECIFICACIÓN TÉCNICA DEL MVP INDUSTRIAL.docx",
            "SEH": "Software Engineering Handbook (SEH).docx"}
    upload = Path("/mnt/agents/upload")
    for nombre, fichero in docs.items():
        p = upload / fichero
        ok = p.is_file() and p.stat().st_size > 100_000
        checks.append({"nombre": f"documento_canonico_{nombre.lower()}",
                       "ok": ok,
                       "detalle": f"{fichero} "
                                  f"({p.stat().st_size if ok else 0} B)"})
    # trazabilidad diseño→código: referencias de capítulo en servicios
    refs = 0
    for py in ROOT.glob("services/*/app/**/*.py"):
        texto = py.read_text(encoding="utf-8", errors="ignore")
        refs += texto.count("(cap.") + texto.count("cap. 1") \
            + texto.count("(EDS") + texto.count("18.")
    checks.append({"nombre": "trazabilidad_diseno_codigo",
                   "ok": refs > 100,
                   "detalle": f"{refs} referencias a capítulos canónicos "
                              "en el código de los servicios"})
    return {"etapa": "DQ", "ok": all(c["ok"] for c in checks),
            "checks": checks,
            "nota": "verificación del diseño (14.9): documentos canónicos "
                    "presentes y trazabilidad capítulo→código"}


# --------------------------------------------------------------------- IQ
def iq() -> dict:
    """Verificación de instalación (14.9)."""
    checks = []
    v = platform.python_version()
    checks.append({"nombre": "python", "ok": v.startswith("3.12"),
                   "detalle": f"Python {v}"})
    deps = ["fastapi", "pydantic", "numpy", "scipy", "httpx", "jwt",
            "sqlalchemy", "asyncua", "uvicorn", "pytest"]
    faltan = [d for d in deps if importlib.util.find_spec(d) is None]
    checks.append({"nombre": "dependencias", "ok": not faltan,
                   "detalle": "todas presentes" if not faltan
                              else f"faltan: {faltan}"})
    # integridad de los datos científicos instalados
    datos = ROOT / "services" / "yield_engine" / "data"
    ficheros = list(datos.rglob("*.json")) + list(datos.rglob("*.txt")) \
        + list(datos.rglob("*.csv"))
    checks.append({"nombre": "datos_cientificos_instalados",
                   "ok": len(ficheros) >= 3,
                   "detalle": f"{len(ficheros)} ficheros de datos en "
                              "yield_engine/data"})
    # servicios importables (instalación del código)
    importables = True
    detalle = []
    for srv in ["nuclear_data_service", "yield_engine",
                "data_lake_service", "auth_service", "qc_engine",
                "telemetry_service", "process_service", "surrogate_service"]:
        proc = subprocess.run(
            [sys.executable, "-c", "import app.main"],
            cwd=ROOT / "services" / srv, capture_output=True, text=True,
            env={**os.environ, "PYTHONPATH": "."}, timeout=120)
        if proc.returncode != 0:
            importables = False
            detalle.append(f"{srv}: FALLO")
        else:
            detalle.append(f"{srv}: ok")
    checks.append({"nombre": "servicios_importables", "ok": importables,
                   "detalle": "; ".join(detalle)})
    return {"etapa": "IQ", "ok": all(c["ok"] for c in checks),
            "checks": checks,
            "nota": "verificación de instalación (14.9): entorno, "
                    "dependencias, datos y servicios"}


# --------------------------------------------------------------------- OQ
def oq() -> dict:
    """Verificación funcional: casos operativos con resultado conocido."""
    checks = []

    def caso(nombre: str, servicio: str, codigo: str, prediccion) -> None:
        try:
            r = _run_py(servicio, codigo)
            ok, detalle = prediccion(r)
            checks.append({"nombre": nombre, "ok": bool(ok),
                           "detalle": detalle})
        except Exception as exc:
            checks.append({"nombre": nombre, "ok": False,
                           "detalle": f"error: {exc}"})

    caso("oq_yield_eob_conocido", "yield_engine", """
import json
from app.application.production_service import ProductionService
from app.infrastructure.repositories.local_reaction_data import LocalReactionDataProvider
from app.infrastructure.stopping.factory import build_stopping_provider
svc = ProductionService(stopping=build_stopping_provider('data/stopping'),
                        rxn=LocalReactionDataProvider('data'))
r = svc.compute('o18_p_n_f18', 'h2_18o', 16.5, 37.0, 60.0)
print(json.dumps({'eob': r.eob_activity_gbq}))
""", lambda r: (r["eob"] > 1.0, f"EOB 16.5MeV/37µA/60min = "
                                f"{r['eob']:.3f} GBq > 1 GBq"))

    caso("oq_decaimiento_exacto", "qc_engine", """
import json
from app.domain.decay_physics import decay_correction
print(json.dumps({'a': decay_correction(100.0, 109.77, 109.77, False)}))
""", lambda r: (abs(r["a"] - 200.0) < 1e-9,
                f"retro-corrección a T½ = {r['a']:.10f} (esperado 200)"))

    caso("oq_qc_release_conforme", "qc_engine", """
import json
from app.application.qc_release_service import QcReleaseService
svc = QcReleaseService()
protos = svc.catalog.list_protocols()
p = protos[0]
res = svc.release(p.protocol_id, {
    'identidad_radionucleidica': 109.77,
    'pureza_radionucleidica_pct': 99.9,
    'pureza_radioquimica_pct': 98.5,
    'ph': 7.0, 'apariencia_score': 1.0, 'actividad_gbq': 20.0,
    'k222_ppm': 10.0, 'acetonitrilo_ppm': 100.0},
    operador='oq', motivo='OQ 14.9')
print(json.dumps({'protocolos': len(protos),
                  'recomendacion': res.recomendacion}))
""", lambda r: (r["protocolos"] >= 1
                and r["recomendacion"] == "liberacion",
                f"QC release conforme → {r['recomendacion']} "
                f"({r['protocolos']} protocolos, cap. 25)"))

    caso("oq_synthesis_e2e", "process_service", """
import json
from app.application.synthesis_service import SynthesisService
svc = SynthesisService()
r = svc.synthesis_e2e(reaction_id='fdg_18f_synthesis',
                      purification_id='fdg_18f_purification',
                      formulation_id='fdg_18f_formulation',
                      eob_activity_gbq=37.0, operador='oq', motivo='OQ 14.9',
                      lote='OQ-1')
act = r['final_activity_gbq']
print(json.dumps({'actividad': act}))
""", lambda r: (r["actividad"] > 0,
                f"cadena RE→PU→FE operativa: {r['actividad']:.3f} GBq "
                "finales (caps. 22-24)"))

    caso("oq_surrogate_inferencia", "surrogate_service", """
import json
from app.application.surrogate_service import SurrogateService
svc = SurrogateService()
svc.train_yield_surrogate(version='oq-1', responsable='oq')
r = svc.infer('yield_sat_f18', 'oq-1', 12.0, usuario='oq', request_id='oq')
print(json.dumps({'prediccion': r['prediccion_yield_sat_mbq_ua']}))
""", lambda r: (r["prediccion"] > 1000.0,
                f"inferencia surrogate en dominio: {r['prediccion']:.1f} "
                "MBq/µA @ 12 MeV (cap. 20)"))

    caso("oq_inventario_decaimiento", "process_service", """
import json
from datetime import datetime, timedelta, timezone
from app.domain.inventory import InventoryService, LoteRadiactivo
inv = InventoryService()
t0 = datetime.now(timezone.utc)
inv.registrar_lote(LoteRadiactivo(
    lote_id='OQ-INV', radiopharmaceutical='FDG', nuclide='F-18',
    half_life_min=109.77, actividad_gbq=37.0,
    referencia_temporal=t0.isoformat()), operador='oq', motivo='OQ')
stock = inv.stock_lote('OQ-INV', t0 + timedelta(minutes=109.77))
print(json.dumps({'a': stock['actividad_gbq']}))
""", lambda r: (abs(r["a"] - 18.5) < 1e-3,
                f"stock a T½ = {r['a']:.4f} GBq (esperado 18.5)"))

    return {"etapa": "OQ", "ok": all(c["ok"] for c in checks),
            "checks": checks,
            "nota": "verificación funcional (14.9): casos operativos con "
                    "resultado esperado sobre los motores reales"}


def construir_reporte() -> dict:
    etapas = [dq(), iq(), oq()]
    ok = all(e["ok"] for e in etapas)
    return {
        "reporte": "Calificación Radiopharma OS (Informe 14.9)",
        "fecha": _ahora(),
        "etapas": etapas + [{
            "etapa": "PQ", "ok": None, "checks": [],
            "nota": "Performance Qualification: verificación bajo "
                    "condiciones reales — no iniciada (requiere entorno "
                    "clínico real); el sistema nunca la declara superada"}],
        "veredicto": "calificado_dq_iq_oq" if ok else "no_calificado",
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=None)
    args = ap.parse_args()
    rep = construir_reporte()
    texto = json.dumps(rep, indent=1, ensure_ascii=False)
    if args.out:
        Path(args.out).write_text(texto, encoding="utf-8")
        print(f"reporte escrito en {args.out}")
    else:
        print(texto)
    return 0 if rep["veredicto"] == "calificado_dq_iq_oq" else 1


if __name__ == "__main__":
    raise SystemExit(main())
