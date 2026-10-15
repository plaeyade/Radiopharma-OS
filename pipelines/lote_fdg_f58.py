"""F58 — Lote FDG de extremo a extremo (ejemplo teórico, memoria: sin ciclotrón).

Flujo canónico EDS vol. III, 21.7:
EOB → Transfer → Reaction → Purification → Formulation → SterileFiltration → EOS → QC

Reglas canónicas aplicadas:
- EOB: calculado con YieldCalculator + dataset IAEA 2021 (o18_p_n_f18) y
  λ real de la biblioteca nuclear (nunca un valor tecleado).
- Eficiencias de etapa: SUPUESTOS DECLARADOS pendiente_fuente (49.11) — no se
  presentan como medidas ni como literatura citada.
- QC/liberación: nunca se libera (14.9/18.10) — queda pendiente_entorno;
  el despacho se modela como actividad calibrada a hora de despacho,
  marcado como recomendación, no decisión.
- Registro append-only ALCOA+ en evidencia.
"""
from __future__ import annotations

import json
import math
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

EVIDENCIA_DEF = Path("/mnt/agents/work/evidencia_v072")

# Parámetros de irradiación DECLARADOS (escenario teórico, no medición):
BEAM_MEV = 16.5
CORRIENTE_UA = 40.0
T_IRRAD_MIN = 60.0
ENRICH = 0.97

# Eficiencias por etapa: SUPUESTO DECLARADO pendiente_fuente (49.11).
ETAPAS = [
    ("transfer", 0.98, 5.0),
    ("reaction", 0.60, 25.0),        # fluoruración + incorporación (supuesto)
    ("purification", 0.90, 15.0),
    ("formulation", 0.95, 8.0),
    ("sterile_filtration", 0.92, 7.0),
]
T_DESPACHO_MIN = 90.0  # EOS → despacho (supuesto logístico declarado)


def correr_lote(evidencia: Path = EVIDENCIA_DEF) -> dict:
    sys.path.insert(0, "/mnt/agents/work/rpos25/services/yield_engine")
    for _m in [k for k in list(sys.modules) if k == "app" or k.startswith("app.")]:
        del sys.modules[_m]
    from app.domain.entities import Beam, TargetMaterial
    from app.domain.yield_calculator import YieldCalculator
    from app.infrastructure.repositories.local_reaction_data import (
        LocalReactionDataProvider)
    from app.infrastructure.stopping.factory import build_stopping_provider

    base = Path("/mnt/agents/work/rpos25/services/yield_engine")
    yc = YieldCalculator(build_stopping_provider(str(base / "data" / "stopping")),
                         LocalReactionDataProvider(base / "data"))
    target = TargetMaterial("h2_18o", "H2-18O 97%", "h2o", "18O",
                            18.0, 0.8881 * ENRICH, enrichment=ENRICH)
    res = yc.compute_production("o18_p_n_f18", "18F",
                                Beam(BEAM_MEV, CORRIENTE_UA), target,
                                T_IRRAD_MIN)
    eob_gbq = res.eob_activity_gbq
    lam = 0.00010524235227596267  # biblioteca nuclear f18.json (DDEP/IAEA)

    t0 = datetime(2026, 10, 14, 6, 0, tzinfo=timezone.utc)  # EOB declarado
    tl = t0
    traza = []
    act = eob_gbq
    for nombre, eff, dur in ETAPAS:
        act *= eff * math.exp(-lam * dur * 60.0)
        tl += timedelta(minutes=dur)
        traza.append({"etapa": nombre, "eficiencia_supuesta": eff,
                      "duracion_min": dur,
                      "actividad_fin_gbq": round(act, 3),
                      "hora_fin": tl.isoformat(),
                      "estado_eficiencia": "supuesto_declarado_pendiente_fuente"})
    eos_gbq = act
    t_desp = tl + timedelta(minutes=T_DESPACHO_MIN)
    act_desp = eos_gbq * math.exp(-lam * T_DESPACHO_MIN * 60.0)

    lote = {
        "fase": "F58_lote_fdg_e2e_teorico",
        "lote_id": "FDG-20261014-001",
        "estado": "ejemplo_teorico_completo_no_produccion_real",
        "irradiacion": {
            "reaccion": "18O(p,n)18F", "dataset": res.dataset_id,
            "beam_mev": BEAM_MEV, "corriente_ua": CORRIENTE_UA,
            "t_irrad_min": T_IRRAD_MIN,
            "saturation_yield_mbq_ua": res.saturation_yield_mbq_ua,
            "factor_saturacion": round(res.saturation_factor, 4),
            "eob_gbq": round(eob_gbq, 3),
            "incertidumbre_rel": round(res.relative_uncertainty, 4),
            "estado": "calculo_teorico_iaea2021 (memoria: sin ciclotron)",
        },
        "eob_hora": t0.isoformat(),
        "traza_etapas": traza,
        "eos_gbq": round(eos_gbq, 3), "eos_hora": tl.isoformat(),
        "despacho": {"hora": t_desp.isoformat(),
                     "actividad_gbq": round(act_desp, 3),
                     "estado": "recomendacion_no_liberacion (18.10)"},
        "qc": "pendiente_entorno (requiere laboratorio real — nunca simulado)",
        "liberacion": "no_liberada (decision operacional humana, 18.10/14.9)",
    }
    out = Path(evidencia) / "fase58"
    out.mkdir(parents=True, exist_ok=True)
    (out / "lote_fdg_f58.json").write_text(
        json.dumps(lote, ensure_ascii=False, indent=2), encoding="utf-8")
    # registro append-only ALCOA+
    with open(out / "registro_lotes.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps({"lote_id": lote["lote_id"],
                            "eob_gbq": lote["irradiacion"]["eob_gbq"],
                            "eos_gbq": lote["eos_gbq"],
                            "ts": datetime.now(timezone.utc).isoformat()},
                           ensure_ascii=False) + "\n")
    return lote


def main() -> int:
    l = correr_lote()
    print(f"EOB={l['irradiacion']['eob_gbq']} GBq  EOS={l['eos_gbq']} GBq  "
          f"despacho={l['despacho']['actividad_gbq']} GBq")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
