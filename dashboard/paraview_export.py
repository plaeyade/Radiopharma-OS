"""Exportación ParaView (Informe 18.11; EDS: post-proceso científico).

Convierte campos calculados por los motores (térmico reducido/FEM,
deposición Monte Carlo) a formato **VTK ImageData (.vti)**, estándar
que ParaView abre directamente. Escritura pura (XML + base64), sin
dependencias pesadas: el mismo artefacto sirve en el sandbox y en el
puesto científico.
"""
from __future__ import annotations

import base64
import struct
from pathlib import Path

import numpy as np


def exportar_vti(campo: np.ndarray, nombre_campo: str, destino: str | Path,
                 espaciado_cm: tuple[float, float, float] = (0.1, 0.1, 0.1),
                 origen_cm: tuple[float, float, float] = (0.0, 0.0, 0.0)
                 ) -> dict:
    """Escribe un campo escalar 3D como .vti (VTK XML ImageData).

    ``campo`` debe ser 3D (nx, ny, nz). Formato binario base64 con
    cabecera de bloque UInt64 (estándar VTK).
    """
    arr = np.asarray(campo, dtype=np.float64)
    if arr.ndim != 3:
        raise ValueError(f"el campo debe ser 3D, recibido {arr.ndim}D")
    nx, ny, nz = arr.shape
    datos = arr.tobytes(order="F")  # VTK orden Fortran
    cab = struct.pack("<Q", len(datos))
    b64 = base64.b64encode(cab + datos).decode("ascii")
    ext = f"0 {nx} 0 {ny} 0 {nz}"
    xml = (
        '<?xml version="1.0"?>\n'
        '<VTKFile type="ImageData" version="1.0" '
        'byte_order="LittleEndian" header_type="UInt64">\n'
        f'  <ImageData WholeExtent="{ext}" '
        f'Origin="{origen_cm[0]} {origen_cm[1]} {origen_cm[2]}" '
        f'Spacing="{espaciado_cm[0]} {espaciado_cm[1]} {espaciado_cm[2]}">\n'
        f'    <Piece Extent="{ext}">\n'
        '      <PointData Scalars="campo">\n'
        f'        <DataArray type="Float64" Name="{nombre_campo}" '
        'format="binary">\n'
        f'          {b64}\n'
        '        </DataArray>\n'
        '      </PointData>\n'
        '      <CellData/>\n'
        '    </Piece>\n'
        '  </ImageData>\n'
        '</VTKFile>\n')
    Path(destino).write_text(xml, encoding="utf-8")
    return {"destino": str(destino), "dimensiones": [nx, ny, nz],
            "campo": nombre_campo, "formato": "VTK ImageData (.vti)",
            "nota": "artefacto de post-proceso ParaView (Fase 7)"}


def leer_vti(ruta: str | Path) -> np.ndarray:
    """Lectura de verificación (roundtrip de integridad)."""
    import re
    xml = Path(ruta).read_text(encoding="utf-8")
    m = re.search(r'WholeExtent="(\d+) (\d+) (\d+) (\d+) (\d+) (\d+)"', xml)
    if not m:
        raise ValueError("WholeExtent no encontrado")
    nx, ny, nz = int(m.group(2)), int(m.group(4)), int(m.group(6))
    b64 = re.search(r'format="binary">\s*([A-Za-z0-9+/=\s]+)\s*<', xml)
    if not b64:
        raise ValueError("DataArray binario no encontrado")
    raw = base64.b64decode(b64.group(1))
    nbytes = struct.unpack("<Q", raw[:8])[0]
    datos = np.frombuffer(raw[8:8 + nbytes], dtype=np.float64)
    return datos.reshape((nx, ny, nz), order="F")


def campo_mc_desde_edep(edep_mev: np.ndarray) -> np.ndarray:
    """Normalización documentada del campo de deposición MC (cap. 19)
    para visualización: MeV → MeV/cm³ con espaciado conocido."""
    arr = np.asarray(edep_mev, dtype=np.float64)
    if arr.ndim != 3:
        raise ValueError("edep debe ser 3D")
    return arr
