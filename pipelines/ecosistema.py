#!/usr/bin/env python3
"""F90 — Integración de radiopharma-os con los repos hermanos (Cyclotron-SIM, Zumaya-AI, RadShieldMx, GAMMA AI).

1. Lee el contrato `cyclotron-sim/termino_fuente@1` (energía, corrientes, doble haz, rendimiento n/p, puertos).
2. Verifica un plan de producción (corridas por isótopo) contra el presupuesto operativo del blindaje de la instalación:
   corriente máxima instantánea y µA·h por semana (el blindaje se diseña con ambos; el número y la duración de las corridas
   son libres dentro de ese presupuesto).
3. Estima la emisión de neutrones semanal (n/semana) para trazabilidad de activación y dosis, por isótopo.
Reglas: los rendimientos n/p de Ga-68 y Cu-64 son pendiente_fuente (se reportan como cota superior con el de 18O(p,n)).
"""
import json, os, pathlib

RAIZ = pathlib.Path(__file__).resolve().parent
CONTRATO = "cyclotron-sim/termino_fuente@1"
E_CARGA = 1.602176634e-19


def cargar_termino_fuente(ruta=None):
    ruta = pathlib.Path(ruta or os.environ.get("CYCLOTRON_SIM_TF", RAIZ / "fixtures/termino_fuente_kiube.json"))
    tf = json.load(open(ruta))
    if tf.get("contrato") != CONTRATO:
        raise ValueError(f"contrato no soportado: {tf.get('contrato')}")
    return tf


def evaluar_plan(plan, tf, presupuesto):
    """plan: [{isotopo, corridas_semana, horas, corriente_uA, doble_haz}] ; presupuesto: {corriente_max_uA, uAh_semana}."""
    filas, uah_tot, n_tot, i_max = [], 0.0, 0.0, 0.0
    y_f18 = tf["rendimiento_neutrones_n_p"]["18O(p,n)"]["v"]
    for c in plan:
        uah = c["corridas_semana"] * c["horas"] * c["corriente_uA"]
        y = y_f18                                          # cota superior para Ga-68/Cu-64 (pendiente_fuente)
        n = uah * 1e-6 * 3600 / E_CARGA * y
        filas.append(dict(c, uAh_semana=uah, neutrones_semana=n, rendimiento_n_p=y,
                          rendimiento_origen="SRG 18O(p,n)" if c["isotopo"] == "F18" else "cota superior (pendiente_fuente)"))
        uah_tot += uah; n_tot += n; i_max = max(i_max, c["corriente_uA"])
    lim_i = min(presupuesto["corriente_max_uA"], max(tf["versiones_corriente_max_uA"].values()))
    return {"filas": filas, "uAh_semana": uah_tot, "neutrones_semana": n_tot, "corriente_max_uA": i_max,
            "uso_presupuesto": uah_tot / presupuesto["uAh_semana"],
            "cumple": i_max <= lim_i and uah_tot <= presupuesto["uAh_semana"]}


if __name__ == "__main__":
    tf = cargar_termino_fuente()
    plan = [{"isotopo": "F18", "corridas_semana": 10, "horas": 2.0, "corriente_uA": 300, "doble_haz": True},
            {"isotopo": "Ga68", "corridas_semana": 3, "horas": 1.0, "corriente_uA": 40, "doble_haz": False},
            {"isotopo": "Cu64", "corridas_semana": 1, "horas": 4.0, "corriente_uA": 40, "doble_haz": False}]
    r = evaluar_plan(plan, tf, {"corriente_max_uA": 300, "uAh_semana": 12000})
    print(json.dumps({k: v for k, v in r.items() if k != "filas"}, indent=1))
