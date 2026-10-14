"""F60-multi — Eficiencias con fuente citada para 11C, 68Ga y 64Cu (49.11).

Extiende F60 (FDG) al resto de isótopos del Batch Manager. Cada cifra va con
su fuente verbatim; lo no cubierto por literatura permanece declarado como
supuesto pendiente de fuente — nunca se mezcla.

Fuentes:
- 11C: Wenz et al. 2022 (EJNMMI Radiopharmacy) — [11C]acetato, rendimiento
  corregido por decaimiento 51 ± 5 % (n=10), 18 ± 2 min; [11C]colina 52 %.
- 68Ga: Siikanen et al. (vía revisión Pharmaceutics 2023, MDPI) — recuperación
  de actividad 76 ± 8 % a EOP (blanco sólido, columna UTEVA); Alves et al.
  2016 — 85 % recuperación/purificación (blanco líquido, Synthera).
- 64Cu: Frontiers in Physics 2022 — electrodeposición 99,83 % (medido);
  pureza radionuclídica >99,99 % post-purificación (la eficiencia de la
  separación no se publica como cifra única → sigue supuesto declarado).

QC y liberación: nunca simulados (18.10/14.9).
"""
from __future__ import annotations

import json
import math
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

EVIDENCIA_DEF = Path("/mnt/agents/work/evidencia_v072")
YE = Path("/mnt/agents/work/rpos25/services/yield_engine")

CASOS = {
    "C11": {
        "reaction_id": "n14_p_a_c11", "target_id": "n2_gas",
        "beam_mev": 16.0, "corriente_ua": 30.0, "t_irrad_min": 30.0,
        "half_life_s": 1221.84, "t_despacho_min": 60.0,
        "escenarios": {
            "wenz_2022_acetato": {
                "rcy_eob_a_eos": 0.51, "t_sintesis_min": 18.0,
                "cita": ("Wenz et al. 2022: [11C]acetate decay-corrected "
                         "yield 51 ± 5% (n=10), total 18 ± 2 min"),
                "url": "https://link.springer.com/article/10.1186/s41181-022-00159-y"},
            "wenz_2022_colina": {
                "rcy_eob_a_eos": 0.52, "t_sintesis_min": 22.0,
                "cita": ("Wenz et al. 2022: N-methyl-[11C]choline isolated "
                         "with 52% decay corrected yield, 22 min"),
                "url": "https://link.springer.com/article/10.1186/s41181-022-00159-y"},
        },
    },
    "GA68": {
        "reaction_id": "zn68_p_n_ga68", "target_id": "zn68",
        "beam_mev": 14.0, "corriente_ua": 25.0, "t_irrad_min": 60.0,
        "half_life_s": 4062.6, "t_despacho_min": 60.0,
        "escenarios": {
            "siikanen_eop": {
                "rcy_eob_a_eos": 0.76, "t_sintesis_min": 45.0,
                "cita": ("Siikanen et al. (rev. Pharmaceutics 2023): activity "
                         "recovery 76 ± 8% at EOP, UTEVA, blanco solido"),
                "url": "https://www.mdpi.com/1999-4923/15/1/70"},
            "alves_2016_liquido": {
                "rcy_eob_a_eos": 0.85, "t_sintesis_min": 30.0,
                "cita": ("Alves et al. 2016: consistent 85% yield for the "
                         "recovery/purification process (blanco liquido, 30 min)"),
                "url": "https://www.ibaradiopharmasolutions.cn/wp-content/uploads/2023/04/paper_award_2016.pdf"},
        },
    },
    "CU64": {
        "reaction_id": "ni64_p_n_cu64", "target_id": "ni64",
        "beam_mev": 12.0, "corriente_ua": 20.0, "t_irrad_min": 120.0,
        "half_life_s": 45721.44, "t_despacho_min": 180.0,
        "escenarios": {
            "frontiers_2022": {
                "rcy_eob_a_eos": 0.9983, "t_sintesis_min": 60.0,
                "cita": ("Frontiers Phys. 2022: electrodeposition yield 99.83% "
                         "medido; pureza radionuclidica >99.99% post-purificacion. "
                         "NOTA: solo cubre electrodeposicion; la separacion no "
                         "publica cifra unica"),
                "url": "https://www.frontiersin.org/journals/physics/articles/10.3389/fphy.2022.1038014/full",
                "nota": "cota superior: la separacion real reduciria el valor"},
        },
    },
}


def correr_f60_multi(evidencia: Path = EVIDENCIA_DEF) -> dict:
    sys.path.insert(0, str(YE))
    from app.main import DATA_DIR
    from app.application.production_service import ProductionService
    from app.infrastructure.repositories.local_reaction_data import (
        LocalReactionDataProvider)
    from app.infrastructure.stopping.factory import build_stopping_provider

    service = ProductionService(
        stopping=build_stopping_provider(DATA_DIR / "stopping"),
        rxn=LocalReactionDataProvider(DATA_DIR))

    salida = {"fase": "F60_multi_eficiencias_citadas",
              "estado": "fuente_citada_parcial_49.11",
              "isotopos": {}}
    for clave, c in CASOS.items():
        lam = math.log(2.0) / c["half_life_s"]
        res = service.compute(reaction_id=c["reaction_id"],
                              target_id=c["target_id"],
                              beam_energy_mev=c["beam_mev"],
                              current_ua=c["corriente_ua"],
                              irradiation_time_min=c["t_irrad_min"])
        eob = res.eob_activity_gbq
        t0 = datetime(2026, 10, 14, 8, 0, tzinfo=timezone.utc)
        escs = {}
        for nombre, e in c["escenarios"].items():
            t_eos = t0 + timedelta(minutes=e["t_sintesis_min"])
            eos = eob * e["rcy_eob_a_eos"] * math.exp(-lam * e["t_sintesis_min"] * 60.0)
            t_desp = t_eos + timedelta(minutes=c["t_despacho_min"])
            escs[nombre] = {
                "fuente": e["cita"], "url": e["url"],
                "nota": e.get("nota", ""),
                "estado_eficiencia": "fuente_citada (49.11)",
                "rcy_eob_a_eos": e["rcy_eob_a_eos"],
                "eos_gbq": round(eos, 3),
                "despacho": {"actividad_gbq": round(
                    eos * math.exp(-lam * c["t_despacho_min"] * 60.0), 3),
                    "estado": "recomendacion_no_liberacion (18.10)"}}
        salida["isotopos"][clave] = {
            "dataset": res.dataset_id, "eob_gbq": round(eob, 3),
            "escenarios_citados": escs,
            "qc": "pendiente_entorno (nunca simulado)",
            "liberacion": "no_liberada (18.10/14.9)"}

    out = Path(evidencia) / "fase60"
    out.mkdir(parents=True, exist_ok=True)
    (out / "eficiencias_citadas_multi_f60.json").write_text(
        json.dumps(salida, ensure_ascii=False, indent=2), encoding="utf-8")
    return salida


def main() -> int:
    s = correr_f60_multi()
    for iso, d in s["isotopos"].items():
        for n, e in d["escenarios_citados"].items():
            print(f"{iso}/{n}: EOB={d['eob_gbq']} EOS={e['eos_gbq']} "
                  f"despacho={e['despacho']['actividad_gbq']} GBq")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
