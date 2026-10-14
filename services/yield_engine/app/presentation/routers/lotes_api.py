"""F59 — Batch Manager API (EDS vol. III, 21.6).

Router FastAPI con trazabilidad de lote: operador, blanco, modulo de
sintesis y cadena EOB→EOS→despacho. Persistencia en registro JSONL
append-only ALCOA+ (nunca se edita ni borra; solo se anexa).

Reglas canónicas:
- Toda corrida es teórica (memoria: sin ciclotrón) — el campo `estado`
  lo declara explícitamente; nunca se simula producción real.
- QC/liberación nunca se completan en software: pendiente_entorno /
  no_liberada (18.10/14.9); el despacho es recomendación.
- Eficiencias: supuesto_declarado_pendiente_fuente salvo FDG citado (F60).
"""
from __future__ import annotations

import json
import math
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.main import DATA_DIR
from app.application.production_service import ProductionService

router = APIRouter(prefix="/lotes", tags=["batch-manager"])

REGISTRO_DEF = Path("/mnt/agents/work/evidencia_v072/fase58/registro_lotes.jsonl")

ESCENARIOS = {
    "F18": {"reaction_id": "o18_p_n_f18", "target_id": "h2_18o",
            "beam_mev": 16.5, "corriente_ua": 40.0, "t_irrad_min": 60.0,
            "half_life_s": 6586.2,
            "etapas": [("transfer", 0.98, 5.0), ("reaction", 0.60, 25.0),
                       ("purification", 0.90, 15.0),
                       ("formulation", 0.95, 8.0),
                       ("sterile_filtration", 0.92, 7.0)],
            "t_despacho_min": 90.0},
    "C11": {"reaction_id": "n14_p_a_c11", "target_id": "n2_gas",
            "beam_mev": 16.0, "corriente_ua": 30.0, "t_irrad_min": 30.0,
            "half_life_s": 1221.84,
            "etapas": [("transfer", 0.95, 3.0), ("reaction", 0.55, 20.0),
                       ("purification", 0.90, 10.0),
                       ("formulation", 0.95, 5.0),
                       ("sterile_filtration", 0.92, 5.0)],
            "t_despacho_min": 60.0},
    "GA68": {"reaction_id": "zn68_p_n_ga68", "target_id": "zn68",
             "beam_mev": 14.0, "corriente_ua": 25.0, "t_irrad_min": 60.0,
             "half_life_s": 4062.6,
             "etapas": [("transfer", 0.95, 5.0), ("reaction", 0.70, 15.0),
                        ("purification", 0.85, 12.0),
                        ("formulation", 0.95, 5.0),
                        ("sterile_filtration", 0.92, 5.0)],
             "t_despacho_min": 60.0},
    "CU64": {"reaction_id": "ni64_p_n_cu64", "target_id": "ni64",
             "beam_mev": 12.0, "corriente_ua": 20.0, "t_irrad_min": 120.0,
             "half_life_s": 45721.44,
             "etapas": [("transfer", 0.95, 10.0), ("reaction", 0.75, 45.0),
                        ("purification", 0.85, 30.0),
                        ("formulation", 0.95, 10.0),
                        ("sterile_filtration", 0.92, 7.0)],
             "t_despacho_min": 180.0},
}


class LoteRequest(BaseModel):
    isotopo: str
    operador: str = "no_declarado"
    blanco: str = "no_declarado"
    modulo_sintesis: str = "no_declarado"


def _registro() -> Path:
    return Path(os.environ.get("REGISTRO_LOTES", str(REGISTRO_DEF)))


def _calcular_lote(req: LoteRequest, service: ProductionService) -> dict:
    clave = req.isotopo.upper()
    if clave not in ESCENARIOS:
        raise HTTPException(400, f"isotopo no soportado: {req.isotopo}")
    e = ESCENARIOS[clave]
    lam = math.log(2.0) / e["half_life_s"]
    res = service.compute(reaction_id=e["reaction_id"],
                          target_id=e["target_id"],
                          beam_energy_mev=e["beam_mev"],
                          current_ua=e["corriente_ua"],
                          irradiation_time_min=e["t_irrad_min"])
    eob = res.eob_activity_gbq
    t0 = datetime.now(timezone.utc)
    tl, act, traza = t0, eob, []
    for nombre, eff, dur in e["etapas"]:
        act *= eff * math.exp(-lam * dur * 60.0)
        tl += timedelta(minutes=dur)
        traza.append({"etapa": nombre, "eficiencia_supuesta": eff,
                      "duracion_min": dur,
                      "actividad_fin_gbq": round(act, 3),
                      "hora_fin": tl.isoformat(),
                      "estado_eficiencia":
                          "supuesto_declarado_pendiente_fuente (49.11)"})
    n = sum(1 for _ in open(_registro())) + 1 if _registro().exists() else 1
    t_desp = tl + timedelta(minutes=e["t_despacho_min"])
    return {
        "lote_id": f"{clave}-{t0:%Y%m%d}-{n:03d}",
        "estado": "ejemplo_teorico_no_produccion_real",
        "trazabilidad": {"operador": req.operador, "blanco": req.blanco,
                         "modulo_sintesis": req.modulo_sintesis},
        "irradiacion": {"reaccion": e["reaction_id"],
                        "dataset": res.dataset_id,
                        "beam_mev": e["beam_mev"],
                        "corriente_ua": e["corriente_ua"],
                        "t_irrad_min": e["t_irrad_min"],
                        "eob_gbq": round(eob, 3)},
        "eob_hora": t0.isoformat(), "traza_etapas": traza,
        "eos_gbq": round(act, 3), "eos_hora": tl.isoformat(),
        "despacho": {"hora": t_desp.isoformat(),
                     "actividad_gbq": round(
                         act * math.exp(-lam * e["t_despacho_min"] * 60.0), 3),
                     "estado": "recomendacion_no_liberacion (18.10)"},
        "qc": "pendiente_entorno (nunca simulado)",
        "liberacion": "no_liberada (18.10/14.9)",
        "ts": t0.isoformat(),
    }


def build_router(service: ProductionService) -> APIRouter:
    @router.post("/teorico", status_code=201)
    def crear_lote_teorico(req: LoteRequest):
        lote = _calcular_lote(req, service)
        r = _registro()
        r.parent.mkdir(parents=True, exist_ok=True)
        with open(r, "a", encoding="utf-8") as f:
            f.write(json.dumps(lote, ensure_ascii=False) + "\n")
        return lote

    @router.get("")
    def listar_lotes():
        r = _registro()
        if not r.exists():
            return {"lotes": [], "estado": "registro_vacio"}
        lotes = [json.loads(l) for l in
                 r.read_text(encoding="utf-8").strip().splitlines()]
        return {"lotes": lotes, "n": len(lotes),
                "registro": "append_only_alcoa_plus"}

    @router.get("/escenarios")
    def escenarios():
        return {"isotopos": sorted(ESCENARIOS),
                "nota": "escenarios teoricos declarados; sin ciclotron"}

    return router
