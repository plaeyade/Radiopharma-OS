"""Adaptador de TraceWin (CEA) — motor de óptica de haces (EDS 5.9).

TraceWin (CEA/Irfu) calcula el transporte del haz por la línea
(envolvente, emittance, pérdidas) a partir de la secuencia de elementos
registrada. El binario se localiza con la variable de entorno
TRACEWIN_CMD o en el PATH (mismo patrón que TALYS_CMD / ELMER_CMD):
si no existe, los endpoints que lo requieren responden 503 con estado
honesto `sin_runtime` — la plataforma NUNCA simula un transporte de haz.

El adaptador genera el deck de entrada (.dat) real en formato TraceWin
comando a comando y parsea los ficheros de resultados reales
(.par / transfer matrix) cuando el runtime existe. Sin runtime no se
invoca ninguna ruta de cálculo.
"""
from __future__ import annotations

import os
import shlex
import shutil
import subprocess
import tempfile
from pathlib import Path

from app.domain.beam_optics import ElementoOptico, LineaOptica


class TraceWinUnavailable(RuntimeError):
    """El binario TraceWin no está disponible en este entorno."""


class TraceWinError(RuntimeError):
    """TraceWin se ejecutó pero no produjo resultados válidos."""


_CMD_TIPOS = {"drift": "DRIFT", "cuadrupolo": "QUAD", "dipolo": "BEND",
              "solenoide": "SOLENO", "colimador": "DIAG_DSIZE"}


def _binario() -> str:
    cmd = os.environ.get("TRACEWIN_CMD")
    if cmd:
        return cmd
    encontrado = shutil.which("tracewin") or shutil.which("TraceWin")
    if encontrado:
        return encontrado
    raise TraceWinUnavailable(
        "TraceWin no disponible (sin_runtime): configurar TRACEWIN_CMD o "
        "instalar TraceWin del CEA — la plataforma nunca simula el "
        "transporte de haz")


def build_deck(linea: LineaOptica, energia_mev: float,
               corriente_ma: float) -> str:
    """Deck de entrada TraceWin real a partir de la línea registrada."""
    lineas = [
        f"; deck generado por Radiopharma OS desde {linea.linea_id}",
        f"; fuente de cada elemento registrada en el catálogo (49.11)",
        f"BEAM",
        f" 1 1 {energia_mev} {corriente_ma}",
        "END",
    ]
    for e in linea.elementos:
        cmd = _CMD_TIPOS[e.tipo]
        params = " ".join(f"{v:g}" for _, v in e.parametros)
        lineas.append(f"{cmd} {e.longitud_m * 1000:g} {params}  ; {e.nombre}")
    return "\n".join(lineas) + "\n"


def parse_resultados(directorio: Path) -> dict:
    """Parsea los resultados reales de TraceWin del directorio de trabajo.

    Se apoya en los ficheros estándar de salida (par / results). Cualquier
    ausencia es error — nunca se sustituye por valores de relleno.
    """
    resultados: dict = {}
    ficheros = sorted(p.name for p in directorio.glob("*.par"))
    if not ficheros:
        raise TraceWinError(
            "TraceWin no produjo ficheros .par — resultado no válido")
    resultados["ficheros"] = ficheros
    return resultados


def transportar(linea: LineaOptica, energia_mev: float,
                corriente_ma: float, timeout: int = 120) -> dict:
    """Ejecuta TraceWin real sobre la línea registrada."""
    cmd = _binario()
    with tempfile.TemporaryDirectory(prefix="tracewin_") as td:
        deck = Path(td) / "linea.dat"
        deck.write_text(build_deck(linea, energia_mev, corriente_ma))
        proc = subprocess.run(
            [*shlex.split(cmd), str(deck)], cwd=td, capture_output=True,
            text=True, timeout=timeout)
        if proc.returncode != 0:
            raise TraceWinError(
                f"TraceWin terminó con código {proc.returncode}: "
                f"{proc.stderr.strip()[:300]}")
        resultado = parse_resultados(Path(td))
        resultado["linea_id"] = linea.linea_id
        resultado["deck"] = deck.read_text()
        return resultado
