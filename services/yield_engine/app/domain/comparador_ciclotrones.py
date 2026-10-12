# -*- coding: utf-8 -*-
"""Comparador de ciclotrones KIUBE vs PETtrace — Fase 47.

Regla canónica 49.11: TODA especificación lleva su fuente citada; lo que no
tiene fuente se marca "pendiente_fuente" y jamás se inventa. Las métricas
derivadas se declaran como derivadas y recomendaciones diferenciadas de
decisiones operativas (18.10).
"""
from __future__ import annotations

# Fuentes (identificadores estables para el registro ALCOA+)
FUENTES = {
    "GE_DS_REV6": ("GE Healthcare, 'PETtrace 800 cyclotron series — Data sheet' "
                   "DOC0776419 rev6 (2018)"),
    "GE_WEB": ("gehealthcare.com — PETtrace 800 Series, Yield Specifications "
               "(consultado 2026-10-13)"),
    "EBERL2012": ("Eberl S. et al., Appl Radiat Isot. 2012 — operación rutinaria "
                  "a 160 µA dual, ~900 GBq F-18 por corrida (PubMed 22476015)"),
    "IBA_PR2018": ("IBA press release 2018-06-19 — Cyclone KIUBE 300: hasta "
                   "1110 GBq (30 Ci) F-18 en corrida de 2 h, 300 dosis FDG"),
    "IBA_WEB": ("iba-worldwide.com — Cyclone KIUBE (consultado 2026-10-13)"),
}

SPECS = {
    "IBA_Cyclone_KIUBE": {
        "fabricante": "IBA (Ion Beam Applications)",
        "energia_protones_MeV": {"valor": 18.0, "fuente": "IBA_WEB"},
        "corriente_max_uA": {"valor": 300, "fuente": "IBA_PR2018"},
        "deuterones": {"valor": None, "fuente": None, "estado": "pendiente_fuente"},
        "f18_max_GBq_2h": {"valor": 1110.0, "fuente": "IBA_PR2018"},
        "puertos_blanco": {"valor": 8, "fuente": "IBA_WEB"},
        "dual_beam": {"valor": True, "fuente": "IBA_WEB"},
        "autoblindaje_opcional": {"valor": True, "fuente": "IBA_WEB"},
    },
    "GE_PETtrace_800": {
        "fabricante": "GE Healthcare",
        "energia_protones_MeV": {"valor": 16.5, "fuente": "GE_DS_REV6"},
        "energia_deuterones_MeV": {"valor": 8.4, "fuente": "GE_DS_REV6"},
        "corriente_max_uA": {"valor": 160, "fuente": "GE_DS_REV6",
                             "nota": "890: 160 µA dual, máx. 100 µA por puerto"},
        "opciones_corriente_uA": {"valor": [60, 100, 130, 160],
                                  "fuente": "GE_DS_REV6",
                                  "nota": "840/860/880/890"},
        "deuterones": {"valor": 60, "fuente": "GE_DS_REV6"},
        "f18_max_GBq_2h": {"valor": 648.0, "fuente": "GE_DS_REV6",
                           "nota": "890; 840/860/880: 240/403/524 GBq"},
        "f18_rutina_GBq": {"valor": 900.0, "fuente": "EBERL2012",
                           "nota": "rutina >2 años a 160 µA dual; >1 TBq logrado"},
        "puertos_blanco": {"valor": 6, "fuente": "GE_DS_REV6"},
        "dual_beam": {"valor": True, "fuente": "GE_DS_REV6"},
        "peso_t": {"valor": 20.0, "fuente": "GE_DS_REV6"},
        "potencia_max_kW": {"valor": 75.0, "fuente": "GE_DS_REV6"},
    },
}


def gbq_por_uA(nombre: str) -> dict:
    """Métrica derivada declarada: capacidad F-18 (2 h) / corriente máx."""
    s = SPECS[nombre]
    f18, corr = s["f18_max_GBq_2h"], s["corriente_max_uA"]
    if f18.get("valor") is None or corr.get("valor") is None:
        return {"estado": "pendiente_fuente"}
    return {"valor": f18["valor"] / corr["valor"], "unidad": "GBq/uA por 2 h",
            "estado": "derivado_declarado",
            "fuentes": [FUENTES[f18["fuente"]], FUENTES[corr["fuente"]]]}


def comparar() -> dict:
    """Comparación declarativa: solo campos con fuente; diferencias derivadas."""
    k, p = SPECS["IBA_Cyclone_KIUBE"], SPECS["GE_PETtrace_800"]
    res = {
        "equipos": {n: {c: (v if not isinstance(v, dict) or "valor" not in v
                            else (v if v.get("valor") is not None
                                  else {"estado": "pendiente_fuente"}))
                        for c, v in s.items()}
                    for n, s in SPECS.items()},
        "metricas_derivadas": {
            n: gbq_por_uA(n) for n in SPECS
        },
        "diferencias": {
            "energia_protones_MeV": k["energia_protones_MeV"]["valor"]
            - p["energia_protones_MeV"]["valor"],
            "corriente_max_uA": k["corriente_max_uA"]["valor"]
            - p["corriente_max_uA"]["valor"],
            "f18_max_GBq_2h": k["f18_max_GBq_2h"]["valor"]
            - p["f18_max_GBq_2h"]["valor"],
        },
        "fuentes": FUENTES,
        "nota_honesta": (
            "Comparación de fichas públicas, NO medición propia ni "
            "recomendación operativa (18.10): es material didáctico de "
            "selección. La capacidad real depende del blanco, el "
            "enriquecimiento del agua 18O y la práctica local. Campos sin "
            "fuente pública marcados pendiente_fuente."),
    }
    return res
