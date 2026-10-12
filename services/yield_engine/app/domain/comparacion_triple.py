# -*- coding: utf-8 -*-
"""Comparación triple de tallies del búnker — Fase 43.

Compara N mapas de fluencia (110×110×60) del MISMO caso (geometría OIEA,
espectro TALYS real, estimador F35): FTFP_BERT (F35, 360k), FTFP_BERT_HP
(F37, 160k) y, cuando el entorno lo permita, OpenMC/ENDF-B-VIII.0 (F42-F43,
pendiente_entorno declarado).

Métricas honestas (idénticas a las de F37): conjunto UNIÓN de voxels
activos, suma de counts por historia, Δ relativa contra la referencia,
diferencia simétrica mediana por voxel — y desglose por componente del
búnker (cine_activacion.mascara_componentes). Una pata ausente queda
marcada "pendiente_entorno" — nunca se fabrica.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

from app.domain.cine_activacion import mascara_componentes

A_CM, V_CM3, Q_NS = 20.0, 8000.0, 5.9412e11  # estimador F35 declarado


@dataclass(frozen=True)
class PataTally:
    """Una pata de la comparación: mapa de counts + nº de historias."""
    nombre: str                 # p.ej. "FTFP_BERT", "FTFP_BERT_HP", "OpenMC"
    counts: np.ndarray          # (110,110,60) counts acumulados
    historias: int
    estado: str = "real"        # "real" | "pendiente_entorno"


def phi_por_voxel(pata: PataTally) -> np.ndarray:
    """φ (n/cm²/s) por voxel con el estimador F35."""
    return pata.counts / pata.historias * (2 * A_CM / 3) / V_CM3 * Q_NS


def comparar(patas: list[PataTally], referencia: str = "FTFP_BERT") -> dict:
    """Comparación N patas sobre el conjunto unión de voxels activos."""
    reales = [p for p in patas if p.estado == "real"]
    pendientes = [p.nombre for p in patas if p.estado != "real"]
    if len(reales) < 1:
        return {"estado": "no_demostrable", "motivo": "sin patas reales"}
    ref = next((p for p in reales if p.nombre == referencia), reales[0])

    union = np.zeros_like(ref.counts, dtype=bool)
    for p in reales:
        if p.counts.shape != ref.counts.shape:
            return {"estado": "no_demostrable",
                    "motivo": f"shape {p.counts.shape} != {ref.counts.shape}"}
        union |= p.counts > 0

    resultado = {
        "referencia": ref.nombre,
        "voxels_union": int(union.sum()),
        "patas_pendientes": pendientes,
        "patas": {},
    }
    suma_ref = float(ref.counts[union].sum()) / ref.historias
    for p in reales:
        suma = float(p.counts[union].sum()) / p.historias
        dif_rel = (abs(p.counts[union] - ref.counts[union])
                   / np.maximum((p.counts[union] + ref.counts[union]) / 2, 1e-30))
        entrada = {
            "historias": p.historias,
            "suma_counts_por_historia_union": suma,
            "delta_rel_vs_referencia": ((suma - suma_ref) / suma_ref
                                        if p is not ref else 0.0),
            "dif_simetrica_mediana_voxel": float(np.median(dif_rel)),
            "voxels_activos_propios": int((p.counts > 0).sum()),
            "phi_media_union": float(phi_por_voxel(p)[union].mean()),
        }
        resultado["patas"][p.nombre] = entrada

    # desglose por componente (suma de counts por historia en cada máscara)
    mascaras = mascara_componentes(ref.counts.shape)
    por_comp = {}
    for nombre, m in mascaras.items():
        s_ref = float(ref.counts[m].sum()) / ref.historias
        por_comp[nombre] = {
            p.nombre: {
                "suma_counts_por_historia": float(p.counts[m].sum()) / p.historias,
                "delta_rel_vs_referencia": ((float(p.counts[m].sum()) / p.historias
                                             - s_ref) / s_ref
                                            if s_ref > 0 and p is not ref else 0.0),
            } for p in reales
        }
    resultado["por_componente"] = por_comp
    resultado["estado"] = ("parcial_pendiente_entorno" if pendientes
                           else "completado")
    return resultado
