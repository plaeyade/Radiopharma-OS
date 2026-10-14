"""F60 — Eficiencias FDG con fuente citada (cierre parcial de 49.11).

Hasta F58 las eficiencias de etapa eran supuestos declarados pendiente_fuente.
Aquí se incorpora el primer valor CON FUENTE CITADA, sin mezclarlo con los
supuestos: el lote FDG se recalcula con el rendimiento de síntesis publicado
y se mantiene el escenario de supuestos solo como comparación declarada.

Fuentes (verbatim en evidence_json):
- IAEA Pub1515 (Cyclotron Produced Radionuclides: Guidance on Facility
  Design...): "The production yield is reasonably good, typically >65%
  (corrected to EOB) within 25-45 minutes after collection of [18F]fluoride."
- Holler et al. 2022 (EJNMMI Radiopharmacy, GE FASTLab2): rendimiento
  radioquímico corregido por decaimiento 81.4 ± 4.6 % de EOB a EOS.
- Kim et al. 2004 (PubMed 15388116): 59.1 ± 5.1 % corregido por decaimiento.

Reglas canónicas: la cifra citada se marca fuente_citada (49.11); el
despacho sigue siendo recomendación, nunca liberación (18.10/14.9).
"""
from __future__ import annotations

import json
import math
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

EVIDENCIA_DEF = Path("/mnt/agents/work/evidencia_v072")
YE = Path("/mnt/agents/work/rpos25/services/yield_engine")

BEAM_MEV, CORRIENTE_UA, T_IRRAD_MIN, ENRICH = 16.5, 40.0, 60.0, 0.97
T_DESPACHO_MIN = 90.0

FUENTES = {
    "iaea_pub1515": {
        "rcy_eob_a_eos": 0.65,
        "cita": ("IAEA Pub1515: production yield typically >65% (corrected "
                 "to EOB) within 25-45 min after collection of [18F]fluoride"),
        "url": "https://www-pub.iaea.org/MTCD/Publications/PDF/Pub1515_web.pdf",
        "nota": "cota inferior conservadora (>65%); se usa 0.65"},
    "holler_2022": {
        "rcy_eob_a_eos": 0.814,
        "cita": ("Holler et al. 2022, GE FASTLab2: decay-corrected "
                 "radiochemical yield 81.4 ± 4.6% from EOB to EOS"),
        "url": "https://link.springer.com/article/10.1186/s41181-022-00154-3",
        "nota": "modulo comercial moderno; valor central"},
    "kim_2004": {
        "rcy_eob_a_eos": 0.591,
        "cita": ("Kim et al. 2004 (PMID 15388116): decay-corrected [18F]FDG "
                 "yield 59.1 ± 5.1%"),
        "url": "https://pubmed.ncbi.nlm.nih.gov/15388116/",
        "nota": "metodo con liquido ionico"},
}
T_SINTESIS_MIN = 35.0  # rango citado IAEA 25-45 min; valor declarado


def correr_f60(evidencia: Path = EVIDENCIA_DEF) -> dict:
    sys.path.insert(0, str(YE))
    from app.domain.entities import Beam, TargetMaterial
    from app.domain.yield_calculator import YieldCalculator
    from app.infrastructure.repositories.local_reaction_data import (
        LocalReactionDataProvider)
    from app.infrastructure.stopping.factory import build_stopping_provider

    yc = YieldCalculator(build_stopping_provider(str(YE / "data" / "stopping")),
                         LocalReactionDataProvider(YE / "data"))
    target = TargetMaterial("h2_18o", "H2-18O 97%", "h2o", "18O",
                            18.0, 0.8881 * ENRICH, enrichment=ENRICH)
    res = yc.compute_production("o18_p_n_f18", "18F",
                                Beam(BEAM_MEV, CORRIENTE_UA), target,
                                T_IRRAD_MIN)
    eob = res.eob_activity_gbq
    lam = 0.00010524235227596267  # f18.json (DDEP/IAEA)

    escenarios = {}
    for nombre, f in FUENTES.items():
        t0 = datetime(2026, 10, 14, 6, 0, tzinfo=timezone.utc)
        t_eos = t0 + timedelta(minutes=T_SINTESIS_MIN)
        eos = eob * f["rcy_eob_a_eos"] * math.exp(-lam * T_SINTESIS_MIN * 60.0)
        t_desp = t_eos + timedelta(minutes=T_DESPACHO_MIN)
        escenarios[nombre] = {
            "fuente": f["cita"], "url": f["url"], "nota": f["nota"],
            "estado_eficiencia": "fuente_citada (49.11)",
            "rcy_eob_a_eos": f["rcy_eob_a_eos"],
            "t_sintesis_min": T_SINTESIS_MIN,
            "eos_gbq": round(eos, 3), "eos_hora": t_eos.isoformat(),
            "despacho": {"hora": t_desp.isoformat(),
                         "actividad_gbq": round(
                             eos * math.exp(-lam * T_DESPACHO_MIN * 60.0), 3),
                         "estado": "recomendacion_no_liberacion (18.10)"},
        }

    salida = {
        "fase": "F60_eficiencias_fdg_fuente_citada",
        "estado": "parcial_citado_restantes_etapas_siguen_supuesto (49.11)",
        "irradiacion": {"dataset": res.dataset_id, "beam_mev": BEAM_MEV,
                        "corriente_ua": CORRIENTE_UA,
                        "t_irrad_min": T_IRRAD_MIN,
                        "eob_gbq": round(eob, 3)},
        "escenarios_citados": escenarios,
        "qc": "pendiente_entorno (nunca simulado)",
        "liberacion": "no_liberada (18.10/14.9)",
    }
    out = Path(evidencia) / "fase60"
    out.mkdir(parents=True, exist_ok=True)
    (out / "eficiencias_citadas_f60.json").write_text(
        json.dumps(salida, ensure_ascii=False, indent=2), encoding="utf-8")
    return salida


def main() -> int:
    s = correr_f60()
    for k, e in s["escenarios_citados"].items():
        print(f"{k}: EOS={e['eos_gbq']} GBq  despacho="
              f"{e['despacho']['actividad_gbq']} GBq  ({e['fuente'][:40]}...)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
