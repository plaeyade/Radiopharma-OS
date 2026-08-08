"""
Ejecutor del código TALYS (segunda fuente teórica de σ(E)).

TALYS es software abierto (IAEA-NDS / A. Koning) de reacciones
nucleares: calcula funciones de excitación sin necesitar datos de
planta — su entrada son modelos físicos. El binario se localiza con
la variable de entorno TALYS_CMD o en el PATH (mismo patrón que
VERAPDF_CMD).

El parser de salidas rp*.tot tolera cualquier cabecera: ignora
líneas de comentario y toma las dos primeras columnas numéricas
(E en MeV, σ en mb).
"""
from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

# Z atómico para los elementos relevantes del MVP (y los más comunes).
Z_TABLE: dict[str, int] = {
    "h": 1, "he": 2, "li": 3, "be": 4, "b": 5, "c": 6, "n": 7, "o": 8,
    "f": 9, "ne": 10, "na": 11, "mg": 12, "al": 13, "si": 14, "p": 15,
    "s": 16, "cl": 17, "ar": 18, "k": 19, "ca": 20, "sc": 21, "ti": 22,
    "v": 23, "cr": 24, "mn": 25, "fe": 26, "co": 27, "ni": 28, "cu": 29,
    "zn": 30, "ga": 31, "ge": 32, "as": 33, "se": 34, "br": 35, "kr": 36,
    "rb": 37, "sr": 38, "y": 39, "zr": 40, "nb": 41, "mo": 42, "tc": 43,
    "ru": 44, "rh": 45, "pd": 46, "ag": 47, "cd": 48, "in": 49, "sn": 50,
    "sb": 51, "te": 52, "i": 53, "xe": 54, "cs": 55, "ba": 56, "lu": 71,
    "hf": 72, "ta": 73, "w": 74, "re": 75, "os": 76, "ir": 77, "pt": 78,
    "au": 79, "hg": 80, "tl": 81, "pb": 82, "bi": 83,
}


class TalysUnavailable(RuntimeError):
    """El binario TALYS no está disponible en este entorno."""


def product_rp_file(product_nuclide: str) -> str:
    """Archivo rp*.tot del producto: 18F -> rp009018.tot."""
    i = 0
    while i < len(product_nuclide) and product_nuclide[i].isdigit():
        i += 1
    mass = int(product_nuclide[:i])
    symbol = product_nuclide[i:].lower()
    z = Z_TABLE.get(symbol)
    if z is None:
        raise ValueError(f"elemento desconocido en '{product_nuclide}'")
    return f"rp{z:03d}{mass:03d}.tot"


def parse_rp_tot(path: Path) -> list[tuple[float, float]]:
    """Parsea un rp*.tot: lista de (E_mev, sigma_mb)."""
    points: list[tuple[float, float]] = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        parts = s.split()
        if len(parts) < 2:
            continue
        try:
            e, xs = float(parts[0]), float(parts[1])
        except ValueError:
            continue
        points.append((e, xs))
    if not points:
        raise ValueError(f"sin puntos numéricos en {path}")
    points.sort(key=lambda p: p[0])
    return points


def build_input(projectile: str, element: str, mass: int,
                emin_mev: float = 0.1, emax_mev: float = 30.0,
                step_mev: float = 0.5) -> str:
    """Input TALYS mínimo para función de excitación (p,x).
    Sintaxis TALYS 2.x: `energy emin emax paso` (paso en MeV)."""
    if mass <= 0:
        raise ValueError("mass debe ser positiva")
    if not 0 < emin_mev < emax_mev:
        raise ValueError("rango de energía inválido")
    if step_mev <= 0 or step_mev >= (emax_mev - emin_mev):
        raise ValueError("step_mev debe ser positivo y menor que el rango")
    return (
        f"projectile {projectile}\n"
        f"element {element.lower()}\n"
        f"mass {mass}\n"
        f"energy {emin_mev:.6g} {emax_mev:.6g} {step_mev:.6g}\n"
    )


class TalysRunner:
    """Ejecuta TALYS en un directorio de trabajo y localiza salidas."""

    def __init__(self, cmd: str | None = None) -> None:
        self._cmd = cmd or os.environ.get("TALYS_CMD") or shutil.which("talys")

    @property
    def cmd(self) -> str | None:
        return self._cmd

    def available(self) -> bool:
        return self._cmd is not None

    def version(self) -> str | None:
        if not self._cmd:
            return None
        try:
            out = subprocess.run([self._cmd, "-h"], capture_output=True,
                                 text=True, timeout=15)
            head = (out.stdout or out.stderr).splitlines()[:1]
            return head[0].strip() if head else "talys"
        except Exception:
            return "talys"

    def run(self, workdir: Path, input_text: str,
            rp_file: str, timeout_s: int = 1800) -> Path:
        """Ejecuta TALYS y devuelve la ruta del rp*.tot esperado."""
        if not self._cmd:
            raise TalysUnavailable(
                "binario TALYS no encontrado (TALYS_CMD ni PATH)")
        workdir.mkdir(parents=True, exist_ok=True)
        (workdir / "talys.inp").write_text(input_text, encoding="utf-8")
        with open(workdir / "talys.log", "w", encoding="utf-8") as log:
            proc = subprocess.run(
                [self._cmd], cwd=workdir,
                stdin=open(workdir / "talys.inp"),
                stdout=log, stderr=subprocess.STDOUT, timeout=timeout_s)
        rp = workdir / rp_file
        if proc.returncode != 0 or not rp.is_file():
            raise RuntimeError(
                f"TALYS falló (rc={proc.returncode}), ver {workdir/'talys.log'}")
        return rp
