# -*- coding: utf-8 -*-
"""Cotizaciones de blindaje del búnker — Fase 39.

Dos cotizaciones REALES subidas por el usuario (fuente citada por cifra,
regla 49.11; documentos en /mnt/agents/upload/, referenciados en el
registro). Nada se inventa: lo que el documento no dice queda
pendiente_fuente. Métricas derivadas declaradas como derivadas (18.10:
material de decisión, no decisión operativa).
"""
from __future__ import annotations

COTIZACIONES = {
    "tabique_2p5": {
        "documento": "WhatsApp Image 2026-09-27 (captura de cotización, JPG)",
        "densidad_g_cm3": 2.5,
        "cantidad": 85,
        "unidad_cantidad": "pendiente_fuente (el JPG no indica m² ni piezas)",
        "partidas_mxn": {
            "tabique": 10_632_310.00,
            "flete_30pct": 3_189_693.00,
            "instalacion": 1_949_256.83,
            "estructura": 2_501_720.00,
            "otro_no_especificado": 2_400_000.00,
        },
        "total_mxn": 20_672_979.83,
        "iva_desglosado": False,
        "estado": "real_cotizada",
    },
    "contuplex_3p5": {
        "documento": ("CONTUPLEX, cotización folio 1171-TAB-VILLAH, "
                      "29-sep-2026 (PDF)"),
        "densidad_g_cm3": 3.5,
        "descripcion": ("Sistema integral de blindaje radiológico con "
                        "tabique de alta densidad 3,5 g/cm³, instalado en "
                        "sitio, transporte incluido a Villahermosa, Tab."),
        "subtotal_mxn": 36_027_051.25,
        "iva_mxn": 5_764_328.20,
        "total_mxn": 41_791_379.45,
        "tc_usd": 17.71,
        "entrega_dias_habiles": 90,
        "pago": "30 % anticipo, 70 % contra estimaciones de avance",
        "vigencia_dias_habiles": 10,
        "iva_desglosado": True,
        "estado": "real_cotizada",
    },
}


def validar_suma(nombre: str) -> dict:
    """Verificación aritmética de la cotización (honesta)."""
    c = COTIZACIONES[nombre]
    if "partidas_mxn" in c:
        suma = sum(c["partidas_mxn"].values())
        return {"estado": "verificada" if abs(suma - c["total_mxn"]) < 0.01
                else "no_cuadra", "suma_partidas": suma,
                "total_documento": c["total_mxn"]}
    suma = c["subtotal_mxn"] + c["iva_mxn"]
    return {"estado": "verificada" if abs(suma - c["total_mxn"]) < 0.01
            else "no_cuadra", "suma_subtotal_iva": suma,
            "total_documento": c["total_mxn"]}


def comparar() -> dict:
    """Comparación derivada declarada de ambas cotizaciones."""
    a, b = COTIZACIONES["tabique_2p5"], COTIZACIONES["contuplex_3p5"]
    return {
        "delta_total_mxn": b["total_mxn"] - a["total_mxn"],
        "ratio_total": b["total_mxn"] / a["total_mxn"],
        "delta_densidad_g_cm3": b["densidad_g_cm3"] - a["densidad_g_cm3"],
        "total_usd_contuplex": b["total_mxn"] / b["tc_usd"],
        "nota_iva": ("La cotización 2,5 g/cm³ (JPG) NO desglosa IVA; el "
                     "ratio compara total-sin-IVA-visible vs total-con-IVA "
                     "— sesgo declarado."),
        "nota_fisica_derivada": (
            "A igualdad de densidad área, el espesor necesario escala "
            "inverso a la densidad: 3,5/2,5 ⇒ el tabique de 3,5 g/cm³ "
            "requeriría ~0,71× el espesor del de 2,5 g/cm³. Derivado "
            "didáctico; la especificación de espesor exige el cálculo de "
            "blindaje con la geometría real (F42b, pendiente_entorno)."),
        "nota_honesta": ("Material de decisión (18.10), no recomendación "
                         "operativa. Unidad de la cantidad 85 del JPG: "
                         "pendiente_fuente."),
        "estado": "completado_con_sesgo_iva_declarado",
    }
