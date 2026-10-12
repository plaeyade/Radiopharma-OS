# -*- coding: utf-8 -*-
"""Geometría real del búnker de ciclotrón — Fase 38 (plano DWG BIND).

Mediciones extraídas del plano arquitectónico REAL "PLANTAS ARQ CENTRO
INTERNACIONAL DE NEURO-ONCOLOGIA BIND 02-10-26.dwg" (AutoCAD 2018,
convertido a DXF con ODA File Converter 27.9 — evidencia fase38).
Todas las medidas son "medido_sobre_plano" con tolerancia ±0,1 m; lo no
medible queda pendiente_verificacion. Nada se inventa (49.11 aplicado a
geometría: la fuente es el propio plano).

Comparación contra el caso declarado F32 (OIEA genérico 6×6×4 m, muros
2,0/3,0/1,0 m): las simulaciones F35/F37/F43-F45 siguen siendo válidas
COMO CASO OIEA DECLARADO, pero NO representan el as-built hasta recorrer
la geometría real (pendiente_entorno: entorno MC).
"""
from __future__ import annotations

FUENTE_PLANO = ("PLANTAS ARQ CENTRO INTERNACIONAL DE NEURO-ONCOLOGIA BIND "
                "02-10-26.dwg (AutoCAD 2018) → plantas_bind.dxf vía ODA "
                "File Converter 27.9, 2026-10-13")
TOL_M = 0.1  # tolerancia honesta de medición sobre plano

# Medidas directas (histograma de segmentos + cotas DIMENSION del plano)
GEOMETRIA_REAL = {
    "envolvente_bunker_m": {
        "x": (-15.39, -5.68), "y": (33.53, 49.02),
        "ancho_m": 9.71, "largo_m": 15.49,
        "cota_plano_m": 15.499,  # DIMENSION en (-17.22, 49.02)
        "estado": "medido_sobre_plano",
    },
    "sala_ciclotron_interior_m": {
        "ancho_estimado_m": 5.9, "fondo_estimado_m": 4.7,
        "estado": "estimado_sobre_plano_pendiente_verificacion",
        "nota": "líneas dominantes x=-13,28 y x=-10,07 no cierran la sala "
                "completa; la máquina (símbolo) está en (-10,6, 38,2)",
    },
    "muro_oeste_m": {
        "espesor_m": 2.11,  # de x=-15,39 (cara exterior) a x=-13,28 (cara interior)
        "estado": "medido_sobre_plano",
    },
    "cotas_interiores_m": {
        "valores": [3.500, 0.900, 3.700, 3.700, 3.700],
        "estado": "medido_sobre_plano",
        "nota": "cota 3,700 m repetida en 4 vanos (34,43/38,12/41,82/45,32)",
    },
    "laberinto": {
        "presente": True, "cambios_direccion": 2,
        "ubicacion": "sur de la sala, acceso desde radiofarmacia",
        "estado": "observado_en_plano",
    },
    "salas_adyacentes": {
        "este": ["WGHS (taller)", "SALA DE SUMINISTRO ELECTRICO",
                 "SALA DE RESIDUOS RADIACTIVOS", "ESCLUSA DE AIRE 1"],
        "nota_alara": ("SALA DE RESIDUOS RADIACTIVOS y WGHS comparten el "
                       "muro ESTE del búnker — el tally de ese muro pasa a "
                       "ser dosis ocupacional directa, no solo fuga."),
        "estado": "observado_en_plano",
    },
    "simbolo_maquina_xy": (-10.6, 38.2),
}

# Caso declarado F32 (canónico anterior)
CASO_F32 = {"boveda_m": (6.0, 6.0, 4.0), "muros_m": {"x": 3.0, "y": 2.0, "z": 1.0},
            "laberinto_cambios": 1}


def verificar_contra_f32() -> dict:
    """Checklist de cumplimiento: caso declarado F32 vs plano real."""
    g = GEOMETRIA_REAL
    interior = g["sala_ciclotron_interior_m"]
    checks = [
        {"requisito": "Bóveda ~6×6 m (F32)",
         "real": f"~{interior['ancho_estimado_m']}×{interior['fondo_estimado_m']} m "
                 f"({interior['estado']})",
         "veredicto": "parcial", "detalle": "dimensiones comparables; fondo menor"},
        {"requisito": "Muros ≥ 2,0 m (supuesto F32, muro Y)",
         "real": f"muro oeste {g['muro_oeste_m']['espesor_m']} m {g['muro_oeste_m']['estado']}",
         "veredicto": "cumple", "detalle": "oeste 2,11 m ≥ 2,0 m"},
        {"requisito": "Laberinto de acceso (F32: 1 cambio de dirección)",
         "real": "laberinto sur con 2 cambios de dirección",
         "veredicto": "cumple_supera",
         "detalle": "más atenuación que el caso F32"},
        {"requisito": "Salas adyacentes controladas",
         "real": "WGHS + RESIDUOS RADIACTIVOS + SUMINISTRO ELECTRICO al este",
         "veredicto": "por_verificar",
         "detalle": "requiere tally del muro este con geometría real "
                    "(pendiente_entorno: entorno MC)"},
        {"requisito": "Re-simulación as-built (F35/F37 con geometría real)",
         "real": "pendiente_entorno",
         "veredicto": "pendiente",
         "detalle": "los resultados F35-F45 valen como caso OIEA, NO as-built"},
    ]
    cumple = sum(1 for c in checks if c["veredicto"].startswith("cumple"))
    return {
        "fuente_plano": FUENTE_PLANO,
        "tolerancia_m": TOL_M,
        "checks": checks,
        "resumen": f"{cumple}/{len(checks)} cumplen; resto parcial/pendiente",
        "estado": "parcial_pendiente_entorno_y_verificacion",
        "nota_honesta": ("Medidas extraídas por análisis geométrico del DXF "
                         "(histograma de segmentos + cotas). La interpretación "
                         "de qué líneas son caras de muro es declarada y "
                         "revisable; la sala interior queda "
                         "pendiente_verificacion. Nada se fabricó."),
    }
