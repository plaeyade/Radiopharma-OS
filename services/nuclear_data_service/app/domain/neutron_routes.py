# -*- coding: utf-8 -*-
"""Rutas de producción de neutrones por isótopo (Fase 31).

Comparación honesta de la producción de neutrones rápidos entre las rutas
C-11, N-13, O-15 y la referencia F-18, con implicaciones de blindaje del
laberinto y de activación.

REGLAS CANÓNICAS:
- Ningún número es simulado por este módulo: las secciones eficaces provienen
  de corridas REALES de TALYS-1.96 ejecutadas en el entorno (evidencia en
  evidencia_v072/fase31/) o de referencias bibliográficas citadas (49.11).
- La interpretación de blindaje es DECLARADA (cita MDPI 2025) y se marca
  RECOMENDACIÓN (18.10): no constituye decisión operativa de blindaje.
"""
from __future__ import annotations

TALYS_VERSION = "1.96"

# Resultados de corridas TALYS reales @ 16.5 MeV (energía PETtrace),
# archivos out.log preservados como evidencia. "mb" = milibarns.
RUTAS_NEUTRONES = {
    "F-18": {
        "reaccion": "18O(p,n)18F",
        "energia_mev": 18.0,
        "sigma_produccion_n_mb": 537.5,
        "origen": "referencia_canonica",
        "fuente": "Dato canónico plataforma (rendimiento F-18, EDS §producción); "
                  "referencia de comparación de blindaje",
    },
    "O-15": {
        "reaccion": "15N(p,n)15O",
        "energia_mev": 16.5,
        "sigma_produccion_n_mb": 249.32,
        "multiplicidad_n": 0.3534,
        "origen": "talys_corrida_real",
        "fuente": f"TALYS-{TALYS_VERSION} corrida real p+15N @ 16.5 MeV "
                  "(evidencia_v072/fase31/n15_p/out.log)",
    },
    "C-11": {
        "reaccion": "14N(p,a)11C",
        "energia_mev": 16.5,
        "sigma_produccion_n_mb": 149.16,
        "multiplicidad_n": 0.2238,
        "origen": "talys_corrida_real",
        "fuente": f"TALYS-{TALYS_VERSION} corrida real p+14N @ 16.5 MeV "
                  "(evidencia_v072/fase31/n14_p/out.log)",
    },
    "N-13": {
        "reaccion": "16O(p,a)13N",
        "energia_mev": 16.5,
        "sigma_produccion_n_mb": 0.0,
        "multiplicidad_n": 0.0,
        "origen": "talys_corrida_real",
        "fuente": f"TALYS-{TALYS_VERSION} corrida real p+16O @ 16.5 MeV: canal (p,n) "
                  "CERRADO, Q = -16.19 MeV (evidencia_v072/fase31/o16_p/out.log)",
        "nota": "La ruta N-13 por 16O(p,a)13N NO produce neutrones primarios a "
                "16.5 MeV: el canal (p,n) sobre 16O tiene umbral >16 MeV.",
    },
}

# Factores de blindaje medidos (búnker de ciclotrón), cita declarada.
BLINDAJE_MEDICION = {
    "fuente": "Jakubowska et al. 2025, MDPI Applied Sciences 15:11946 "
              "(mediciones en búnker, ciclotrón de producción PET)",
    "factor_k_laberinto": {"F-18": 14000, "C-11": 86000},
    "razon_dosis_bunker_F18_vs_C11": 2.5,
    "nota": "k mayor implica espectro MÁS BLANDO (neutrones secundarios Ag(p,n) "
            "en la ruta 11C): a igual corriente, F-18 domina los niveles de "
            "neutrones en el búnker (~2.5x).",
}

CONCLUSION = (
    "Las rutas C-11, N-13 y O-15 NO incrementan la producción de neutrones "
    "rápidos respecto a F-18: F-18 (537.5 mb) > O-15 (249.3 mb) > C-11 "
    "(149.2 mb) > N-13 (0.0 mb, canal cerrado). Por tanto la producción "
    "habitual de F-18 gobierna el blindaje del laberinto y el estudio de "
    "activación; añadir C-11/N-13/O-15 no endurece el requisito. La "
    "activación se evalúa con el motor Bateman ya implementado."
)


def tabla_rutas() -> list[dict]:
    """Tabla comparativa ordenada de mayor a menor producción de neutrones."""
    filas = []
    for iso, r in RUTAS_NEUTRONES.items():
        filas.append({
            "isotopo": iso,
            "reaccion": r["reaccion"],
            "energia_mev": r["energia_mev"],
            "sigma_produccion_n_mb": r["sigma_produccion_n_mb"],
            "origen": r["origen"],
            "fuente": r["fuente"],
        })
    filas.sort(key=lambda f: f["sigma_produccion_n_mb"], reverse=True)
    return filas


def comparacion_f18() -> dict:
    """Razón de cada ruta respecto a F-18 (referencia de blindaje)."""
    ref = RUTAS_NEUTRONES["F-18"]["sigma_produccion_n_mb"]
    return {
        iso: round(r["sigma_produccion_n_mb"] / ref, 4)
        for iso, r in RUTAS_NEUTRONES.items()
    }


def implicaciones_blindaje() -> dict:
    """Implicaciones DECLARADAS de blindaje y activación (RECOMENDACIÓN 18.10)."""
    return {
        "naturaleza": "RECOMENDACIÓN (18.10) — no es decisión operativa de blindaje",
        "conclusion": CONCLUSION,
        "medicion_bunker": BLINDAJE_MEDICION,
        "motor_activacion": "Bateman (activation.py) ya implementado en la plataforma",
    }
