"""
Ejecutor de ElmerSolver (acoplamiento FEM del Burnup/Thermal Engine).

Elmer (ElmerFEM, CSC IT Center for Science, GPL) es el motor FEM
abierto del Physics Twin: resuelve la ecuación del calor 2D
axisimétrica del blanco con el haz gaussiano como fuente. El binario se
localiza con la variable de entorno ELMER_CMD o en el PATH (mismo
patrón que TALYS_CMD y VERAPDF_CMD): si no existe, los endpoints que lo
requieren responden 503 con estado honesto — nunca se simula un
resultado FEM.

Parser de SaveScalars tolerante: ignora comentarios/cabeceras, toma la
última fila numérica y descarta la primera columna (índice de paso), de
modo que los valores quedan en el orden declarado en el SIF
(max Temperature, mean Temperature).
"""
from __future__ import annotations

import os
import shlex
import shutil
import subprocess
from pathlib import Path


class ElmerUnavailable(RuntimeError):
    """El binario ElmerSolver no está disponible en este entorno."""


class ElmerError(RuntimeError):
    """ElmerSolver se ejecutó pero no produjo resultados válidos."""


def parse_save_scalars(text: str, names_text: str | None = None) -> list[float]:
    """Parsea la salida de SaveScalars: última fila numérica.

    Si se facilita el contenido de `scalars.dat.names` (formato real de
    Elmer), se usa el nº de variables declarado para decidir si la fila
    lleva una columna inicial de paso/tiempo (transitorio) o no
    (estacionario: todas las columnas son variables). Sin `.names` se
    asume el formato con paso inicial (compatibilidad histórica)."""
    n_vars: int | None = None
    if names_text is not None:
        count = 0
        for line in names_text.splitlines():
            s = line.strip()
            if s and s[0].isdigit() and ":" in s:
                try:
                    count = max(count, int(s.split(":", 1)[0]))
                except ValueError:
                    pass
        n_vars = count or None
    last_row: list[float] | None = None
    for line in text.splitlines():
        s = line.strip()
        if not s or s.startswith(("!", "#", "res:", "name:")):
            continue
        try:
            row = [float(tok) for tok in s.split()]
        except ValueError:
            continue
        if len(row) >= 1:
            last_row = row
    if last_row is None:
        raise ValueError("SaveScalars sin filas de datos")
    if n_vars is not None:
        if len(last_row) == n_vars:
            return last_row
        if len(last_row) == n_vars + 1:
            return last_row[1:]
        raise ValueError(
            f"fila de {len(last_row)} columnas incompatible con "
            f"{n_vars} variables declaradas en scalars.dat.names")
    if len(last_row) < 2:
        raise ValueError("SaveScalars sin columnas de datos")
    return last_row[1:]


class ElmerRunner:
    """Localiza y ejecuta ElmerSolver sobre un caso (malla + SIF)."""

    def __init__(self, cmd: str | None = None, timeout_s: float = 120.0) -> None:
        self._cmd = shlex.split(
            cmd or os.environ.get("ELMER_CMD") or "ElmerSolver")
        self._timeout = timeout_s

    @property
    def cmd_label(self) -> str:
        return " ".join(self._cmd)

    def available(self) -> bool:
        return shutil.which(self._cmd[0]) is not None

    def version(self) -> str | None:
        """Versión reportada por el binario (None si no se puede saber)."""
        if not self.available():
            return None
        for flag in ("--version", "-v"):
            try:
                proc = subprocess.run(
                    [*self._cmd, flag], capture_output=True, text=True,
                    timeout=10, check=False)
            except (OSError, subprocess.TimeoutExpired):
                continue
            out = (proc.stdout or proc.stderr).strip().splitlines()
            if proc.returncode == 0 and out:
                return out[0][:120]
        return None

    def run(self, case_dir: Path) -> list[float]:
        """Ejecuta `ElmerSolver case.sif` en case_dir y devuelve los
        escalares (max/mean Temperature)."""
        if not self.available():
            raise ElmerUnavailable(
                f"ElmerSolver no disponible (cmd: {self._cmd[0]})")
        log_path = case_dir / "elmer.log"
        with open(log_path, "w", encoding="utf-8") as log:
            proc = subprocess.run(
                [*self._cmd, "case.sif"], cwd=case_dir,
                stdout=log, stderr=subprocess.STDOUT, text=True,
                timeout=self._timeout, check=False)
        scalars = case_dir / "scalars.dat"
        if proc.returncode != 0:
            raise ElmerError(
                f"ElmerSolver rc={proc.returncode}; ver {log_path}")
        if not scalars.exists():
            raise ElmerError(
                f"ElmerSolver no generó scalars.dat; ver {log_path}")
        names = case_dir / "scalars.dat.names"
        return parse_save_scalars(
            scalars.read_text(encoding="utf-8"),
            names.read_text(encoding="utf-8") if names.exists() else None)
