"""F58-multi — Lotes teóricos e2e para 11C, 68Ga y 64Cu (memoria: sin ciclotrón).

Generaliza el patrón canónico de F58 (EDS vol. III, 21.7):
EOB → Transfer → Reaction → Purification → Formulation → SterileFiltration →
EOS → QC → (despacho como recomendación).

Reglas canónicas:
- EOB con ProductionService/YieldCalculator + datasets IAEA versionados
  (n14_p_a_c11_iaea2021, zn68_p_n_ga68_iaea2021, ni64_p_n_cu64_iaea).
- λ desde la biblioteca nuclear versionada (decay/*.json), nunca tecleada.
- Eficiencias de etapa: supuestos declarados pendiente_fuente (49.11);
  para FDG ya existe F60 con fuente citada — estos radiosiótopos quedan
  honestamente en supuesto_declarado_pendiente_fuente.
- QC/liberación: nunca liberado (18.10/14.9); registro append-only ALCOA+.
"""
from __future__ import annotations

import json
import math
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

EVIDENCIA_DEF = Path("/mnt/agents/work/evidencia_v072")
YE = Path("/mnt/agents/work/rpos25/services/yield_engine")

# Escenarios teóricos DECLARADOS (no mediciones):
ESCENARIOS = {
    "C11": {
        "reaction_id": "n14_p_a_c11", "target_id": "n2_gas",
        "beam_mev": 16.0, "corriente_ua": 30.0, "t_irrad_min": 30.0,
        "decay_json": "c11.json", "producto": "11C",
        "etapas": [("transfer", 0.95, 3.0), ("reaction", 0.55, 20.0),
                   ("purification", 0.90, 10.0), ("formulation", 0.95, 5.0),
                   ("sterile_filtration", 0.92, 5.0)],
        "t_despacho_min": 60.0,
    },
    "GA68": {
        "reaction_id": "zn68_p_n_ga68", "target_id": "zn68",
        "beam_mev": 14.0, "corriente_ua": 25.0, "t_irrad_min": 60.0,
        "decay_json": "ga68.json", "producto": "68Ga",
        "etapas": [("transfer", 0.95, 5.0), ("reaction", 0.70, 15.0),
                   ("purification", 0.85, 12.0), ("formulation", 0.95, 5.0),
                   ("sterile_filtration", 0.92, 5.0)],
        "t_despacho_min": 60.0,
    },
    "CU64": {
        "reaction_id": "ni64_p_n_cu64", "target_id": "ni64",
        "beam_mev": 12.0, "corriente_ua": 20.0, "t_irrad_min": 120.0,
        "decay_json": "cu64.json", "producto": "64Cu",
        "etapas": [("transfer", 0.95, 10.0), ("reaction", 0.75, 45.0),
                   ("purification", 0.85, 30.0), ("formulation", 0.95, 10.0),
                   ("sterile_filtration", 0.92, 7.0)],
        "t_despacho_min": 180.0,
    },
}


def _lambda(decay_json: str) -> float:
    d = json.loads((YE / "data" / "decay" / decay_json).read_text())
    return math.log(2.0) / float(d["half_life_s"])


def correr_lotes(evidencia: Path = EVIDENCIA_DEF) -> dict:
    sys.path.insert(0, str(YE))
    from app.main import DATA_DIR
    from app.application.production_service import ProductionService
    from app.infrastructure.repositories.local_reaction_data import (
        LocalReactionDataProvider)
    from app.infrastructure.stopping.factory import build_stopping_provider

    service = ProductionService(
        stopping=build_stopping_provider(DATA_DIR / "stopping"),
        rxn=LocalReactionDataProvider(DATA_DIR))

    lotes = {}
    for clave, e in ESCENARIOS.items():
        lam = _lambda(e["decay_json"])
        res = service.compute(
            reaction_id=e["reaction_id"], target_id=e["target_id"],
            beam_energy_mev=e["beam_mev"], current_ua=e["corriente_ua"],
            irradiation_time_min=e["t_irrad_min"])
        eob = res.eob_activity_gbq
        t0 = datetime(2026, 10, 14, 8, 0, tzinfo=timezone.utc)
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
        eos = act
        t_desp = tl + timedelta(minutes=e["t_despacho_min"])
        act_desp = eos * math.exp(-lam * e["t_despacho_min"] * 60.0)
        lote = {
            "lote_id": f"{clave}-20261014-001",
            "estado": "ejemplo_teorico_completo_no_produccion_real",
            "irradiacion": {
                "reaccion": e["reaction_id"], "dataset": res.dataset_id,
                "beam_mev": e["beam_mev"], "corriente_ua": e["corriente_ua"],
                "t_irrad_min": e["t_irrad_min"],
                "saturation_yield_mbq_ua": res.saturation_yield_mbq_ua,
                "eob_gbq": round(eob, 3),
                "estado": "calculo_teorico_dataset_versionado"},
            "eob_hora": t0.isoformat(), "traza_etapas": traza,
            "eos_gbq": round(eos, 3), "eos_hora": tl.isoformat(),
            "despacho": {"hora": t_desp.isoformat(),
                         "actividad_gbq": round(act_desp, 3),
                         "estado": "recomendacion_no_liberacion (18.10)"},
            "qc": "pendiente_entorno (nunca simulado)",
            "liberacion": "no_liberada (18.10/14.9)",
        }
        lotes[clave] = lote

    out = Path(evidencia) / "fase58"
    out.mkdir(parents=True, exist_ok=True)
    (out / "lotes_multi_f58.json").write_text(
        json.dumps(lotes, ensure_ascii=False, indent=2), encoding="utf-8")
    with open(out / "registro_lotes.jsonl", "a", encoding="utf-8") as f:
        for l in lotes.values():
            f.write(json.dumps({"lote_id": l["lote_id"],
                                "eob_gbq": l["irradiacion"]["eob_gbq"],
                                "eos_gbq": l["eos_gbq"],
                                "ts": datetime.now(timezone.utc).isoformat()},
                               ensure_ascii=False) + "\n")
    return lotes


def main() -> int:
    for k, l in correr_lotes().items():
        print(f"{k}: EOB={l['irradiacion']['eob_gbq']}  EOS={l['eos_gbq']}  "
              f"despacho={l['despacho']['actividad_gbq']} GBq")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
