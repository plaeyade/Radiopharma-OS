"""Tablero de producción por lote: EOB/EOS, rendimiento de blanco y de síntesis, y QC.

Compara cada lote registrado con lo esperado y produce un tablero en JSON o HTML estático:
- EOB TEÓRICO de la corrida: sale de `plan_produccion.planificar` (Yield Engine, datos IAEA) y se
  escala a la corriente y duración reales con el factor de saturación (1 − e^{−λt}).
- Rendimiento de blanco = EOB medido / EOB teórico.
- Rendimiento de síntesis corregido por decaimiento = EOS / (EOB · e^{−λ·Δt}).
- QC: recomendación del Release Engine de qc_engine (liberación / rechazo / revisión) con el
  protocolo del producto. Un producto sin protocolo queda como SIN_PROTOCOLO.

Ningún resultado es una liberación farmacéutica: la decisión es del responsable sanitario.
Uso: python pipelines/tablero_produccion.py lotes.json [--html tablero.html]
Formato de lotes.json: lista de objetos con
  lote, isotopo, fecha, corriente_uA, horas, eob_GBq,
  y opcionalmente doble_haz, eos_GBq, minutos_eob_a_eos, producto, qc (dict ensayo → valor).
"""
from __future__ import annotations

import argparse
import html
import json
import math
import pathlib
import sys

RAIZ = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(RAIZ))
import plan_produccion

SEMIVIDA_MIN = {"F18": 109.77, "Ga68": 67.71, "Cu64": 762.0}  # NNDC/ENSDF
PROTOCOLO_QC = {"F18": "fdg_18f_qc"}
CAMPOS = ("lote", "isotopo", "fecha", "corriente_uA", "horas", "eob_GBq")


def _servicio_qc():
    qc = RAIZ.parent / "services" / "qc_engine"
    for m in [k for k in list(sys.modules) if k == "app" or k.startswith("app.")]:
        del sys.modules[m]
    sys.path.insert(0, str(qc))
    try:
        from app.application.qc_release_service import QcReleaseService
    finally:
        sys.path.remove(str(qc))
    return QcReleaseService()


def _saturacion(isotopo: str, horas: float) -> float:
    lam = math.log(2) / SEMIVIDA_MIN[isotopo]
    return 1 - math.exp(-lam * horas * 60)


def eob_teorico(lote: dict, fila_plan: dict) -> float | None:
    base = fila_plan.get("eob_GBq_por_corrida_teorico")
    if base is None or lote["isotopo"] not in SEMIVIDA_MIN:
        return None
    blancos = lambda c: 2 if c.get("doble_haz") else 1
    por_blanco = lambda c: c["corriente_uA"] / blancos(c)
    escala = (por_blanco(lote) / por_blanco(fila_plan)) * (blancos(lote) / blancos(fila_plan))
    escala *= _saturacion(lote["isotopo"], lote["horas"]) / _saturacion(lote["isotopo"], fila_plan["horas"])
    return base * escala


def evaluar_lote(lote: dict, filas_plan: dict, qc) -> dict:
    faltan = [c for c in CAMPOS if c not in lote]
    if faltan:
        raise ValueError(f"lote {lote.get('lote', '?')}: faltan {', '.join(faltan)}")
    iso = lote["isotopo"]
    fila = {k: lote.get(k) for k in ("lote", "isotopo", "fecha", "producto", "corriente_uA", "horas", "eob_GBq", "eos_GBq")}
    alertas = []
    teo = eob_teorico(lote, filas_plan[iso]) if iso in filas_plan else None
    fila["eob_teorico_GBq"] = round(teo, 1) if teo else None
    fila["rendimiento_blanco"] = round(lote["eob_GBq"] / teo, 3) if teo else None
    if teo is None:
        alertas.append("sin EOB teórico (isótopo fuera del plan o sin Yield Engine)")
    elif fila["rendimiento_blanco"] > 1.05:
        alertas.append("EOB medido > teórico: revisar calibración del activímetro o los datos de la corrida")
    eos, dt = lote.get("eos_GBq"), lote.get("minutos_eob_a_eos")
    if eos is not None and dt is not None and iso in SEMIVIDA_MIN:
        esperado = lote["eob_GBq"] * math.exp(-math.log(2) / SEMIVIDA_MIN[iso] * dt)
        fila["rendimiento_sintesis_corr"] = round(eos / esperado, 3)
    else:
        fila["rendimiento_sintesis_corr"] = None
    protocolo = PROTOCOLO_QC.get(iso)
    if not protocolo:
        fila.update(qc="SIN_PROTOCOLO", qc_oos=None, qc_pendientes=None)
        alertas.append(f"sin protocolo QC para {iso}")
    else:
        r = qc.release(protocolo, lote.get("qc") or {}, lote=str(lote["lote"]))
        fila.update(qc=r.recomendacion, qc_oos=r.n_oos, qc_pendientes=r.n_pendientes,
                    qc_motivos=list(r.motivos))
    fila["alertas"] = alertas
    return fila


def _media(filas: list[dict], clave: str) -> float | None:
    v = [f[clave] for f in filas if f[clave] is not None]
    return round(sum(v) / len(v), 3) if v else None


def tablero(lotes: list[dict], plan: dict | None = None, qc=None) -> dict:
    plan = plan or plan_produccion.planificar()
    qc = qc or _servicio_qc()
    filas_plan = {f["isotopo"]: f for f in plan["plan"]}
    filas = [evaluar_lote(lote, filas_plan, qc) for lote in lotes]
    resumen = {}
    for iso in sorted({f["isotopo"] for f in filas}):
        sub = [f for f in filas if f["isotopo"] == iso]
        resumen[iso] = {
            "lotes": len(sub),
            "eob_GBq_total": round(sum(f["eob_GBq"] for f in sub), 1),
            "eob_GBq_semana_teorico_plan": filas_plan.get(iso, {}).get("eob_GBq_semana_teorico"),
            "rendimiento_blanco_medio": _media(sub, "rendimiento_blanco"),
            "rendimiento_sintesis_medio": _media(sub, "rendimiento_sintesis_corr"),
            "qc": {e: sum(f["qc"] == e for f in sub) for e in ("liberacion", "rechazo", "revision", "SIN_PROTOCOLO")},
        }
    return {
        "lotes": filas,
        "resumen": resumen,
        "plan_cumple": plan["cumple"],
        "fichas_evidencia": {k: v for k, v in plan.get("fichas_evidencia", {}).items()
                             if k in resumen or k == "ciclotron"},
        "advertencias": [
            "Recomendación técnica de QC; la liberación la firma el responsable sanitario.",
            "EOB teórico con datos IAEA citados: no incluye la eficiencia real del blanco.",
            *plan["advertencias"],
        ],
    }


def a_html(t: dict) -> str:
    e = html.escape
    cols = ("lote", "fecha", "isotopo", "producto", "corriente_uA", "horas", "eob_GBq", "eob_teorico_GBq",
            "rendimiento_blanco", "eos_GBq", "rendimiento_sintesis_corr", "qc")
    filas = "".join(
        f"<tr class='{e(str(f['qc']))}'>" + "".join(f"<td>{e('' if f.get(c) is None else str(f.get(c)))}</td>" for c in cols)
        + f"<td>{e('; '.join(f['alertas']))}</td></tr>" for f in t["lotes"])
    res = "".join(
        f"<tr><td>{e(i)}</td><td>{r['lotes']}</td><td>{r['eob_GBq_total']}</td><td>{r['eob_GBq_semana_teorico_plan']}</td>"
        f"<td>{r['rendimiento_blanco_medio']}</td><td>{r['rendimiento_sintesis_medio']}</td>"
        f"<td>{e(json.dumps(r['qc']))}</td></tr>" for i, r in t["resumen"].items())
    adv = "".join(f"<li>{e(a)}</li>" for a in t["advertencias"])
    fichas = "".join(
        f"<h3>{e(k)}</h3><ul>"
        + "".join(f"<li>{e(r['texto'])}</li>" for r in v["referencias"])
        + (f"<li><em>{e(v['pendiente'])}</em></li>" if v.get("pendiente") else "")
        + "</ul>"
        for k, v in t.get("fichas_evidencia", {}).items())
    return f"""<!doctype html><html lang="es"><meta charset="utf-8"><title>Tablero de producción</title>
<style>body{{font:14px system-ui;margin:16px;background:#fff;color:#111}}table{{border-collapse:collapse;margin:8px 0}}
td,th{{border:1px solid #ccc;padding:4px 6px;text-align:right}}td:first-child{{text-align:left}}
tr.rechazo{{background:#fde2e2}}tr.revision{{background:#fff4d6}}tr.liberacion{{background:#e6f6e6}}</style>
<h1>Tablero de producción</h1><h2>Resumen por isótopo</h2><table><tr><th>Isótopo</th><th>Lotes</th><th>EOB total GBq</th>
<th>EOB teórico semana (plan)</th><th>Rend. blanco</th><th>Rend. síntesis</th><th>QC</th></tr>{res}</table>
<h2>Lotes</h2><table><tr>{''.join(f'<th>{c}</th>' for c in cols)}<th>alertas</th></tr>{filas}</table>
<h2>Fichas: evidencia citada por GAMMA-AI</h2>{fichas or '<p>Sin paquete de evidencia.</p>'}
<h2>Advertencias</h2><ul>{adv}</ul></html>"""


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("lotes", type=pathlib.Path)
    ap.add_argument("--html", type=pathlib.Path)
    a = ap.parse_args()
    t = tablero(json.loads(a.lotes.read_text(encoding="utf-8")))
    if a.html:
        a.html.write_text(a_html(t), encoding="utf-8")
    print(json.dumps(t, ensure_ascii=False, indent=1))
    return 0 if all(f["qc"] != "rechazo" for f in t["lotes"]) else 1


if __name__ == "__main__":
    sys.exit(main())
