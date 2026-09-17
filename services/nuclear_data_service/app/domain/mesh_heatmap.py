"""Mapas de calor de mesh tally — backend PyVista/VTK con respaldo (Fase 30).

Contrato canónico:
- El módulo SOLO renderiza campos de fluencia con origen declarado.
- origen="mesh_tally:<archivo>" → campo MC real (hoja de ruta ②).
- origen="declarado_demo" → campo sintético de demostración, ETIQUETADO
  en el propio render como "CAMPO DECLARADO — NO ES RESULTADO MC".
- El backend usado (pyvista | matplotlib) queda declarado en los metadatos
  y en la etiqueta del render — nunca se disimula.
- Cuando el mesh tally Geant4 real exista, su malla se consume con el mismo
  código; cuando PyVista/VTK sea instalable en el entorno, backend="pyvista"
  es la ruta preferida (malla .vtk/.vtu nativa).
"""
from __future__ import annotations

import math
from pathlib import Path


def _etiqueta(origen: str) -> str:
    return ("FLUENCIA MC — mesh tally real" if origen.startswith("mesh_tally:")
            else "CAMPO DECLARADO DE DEMOSTRACIÓN — NO ES RESULTADO MC")


def construir_malla_demo(nx=80, ny=60, ext_x=200.0, ext_y=150.0):
    """Malla cartesiana (cm) de un muro con campo gaussiano DECLARADO.

    Devuelve (xx, yy, fluencia) en numpy — convertible a pv.ImageData con
    `a_pyvista()` cuando VTK esté disponible.
    """
    import numpy as np

    xx, yy = np.meshgrid(
        np.linspace(0, ext_x, nx), np.linspace(0, ext_y, ny), indexing="ij")
    # Campo gaussiano sintético: pico en la huella del haz + componente
    # difusa — SOLO demostración del pipeline de render.
    fluencia = 1.0e6 * np.exp(-(((xx - ext_x / 2) / 35.0) ** 2
                                + ((yy - ext_y / 2) / 35.0) ** 2)) \
        + 1.0e4 * np.exp(-(((xx - ext_x * 0.2) / 60.0) ** 2
                           + ((yy - ext_y * 0.7) / 60.0) ** 2)) \
        + 1.0e2
    return xx, yy, fluencia


def a_pyvista(xx, yy, fluencia):
    """Convierte la malla a pv.ImageData (requiere pyvista instalado)."""
    import numpy as _np
    import pyvista as pv

    # Acepta mallas 2-D (meshgrid) o vectores 1-D de ejes (Fase 32)
    if xx.ndim == 1:
        xx, yy = _np.meshgrid(xx, yy, indexing="ij")
    nx, ny = xx.shape
    grid = pv.ImageData(dimensions=(nx, ny, 1))
    grid.spacing = (xx[1, 0] - xx[0, 0], yy[0, 1] - yy[0, 0], 1.0)
    grid.point_data["fluencia_n_cm2_s"] = fluencia.ravel(order="F")
    return grid


def render_heatmap(salida_png: str, origen: str,
                   titulo: str = "Fluencia neutrónica en muro (corte XY)",
                   backend: str = "auto", malla=None) -> dict:
    """Render offscreen del campo demo o de una malla MC real.

    backend: "auto" (pyvista si importable, si no matplotlib) | "pyvista" |
    "matplotlib". origen obligatorio (49.11).
    """
    if not origen:
        raise ValueError("origen del campo de fluencia obligatorio (49.11)")
    import numpy as np

    if backend == "auto":
        try:
            import pyvista  # noqa
            backend = "pyvista"
        except ImportError:
            backend = "matplotlib"

    etiqueta = _etiqueta(origen)
    if malla is not None:
        # Fase 32: malla REAL de un mesh tally MC (origen mesh_tally:...).
        import numpy as _np
        fl = _np.asarray(malla, dtype=float)
        xx = _np.arange(fl.shape[1], dtype=float)
        yy = _np.arange(fl.shape[0], dtype=float)
    else:
        xx, yy, fl = construir_malla_demo()

    if backend == "pyvista":
        import pyvista as pv
        grid = a_pyvista(xx, yy, fl)
        pl = pv.Plotter(off_screen=True, window_size=(1600, 1000))
        pl.add_mesh(grid, scalars="fluencia_n_cm2_s", cmap="inferno",
                    log_scale=True,
                    scalar_bar_args={"title": "φ (n/cm²·s) log"})
        pl.add_text(f"{titulo}\n{etiqueta}\norigen: {origen} · backend: pyvista",
                    position="upper_left", font_size=11, color="white")
        pl.view_xy()
        pl.show(screenshot=salida_png)
    elif backend == "matplotlib":
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        from matplotlib.colors import LogNorm

        fig, ax = plt.subplots(figsize=(12, 7.5), dpi=140)
        fig.patch.set_facecolor("#0d1117")
        ax.set_facecolor("#0d1117")
        pcm = ax.pcolormesh(xx, yy, fl, cmap="inferno",
                            norm=LogNorm(vmin=1e2, vmax=fl.max()))
        cb = fig.colorbar(pcm, ax=ax)
        cb.set_label("φ (n/cm²·s) — escala log", color="white")
        cb.ax.yaxis.set_tick_params(color="white", labelcolor="white")
        ax.set_xlabel("x (cm)", color="white")
        ax.set_ylabel("y (cm)", color="white")
        ax.tick_params(colors="white")
        ax.set_title(f"{titulo}\n{etiqueta}\norigen: {origen} · backend: matplotlib "
                     f"(PyVista/VTK declarado pendiente de instalación en el entorno)",
                     color="white", fontsize=11)
        for s in ax.spines.values():
            s.set_color("#30363d")
        fig.tight_layout()
        fig.savefig(salida_png, facecolor=fig.get_facecolor())
        plt.close(fig)
    else:
        raise ValueError("backend debe ser auto|pyvista|matplotlib")

    return {"png": salida_png, "origen": origen, "etiqueta": etiqueta,
            "backend_usado": backend,
            "celdas": [int(fl.shape[0]), int(fl.shape[1])],
            "flujo_max": float(fl.max())}


if __name__ == "__main__":
    import json
    print(json.dumps(render_heatmap("/tmp/mesh_heatmap_demo.png",
                                    origen="declarado_demo"), indent=2))
