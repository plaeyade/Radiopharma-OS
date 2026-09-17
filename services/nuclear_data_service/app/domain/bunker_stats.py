# -*- coding: utf-8 -*-
"""Estadística de lotes MC del búnker — Fase 35.

Combina N lotes INDEPENDIENTES del mesh tally del búnker (mismo caso,
semillas distintas) y cuantifica la incertidumbre estadística REAL del
mapa de fluencia: nada de barras de error inventadas — la desviación se
calcula voxel a voxel como la dispersión muestral entre lotes.

Definiciones (declaradas, primer orden):
- φ combinada = media de lotes (equivale a correr ΣN historias).
- σ_rel(voxel) = std_muestral(lotes) / (media × √n_lotes) — error
  estándar de la media relativo, solo donde hay cuentas.
- Métricas de muros: φ media/máx y σ_rel medio/máx sobre voxels con
  cuentas > 0 (los únicos donde el tally informa).

REGLA CANÓNICA: si hay < 2 lotes, la incertidumbre es no_demostrable y
se dice así; nunca se fabrica una σ analítica de relleno.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from app.domain.fluence_connector import leer_tally_mhd


@dataclass(frozen=True)
class EstadisticaLotes:
    n_lotes: int
    historias_por_lote: tuple
    phi_media_muros: float
    phi_max_muros: float
    sigma_rel_media: float | None   # None → no_demostrable (< 2 lotes)
    sigma_rel_max: float | None
    voxels_activos: int
    estado: str
    nota: str


def combinar_lotes(rutas_mhd: list[str | Path],
                   historias: list[int]) -> dict:
    """Suma/normaliza lotes y devuelve mapas media, std y métricas.

    Cada lote se normaliza por sus historias ANTES de promediar (los
    lotes pueden tener N distinto); la media de los mapas normalizados
    es el estimador por historia del conjunto.
    """
    import numpy as np

    if len(rutas_mhd) != len(historias) or not rutas_mhd:
        raise ValueError("rutas e historias deben tener la misma longitud > 0")
    mapas, dims, spacing = [], None, None
    for r, n in zip(rutas_mhd, historias):
        if n <= 0:
            raise ValueError("historias debe ser > 0")
        t = leer_tally_mhd(r)
        if dims is None:
            dims, spacing = t["dims"], t["spacing_mm"]
        elif t["dims"] != dims:
            raise ValueError("lotes con geometrías distintas — no combinables")
        mapas.append(t["counts"] / float(n))
    stack = np.stack(mapas)                     # (n_lotes, nz, ny, nx)
    media = stack.mean(axis=0)
    activos = media > 0
    n_lotes = len(mapas)

    if n_lotes >= 2:
        std = stack.std(axis=0, ddof=1)
        # error estándar de la media relativo por voxel activo
        with np.errstate(divide="ignore", invalid="ignore"):
            sigma_rel = np.where(activos,
                                 std / (np.sqrt(n_lotes) * np.abs(media)),
                                 np.nan)
        sr = sigma_rel[activos]
        estado = "estadistica_real_independiente"
        nota = (f"σ_rel = std muestral de {n_lotes} lotes independientes "
                f"/ (media·√n) — error estándar de la media por voxel")
        sigma_rel_media = float(np.mean(sr))
        sigma_rel_max = float(np.max(sr))
    else:
        sigma_rel = None
        estado = "no_demostrable"
        nota = "un solo lote: incertidumbre estadística no_demostrable"
        sigma_rel_media = None
        sigma_rel_max = None

    a_cm = spacing[0] / 10.0
    v_cm3 = a_cm ** 3
    return {
        "media_por_historia": media,
        "sigma_rel": sigma_rel,
        "voxels_activos": int(activos.sum()),
        "dims": dims,
        "spacing_mm": spacing,
        "voxel_cm3": v_cm3,
        "estado": estado,
        "nota": nota,
        "phi_media_muros": float(media[activos].mean()) if activos.any() else 0.0,
        "phi_max_muros": float(media.max()),
        "sigma_rel_media": sigma_rel_media,
        "sigma_rel_max": sigma_rel_max,
    }


def estadistica(rutas_mhd: list[str | Path],
                historias: list[int]) -> EstadisticaLotes:
    """Resumen tipado para registro/endpoint (sin los arrays)."""
    c = combinar_lotes(rutas_mhd, historias)
    return EstadisticaLotes(
        n_lotes=len(rutas_mhd),
        historias_por_lote=tuple(historias),
        phi_media_muros=c["phi_media_muros"],
        phi_max_muros=c["phi_max_muros"],
        sigma_rel_media=c["sigma_rel_media"],
        sigma_rel_max=c["sigma_rel_max"],
        voxels_activos=c["voxels_activos"],
        estado=c["estado"],
        nota=c["nota"],
    )


def escribir_tally_combinado(rutas_mhd: list[str | Path],
                             historias: list[int],
                             salida_mhd: str | Path) -> Path:
    """Escribe el tally combinado (counts totales de ΣN historias) en
    formato .mhd/.raw idéntico al de un lote — entrada directa para
    fluence_connector.mapa_flujo con n_historias=ΣN."""
    import numpy as np

    c = combinar_lotes(rutas_mhd, historias)
    n_total = sum(historias)
    counts_total = (c["media_por_historia"] * n_total).astype(np.float32)
    salida_mhd = Path(salida_mhd)
    raw_path = salida_mhd.with_suffix(".raw")
    counts_total.tofile(raw_path)
    nx, ny, nz = c["dims"]
    sx, sy, sz = c["spacing_mm"]
    salida_mhd.write_text(
        "ObjectType = Image\nNDims = 3\nBinaryData = True\n"
        "BinaryDataByteOrderMSB = False\nCompressedData = False\n"
        "TransformMatrix = 1 0 0 0 1 0 0 0 1\nOffset = 0 0 0\n"
        "CenterOfRotation = 0 0 0\nAnatomicalOrientation = RAI\n"
        f"ElementSpacing = {sx} {sy} {sz}\n"
        f"DimSize = {nx} {ny} {nz}\n"
        "ElementType = MET_FLOAT\n"
        f"ElementDataFile = {raw_path.name}\n")
    return salida_mhd
