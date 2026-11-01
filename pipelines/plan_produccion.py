#!/usr/bin/env python3
"""Plan semanal de producción contra el ciclotrón real y el blindaje de la instalación.

Une tres fuentes por contrato, sin copiar datos a mano:
- `cyclotron-sim/termino_fuente@1` (Cyclotron-SIM): versión y corriente máxima, energía fija de
  18 MeV o variable de 13 a 17 MeV en los puertos 3/7, doble haz en puertos opuestos con blancos
  F-18 T1/T5.
- `zumaya-ai/presupuesto_operativo@1` (Zumaya-AI): corriente máxima y µA·h por semana con los que se
  diseñó el blindaje.
- Yield Engine (este repo): actividad EOB TEÓRICA por corrida (datos IAEA citados). No es
  rendimiento medido: la eficiencia real de blanco y síntesis está pendiente de producción.

Rutas: CYCLOTRON_SIM_RAIZ y ZUMAYA_RAIZ apuntan a los repos hermanos. Sin ellas se usan las
fixtures versionadas (copias de esos contratos).
Uso: python pipelines/plan_produccion.py [plan.json]
"""
from __future__ import annotations

import json
import os
import pathlib
import sys

RAIZ = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(RAIZ))
import ecosistema  # noqa: E402

CONTRATO_PRESUPUESTO = "zumaya-ai/presupuesto_operativo@1"
VERSION = "KIUBE 300"
REACCION = {  # isótopo → (reacción, blanco) del catálogo de Yield Engine
    "F18": ("o18_p_n_f18", "h2_18o"),
    "Ga68": ("zn68_p_n_ga68", "zn68"),
    "Cu64": ("ni64_p_n_cu64", "ni64"),
}
# Mezcla declarada por el usuario (2026-10-31): fracción de radiofármacos, no de tiempo de haz.
MEZCLA_DECLARADA = {"F18": 0.80, "Ga68": 0.10, "Cu64": 0.05, "otros": 0.05}

PLAN_BASE = [
    {"isotopo": "F18", "corridas_semana": 10, "horas": 2.0, "corriente_uA": 300, "energia_MeV": 18.0, "doble_haz": True},
    {"isotopo": "Ga68", "corridas_semana": 3, "horas": 1.0, "corriente_uA": 40, "energia_MeV": 13.0, "doble_haz": False},
    {"isotopo": "Cu64", "corridas_semana": 1, "horas": 4.0, "corriente_uA": 40, "energia_MeV": 13.0, "doble_haz": False},
]


def cargar_presupuesto(ruta=None):
    raiz = os.environ.get("ZUMAYA_RAIZ")
    ruta = pathlib.Path(ruta or (pathlib.Path(raiz) / "licencia/presupuesto_operativo.json" if raiz
                                 else RAIZ / "fixtures/presupuesto_operativo_zumaya.json"))
    p = json.load(open(ruta, encoding="utf-8"))
    if p.get("contrato") != CONTRATO_PRESUPUESTO:
        raise ValueError(f"contrato no soportado: {p.get('contrato')}")
    return p


def cargar_tf():
    raiz = os.environ.get("CYCLOTRON_SIM_RAIZ")
    return ecosistema.cargar_termino_fuente(
        pathlib.Path(raiz) / "machines/iba_kiube/export/termino_fuente.json" if raiz else None)


def _servicio_rendimiento():
    ye = RAIZ.parent / "services" / "yield_engine"
    sys.path.insert(0, str(ye))
    for m in [k for k in list(sys.modules) if k == "app" or k.startswith("app.")]:
        del sys.modules[m]
    from app.main import service  # noqa: PLC0415
    return service


def verificar_corrida(c, tf, i_max_version):
    """Reglas de máquina por corrida; devuelve lista de incumplimientos (vacía si cumple)."""
    e = []
    if c["isotopo"] not in REACCION:
        e.append(f"{c['isotopo']}: sin reacción en Yield Engine (pendiente)")
    ev = tf["energia_variable"]
    e_fija = tf["energia_MeV"]["v"]
    lo, hi = ev["rango_MeV"]
    if not (abs(c["energia_MeV"] - e_fija) < 1e-9 or lo <= c["energia_MeV"] <= hi):
        e.append(f"{c['isotopo']}: {c['energia_MeV']} MeV no es {e_fija} MeV ni está en {lo}–{hi} MeV (puertos {ev['puertos']})")
    if c["corriente_uA"] > i_max_version:
        e.append(f"{c['isotopo']}: {c['corriente_uA']} µA excede {VERSION} ({i_max_version} µA)")
    if c.get("doble_haz"):
        if c["isotopo"] != "F18":
            e.append(f"{c['isotopo']}: doble haz sólo con blancos F-18 {tf['blancos_F18']} en puertos opuestos")
        if abs(c["energia_MeV"] - e_fija) > 1e-9:
            e.append(f"{c['isotopo']}: doble haz a energía fija {e_fija} MeV (los puertos VE son 3/7)")
    return e


def planificar(plan=None, tf=None, presupuesto=None, rendimiento=None):
    tf = tf or cargar_tf()
    presupuesto = presupuesto or cargar_presupuesto()
    plan = plan or PLAN_BASE
    i_max_version = tf["versiones_corriente_max_uA"][VERSION]
    svc = rendimiento or _servicio_rendimiento()
    filas, incumplimientos = [], []
    for c in plan:
        inc = verificar_corrida(c, tf, i_max_version)
        incumplimientos += inc
        fila = dict(c)
        if c["isotopo"] in REACCION and not any(c["isotopo"] in x and "Yield" in x for x in inc):
            rx, blanco = REACCION[c["isotopo"]]
            por_blanco = c["corriente_uA"] / (2 if c.get("doble_haz") else 1)
            r = svc.compute(rx, blanco, c["energia_MeV"], por_blanco, c["horas"] * 60)
            blancos = 2 if c.get("doble_haz") else 1
            fila.update(eob_GBq_por_corrida_teorico=round(r.eob_activity_gbq * blancos, 1),
                        eob_GBq_semana_teorico=round(r.eob_activity_gbq * blancos * c["corridas_semana"], 1),
                        dataset=r.dataset_id, incertidumbre_relativa=r.relative_uncertainty)
        filas.append(fila)
    blindaje = ecosistema.evaluar_plan(plan, tf, {"corriente_max_uA": presupuesto["corriente_max_uA"],
                                                  "uAh_semana": presupuesto["uAh_semana"]})
    if not blindaje["cumple"]:
        incumplimientos.append(
            f"presupuesto de blindaje: {blindaje['uAh_semana']:.0f} µA·h/semana "
            f"(límite {presupuesto['uAh_semana']}) o corriente {blindaje['corriente_max_uA']} µA "
            f"(límite {presupuesto['corriente_max_uA']})")
    t_haz = {c["isotopo"]: c["corridas_semana"] * c["horas"] for c in plan}
    total_t = sum(t_haz.values()) or 1.0
    return {
        "plan": filas,
        "cumple": not incumplimientos,
        "incumplimientos": incumplimientos,
        "blindaje": {k: blindaje[k] for k in ("uAh_semana", "uso_presupuesto", "neutrones_semana", "corriente_max_uA")},
        "presupuesto": {k: presupuesto[k] for k in ("corriente_max_uA", "uAh_semana", "estado")},
        "fraccion_tiempo_haz": {k: round(v / total_t, 3) for k, v in t_haz.items()},
        "mezcla_declarada_radiofarmacos": MEZCLA_DECLARADA,
        "advertencias": [
            "EOB teórico (sección eficaz IAEA y frenado): no incluye eficiencia real de blanco ni de síntesis.",
            "La mezcla declarada es por radiofármaco y la fracción de haz por tiempo: no son comparables uno a uno.",
            "«otros» (5 %) sin isótopo ni reacción definidos: pendiente.",
            f"Presupuesto de blindaje en estado «{presupuesto.get('estado')}».",
        ],
    }


if __name__ == "__main__":
    plan = json.load(open(sys.argv[1], encoding="utf-8")) if len(sys.argv) > 1 else None
    r = planificar(plan)
    print(json.dumps(r, ensure_ascii=False, indent=1))
    sys.exit(0 if r["cumple"] else 1)
