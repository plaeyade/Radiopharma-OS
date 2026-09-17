"""Capacidades máximas de producción por isótopo y ciclotrón (Fase 30).

A_EOB = I · Y_sat · (1 - e^(-λ·t)) — fórmula de saturación estándar de
targetry, con rendimiento de saturación Y_sat SIEMPRE citado (49.11).

Si el ciclotrón opera por debajo del rango del dataset citado (p. ej.
BG-75 a 7.5 MeV vs dataset IAEA 8-18 MeV), NO se extrapola: se usa la
especificación del vendedor citada para ese equipo, marcada como tal.
"""
from __future__ import annotations

import math

from .cost_engine import CICLOTRONES
from .equipment_catalog import CICLOTRONES_EXT

T12_S = {
    "F-18": 109.77 * 60.0,
    "N-13": 9.965 * 60.0,
    "Cu-64": 12.7 * 3600.0,
    "C-11": 20.34 * 60.0,
}

# Rendimientos de saturación citados.
# F-18: Y_sat(E) aproximado por tramos citados.
#  - 18 MeV: 9.902 GBq/µA saturación (dataset IAEA-2021 de la plataforma, inc. 7.78 %)
#  - 16-18 MeV: 230-280 mCi/µA (OSTI 945375, curvas teóricas water target)
#  - 7.5 MeV BG-75: 1 mCi/min @ 5 µA especificación de vendedor (Zaman 2019)
# N-13: rutina 29±2 GBq @ 55 µA / 40 min (PMC10254488); ORISE: 100 mCi / 10 min típico.
# Cu-64: 228 MBq/µA·h calculado 12→9 MeV (IAEA Pub1717, tabla 2);
#        experimental TR-19: 8.7 GBq @ 20 µA / 4 h (Frontiers Phys 2022).
Y_SAT_F18 = {
    # energía_mev_min: (y_sat_gb_por_ua, fuente)
    18.0: (9.902, "Dataset IAEA-2021 plataforma (o18_p_n_f18_iaea2021), inc. 7.78 %"),
    16.0: (8.9, "OSTI 945375: 230-280 mCi/µA @ 16-18 MeV → 8.5-10.4 GBq/µA (punto medio declarado)"),
    11.0: (5.5, "Estimación por curva teórica OSTI 945375 fig. 2 (declarada, pendiente dataset <16 MeV)"),
    7.5: (None, "Fuera del rango del dataset IAEA (8-18 MeV) — NO extrapolado; usar modelo_vendedor"),
}

MODELO_VENDEDOR_BG75 = {
    "tasa_mci_min_a_5ua": 1.0,
    "fuente": ("Especificación de vendedor BG-75: 1 mCi/min @ 5 µA "
               "(Zaman 2019, PMC6709360; rutina real 4.5 µA por ruptura de blanco a 5.5 µA)"),
}

Y_N13 = {
    "rutina_gb": 29.0, "corriente_ua": 55.0, "t_min": 40.0,
    "fuente": "PMC10254488: 29±2 GBq 13N-NH3 @ 55 µA / 40 min (sistema 2XL)",
}

Y_CU64 = {
    "mbq_por_ua_h": 228.0, "rango_mev": (9.0, 12.0),
    "fuente": "IAEA Pub1717 tabla 2: 64Ni(p,n)64Cu, 228 MBq/µA·h calculado (12→9 MeV)",
    "exp": "Frontiers Phys 2022: 8.7±0.7 GBq experimental @ 20 µA / 4 h (TR-19, 11.66 MeV)",
}


def _y_sat_f18(energia_mev: float):
    """Y_sat 18F por tramos citados; nunca interpola por debajo de 16 MeV
    hacia el dataset IAEA — 7.5 MeV usa modelo de vendedor."""
    if energia_mev >= 17.0:
        return Y_SAT_F18[18.0]
    if energia_mev >= 12.0:
        return Y_SAT_F18[16.0]
    if energia_mev >= 8.0:
        return Y_SAT_F18[11.0]
    return Y_SAT_F18[7.5]


def capacidad_f18(ciclotron_id: str, corriente_ua: float, t_min: float) -> dict:
    cat = {**CICLOTRONES_EXT}
    kiube = {"energia_mev": 18.0, "corriente_max_ua": None,
             "fuente": "ficha IBA KIUBE (18 MeV; corriente según blanco instalado)"}
    if ciclotron_id == "iba_cyclone_kiube":
        c = kiube
    elif ciclotron_id in cat:
        c = cat[ciclotron_id]
    else:
        raise ValueError("ciclotron no catalogado")
    if corriente_ua <= 0 or t_min <= 0:
        raise ValueError("corriente y tiempo deben ser positivos")
    if c.get("corriente_max_ua") is not None and corriente_ua > c["corriente_max_ua"]:
        raise ValueError(f"corriente excede el máximo citado ({c['corriente_max_ua']} µA)")

    lam = math.log(2) / T12_S["F-18"]
    e = c["energia_mev"]
    if e < 8.0:
        # Modelo vendedor BG-75: tasa lineal escalada por corriente, marcado.
        esc = corriente_ua / 5.0
        act_mci = MODELO_VENDEDOR_BG75["tasa_mci_min_a_5ua"] * esc * t_min
        return {
            "isotopo": "F-18", "modelo": "modelo_vendedor_lineal (energía <8 MeV)",
            "actividad_eob_gb": round(act_mci * 0.037, 3),
            "corriente_ua": corriente_ua, "t_min": t_min,
            "energia_mev": e,
            "advertencia": ("energía por debajo del dataset IAEA 8-18 MeV — NO "
                            "extrapolado; resultado según especificación de vendedor"),
            "fuente": MODELO_VENDEDOR_BG75["fuente"],
        }
    y, fy = _y_sat_f18(e)
    act_gb = corriente_ua * y * (1.0 - math.exp(-lam * t_min * 60.0))
    return {
        "isotopo": "F-18", "modelo": "saturación con Y_sat citado",
        "actividad_eob_gb": round(act_gb, 3),
        "y_sat_gb_por_ua": y, "corriente_ua": corriente_ua, "t_min": t_min,
        "energia_mev": e, "fuente": fy,
    }


def capacidad_n13(ciclotron_id: str, corriente_ua: float, t_min: float) -> dict:
    """13N-NH3 por 16O(p,α)13N: escala de la rutina citada por I y saturación."""
    if ciclotron_id not in CICLOTRONES_EXT and ciclotron_id != "iba_cyclone_kiube":
        raise ValueError("ciclotron no catalogado")
    e = (CICLOTRONES_EXT.get(ciclotron_id) or {}).get("energia_mev", 18.0)
    if e < 8.0:
        raise ValueError("13N no demostrable a <8 MeV sin fuente — no se extrapola")
    lam = math.log(2) / T12_S["N-13"]
    # Escala de la rutina citada: ajuste por corriente y factor de saturación
    # relativo al pulso citado (40 min ≈ 4 T½ → ~0.937).
    sat_ref = 1.0 - math.exp(-lam * Y_N13["t_min"] * 60.0)
    sat = 1.0 - math.exp(-lam * t_min * 60.0)
    act = Y_N13["rutina_gb"] * (corriente_ua / Y_N13["corriente_ua"]) * (sat / sat_ref)
    return {
        "isotopo": "N-13 (NH3)", "modelo": "escala de rutina citada + saturación",
        "actividad_eob_gb": round(act, 3),
        "corriente_ua": corriente_ua, "t_min": t_min, "energia_mev": e,
        "advertencia": "escala declarada de rutina citada; capacidad absoluta exige blanco y química reales",
        "fuente": Y_N13["fuente"],
    }


def capacidad_cu64(ciclotron_id: str, corriente_ua: float, t_h: float) -> dict:
    """64Cu por 64Ni(p,n) en blanco sólido con degradador a la ventana citada."""
    if ciclotron_id not in CICLOTRONES_EXT and ciclotron_id != "iba_cyclone_kiube":
        raise ValueError("ciclotron no catalogado")
    if corriente_ua <= 0 or t_h <= 0:
        raise ValueError("corriente y tiempo deben ser positivos")
    e = (CICLOTRONES_EXT.get(ciclotron_id) or {}).get("energia_mev", 18.0)
    if e < 12.0:
        raise ValueError("64Cu vía 64Ni(p,n) en ventana 12→9 MeV exige ≥12 MeV citado")
    lam_h = math.log(2) / 12.7  # T½ 64Cu = 12.7 h (por hora)
    act_mbq = (corriente_ua * Y_CU64["mbq_por_ua_h"] / lam_h
               * (1.0 - math.exp(-lam_h * t_h)))
    return {
        "isotopo": "Cu-64", "modelo": "TTY citado con saturación exacta",
        "actividad_eob_gb": round(act_mbq / 1000.0, 3),
        "corriente_ua": corriente_ua, "t_h": t_h, "energia_mev": e,
        "advertencia": ("requiere blanco sólido 64Ni + degradador a 12→9 MeV; "
                        "verificar disponibilidad de estación de blanco sólido"),
        "fuente": Y_CU64["fuente"] + " | " + Y_CU64["exp"],
    }


def tablero_capacidades() -> dict:
    """Capacidad máxima citada por ciclotrón e isótopo (entradas declaradas)."""
    escenarios = []
    # FDG por ciclotrón: corriente máxima citada, 60 min para F-18
    for cid, c in CICLOTRONES_EXT.items():
        imax = c.get("corriente_max_ua")
        if imax is None:
            escenarios.append({"ciclotron": cid, "isotopo": "F-18",
                               "estado": "sin_capacidad_calculable — corriente pendiente_fuente",
                               "fuente": c["fuente"]})
            continue
        escenarios.append({"ciclotron": cid,
                           **capacidad_f18(cid, imax, 60.0)})
    escenarios.append({"ciclotron": "iba_cyclone_kiube",
                       **capacidad_f18("iba_cyclone_kiube", 80.0, 60.0)})
    return {"escenarios": escenarios,
            "nota": ("corrientes = máximos citados por fabricante/literatura; "
                     "tiempo 60 min F-18. Capacidades = cálculo declarado, no "
                     "medición operativa (sin ciclotrón, 19.16 diferido).")}
