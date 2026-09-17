# -*- coding: utf-8 -*-
"""Visualización 3D del mesh tally del búnker con PyVista — Fase 35.

Render 3D REAL del mapa de fluencia: volúmenes con cuentas > 0 se
dibujan como voxels coloreados por φ (escala log), con la geometría
declarada OIEA de referencia. PyVista/VTK instalado de verdad
(memoria: reintentar cuando la red lo permitiera — cumplido, VTK 9.7).

REGLA CANÓNICA: igual que los renders Cycles, esto es COMUNICACIÓN del
tally real; si el .mhd no existe o está vacío, aborta (no_demostrable).
Nunca se dibuja un mapa sintético.
"""
from __future__ import annotations

from pathlib import Path

from app.domain.fluence_connector import leer_tally_mhd


def render_volumen_tally(path_mhd: str | Path,
                         salida_png: str | Path,
                         titulo: str = "Fluencia φ — mesh tally real",
                         umbral_min: float = 0.0) -> dict:
    """Render off-screen de los voxels activos del tally.

    Devuelve metadatos del render (voxels dibujados, rango φ). Requiere
    pyvista; si falta, propaga ImportError — el llamador lo declara.
    """
    import numpy as np
    import pyvista as pv

    t = leer_tally_mhd(path_mhd)
    counts = t["counts"]
    if not np.any(counts > umbral_min):
        raise ValueError(f"no_demostrable: tally sin voxels activos en {path_mhd}")

    nx, ny, nz = t["dims"]
    sx, sy, sz = t["spacing_mm"]
    grid = pv.ImageData()
    grid.dimensions = (nx + 1, ny + 1, nz + 1)
    grid.spacing = (sx, sy, sz)
    grid.origin = (-nx * sx / 2, -ny * sy / 2, -nz * sz / 2)
    grid.cell_data["phi_counts"] = counts.ravel(order="F")

    activos = grid.threshold(umbral_min if umbral_min > 0 else 1e-12,
                             scalars="phi_counts")
    n_dibujados = int(activos.n_cells)
    vmax = float(counts.max())

    pv.OFF_SCREEN = True
    pl = pv.Plotter(off_screen=True, window_size=(1400, 900))
    pl.set_background("#0d1117")
    pl.add_mesh(activos, scalars="phi_counts", log_scale=True,
                cmap="inferno", opacity=0.85,
                scalar_bar_args={"title": "counts/voxel (log)",
                                 "color": "white"})
    pl.add_text(titulo + f"\nvoxels activos: {counts.size and int((counts > 0).sum())}"
                f" · máx {vmax:.0f}", font_size=12, color="white")
    pl.camera_position = "iso"
    pl.camera.zoom(1.1)
    salida_png = Path(salida_png)
    pl.screenshot(salida_png)
    pl.close()

    return {
        "salida": str(salida_png),
        "voxels_dibujados": n_dibujados,
        "counts_max": vmax,
        "origen": f"mesh_tally_real:{path_mhd}",
        "backend": f"pyvista {pv.__version__} (VTK real)",
    }
