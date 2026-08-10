"""Vistas 3D con PyVista (Informe 18.11; EDS: mallas PyVista/ParaView).

Visualización 3D del blanco del ciclotrón y de los campos calculados
(térmico reducido, deposición Monte Carlo). La construcción de la
malla (geometría + campo escalar) es testable sin el runtime
PyVista; el render requiere el runtime real y reporta su ausencia
honestamente (patrón de plataforma).
"""
from __future__ import annotations

import importlib.util
import math

import numpy as np

PYVISTA_DISPONIBLE = importlib.util.find_spec("pyvista") is not None


def malla_blanco(radio_cm: float = 1.0, espesor_cm: float = 0.5,
                 n_theta: int = 48, n_z: int = 12) -> dict:
    """Malla cilíndrica del blanco (pura numpy; testable sin PyVista).

    Devuelve vértices y la parametrización para el campo escalar.
    """
    if radio_cm <= 0 or espesor_cm <= 0:
        raise ValueError("geometría del blanco inválida")
    theta = np.linspace(0.0, 2.0 * math.pi, n_theta)
    z = np.linspace(-espesor_cm / 2.0, espesor_cm / 2.0, n_z)
    tt, zz = np.meshgrid(theta, z)
    xs = radio_cm * np.cos(tt)
    ys = radio_cm * np.sin(tt)
    return {"vertices": np.stack([xs, ys, zz], axis=-1),
            "theta": tt, "z": zz, "radio_cm": radio_cm,
            "espesor_cm": espesor_cm}


def campo_termico_analitico(malla: dict, potencia_w: float,
                            conductividad_w_cm_k: float = 0.006,
                            t_refrigerante_k: float = 293.15) -> np.ndarray:
    """Perfil parabólico conservador del modelo térmico reducido
    (cap. 18: cota 1D) mapeado sobre la superficie del blanco.

    T(r) = T_cool + q'''·R²/(4k)·(1−r²/R²) con q''' = P/V.
    """
    volumen = math.pi * malla["radio_cm"] ** 2 * malla["espesor_cm"]
    q_v = potencia_w / volumen
    r = malla["radio_cm"]
    delta_t = q_v * r ** 2 / (4.0 * conductividad_w_cm_k)
    # en la superficie cilíndrica el perfil axial es uniforme: el pico
    # está en el eje; la superficie lateral queda a T_cool + ΔT/2
    return t_refrigerante_k + 0.5 * delta_t * np.ones_like(malla["z"])


def render_vista(malla: dict, campo: np.ndarray, destino_html: str) -> dict:
    """Render 3D interactivo (HTML) con PyVista real.

    Sin runtime: RuntimeError honesto (nunca se simula el render).
    """
    if not PYVISTA_DISPONIBLE:
        raise RuntimeError(
            "runtime PyVista no instalado: las vistas 3D se generan en "
            "el despliegue de dashboards (Fase 7); la malla y el campo "
            "se validan sin runtime en pipelines/test_dashboards.py")
    import pyvista as pv  # noqa: WPS433

    verts = malla["vertices"]
    nz, nt = verts.shape[:2]
    grid = pv.StructuredGrid()
    pts = verts.reshape(-1, 3)
    grid.points = pts
    grid.dimensions = [nt, nz, 1]
    grid["temperatura_k"] = campo.reshape(-1)
    plotter = pv.Plotter(off_screen=True)
    plotter.add_mesh(grid, scalars="temperatura_k", cmap="inferno")
    plotter.export_html(destino_html)
    return {"destino": destino_html, "n_puntos": int(pts.shape[0]),
            "pyvista_version": pv.__version__}
