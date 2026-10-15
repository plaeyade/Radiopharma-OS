"""F64 — Simulacro de jornada de producción (ETIQUETADO: no es producción).

Ejercicio de validación teórica de la cadena completa: una jornada típica del
centro (2 lotes FDG + 1 lote 11C + 1 lote 68Ga) calculada con los pipelines
reales (datasets IAEA, λ de biblioteca, eficiencias citadas F60 donde existen)
y registrada en el registro append-only ALCOA+.

Reglas canónicas aplicadas:
- Estado global: simulacro_teorico_jornada_NO_produccion_real.
- Cada lote mantiene: QC pendiente_entorno, liberacion no_liberada (18.10/14.9).
- Eficiencias: citadas donde F60 las tiene; el resto supuesto declarado (49.11).
- Nada de este ejercicio "cierra" Producción Clínica (18.19): esa fase exige
  planta física, IQ/OQ/PQ reales y expediente regulatorio.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

EVIDENCIA_DEF = Path("/mnt/agents/work/evidencia_v072")

JORNADA = [
    ("FDG", "F18", "06:00", "lote_fdg"),
    ("FDG", "F18", "10:30", "lote_fdg"),
    ("11C-acetato", "C11", "13:00", "lote_multi"),
    ("68Ga", "GA68", "15:00", "lote_multi"),
]


def correr_simulacro(evidencia: Path = EVIDENCIA_DEF) -> dict:
    sys.path.insert(0, "/mnt/agents/work/rpos25")
    from pipelines.lotes_multi_f58 import correr_lotes
    from pipelines.lote_fdg_f58 import correr_lote
    from pipelines.eficiencias_citadas_f60 import correr_f60

    # reutilizar los pipelines reales (datasets y λ de biblioteca)
    fdg = correr_lote(evidencia)
    multi = correr_lotes(evidencia)
    f60 = correr_f60(evidencia)

    t0 = datetime(2026, 10, 16, 6, 0, tzinfo=timezone.utc)
    lotes = []
    for nombre, iso, hora, _ in JORNADA:
        h, m = map(int, hora.split(":"))
        eob_h = t0.replace(hour=h, minute=m)
        if iso == "F18":
            base = fdg
            esc = f60["escenarios_citados"]["iaea_pub1515"]
            lotes.append({
                "lote_id": f"{nombre}-{eob_h:%Y%m%d-%H%M}",
                "isotopo": iso,
                "eob_gbq": base["irradiacion"]["eob_gbq"],
                "eos_gbq_citado": esc["eos_gbq"],
                "fuente_eficiencia": esc["fuente"][:60],
                "despacho_gbq": esc["despacho"]["actividad_gbq"],
            })
        else:
            base = multi[iso]
            lotes.append({
                "lote_id": f"{nombre}-{eob_h:%Y%m%d-%H%M}",
                "isotopo": iso,
                "eob_gbq": base["irradiacion"]["eob_gbq"],
                "eos_gbq": base["eos_gbq"],
                "despacho_gbq": base["despacho"]["actividad_gbq"],
                "eficiencias": "supuesto_declarado_pendiente_fuente (49.11)",
            })
        lotes[-1]["eob_hora"] = eob_h.isoformat()
        lotes[-1]["qc"] = "pendiente_entorno (nunca simulado)"
        lotes[-1]["liberacion"] = "no_liberada (18.10/14.9)"

    salida = {
        "fase": "F64_simulacro_jornada",
        "estado": "simulacro_teorico_jornada_NO_produccion_real",
        "advertencia": ("Ejercicio de validacion de la cadena de calculo. "
                        "No es produccion. No cierra 18.19 ni PQ (14.9)."),
        "fecha": t0.date().isoformat(),
        "lotes": lotes,
        "resumen": {
            "n_lotes": len(lotes),
            "fdg_total_despacho_gbq": round(sum(
                l["despacho_gbq"] for l in lotes if l["isotopo"] == "F18"), 3),
        },
    }
    out = Path(evidencia) / "fase64"
    out.mkdir(parents=True, exist_ok=True)
    (out / "simulacro_jornada_f64.json").write_text(
        json.dumps(salida, ensure_ascii=False, indent=2), encoding="utf-8")
    # registro append-only ALCOA+
    with open(out / "registro_simulacro.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps({"evento": "simulacro_jornada",
                            "estado": salida["estado"],
                            "n_lotes": len(lotes),
                            "ts": datetime.now(timezone.utc).isoformat()},
                           ensure_ascii=False) + "\n")
    return salida


def main() -> int:
    s = correr_simulacro()
    for l in s["lotes"]:
        print(f"{l['lote_id']}: EOB={l['eob_gbq']} despacho={l['despacho_gbq']} GBq")
    print(s["estado"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
