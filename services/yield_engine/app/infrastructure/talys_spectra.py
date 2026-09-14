"""Espectros de emisión neutrónica con TALYS (EDS 19.12, 19.14).

TALYS (IAEA-NDS / A.J. Koning, software abierto) calcula el espectro de
emisión de neutrones (p,xn) de una reacción con modelos físicos reales
— evaporación (compound) + pre-equilibrio + directo. El binario se
localiza con TALYS_CMD o en el PATH (mismo patrón que Elmer/TraceWin):
si no existe, los endpoints que lo requieren responden 503 con estado
honesto — la plataforma NUNCA inventa un espectro neutrónico.

Los resultados se cachean como dato versionado (JSON con fuente,
versión de TALYS, fecha y sha256 implícito del contenido): una misma
energía nunca se recalcula ni se sobrescribe — se reutiliza el registro.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path

Z_TABLE: dict[str, int] = {
    "h": 1, "he": 2, "li": 3, "be": 4, "b": 5, "c": 6, "n": 7, "o": 8,
    "f": 9, "ne": 10, "na": 11, "mg": 12, "al": 13, "si": 14, "p": 15,
    "s": 16, "cl": 17, "ar": 18, "k": 19, "ca": 20, "sc": 21, "ti": 22,
    "v": 23, "cr": 24, "mn": 25, "fe": 26, "co": 27, "ni": 28, "cu": 29,
    "zn": 30, "ga": 31, "ge": 32, "as": 33, "se": 34, "br": 35,
}


class TalysUnavailable(RuntimeError):
    """El binario TALYS no está disponible en este entorno."""


class TalysError(RuntimeError):
    """TALYS se ejecutó pero no produjo el espectro esperado."""


def parse_nspec(text: str) -> dict:
    """Parsea un archivo nspecEEEE.EEE.tot real de TALYS-2.x.

    Devuelve los puntos (E_out MeV, dσ/dE' mb/MeV) y las componentes
    (directo, pre-equilibrio, compound) tal como las escribe TALYS —
    nunca valores de relleno.
    """
    puntos: list[tuple[float, float]] = []
    directo = preeq = compound = 0.0
    e_prev = None
    for linea in text.splitlines():
        s = linea.strip()
        if not s or s.startswith("#"):
            continue
        toks = s.split()
        if len(toks) < 2:
            continue
        try:
            vals = [float(t) for t in toks]
        except ValueError:
            continue
        e_out, xs = vals[0], vals[1]
        puntos.append((e_out, xs))
        if e_prev is not None:
            de = e_out - e_prev
            if len(vals) >= 6:
                directo += 0.5 * (vals[2] + prev[2]) * de
                preeq += 0.5 * (vals[3] + prev[3]) * de
                compound += 0.5 * (vals[5] + prev[5]) * de
        prev = vals
        e_prev = e_out
    if not puntos:
        raise TalysError("nspec sin puntos numéricos — salida inesperada")
    sigma = 0.0
    for (e0, s0), (e1, s1) in zip(puntos, puntos[1:]):
        sigma += 0.5 * (s0 + s1) * (e1 - e0)
    return {"puntos": puntos, "sigma_total_mb": sigma,
            "componentes_mb": {"directo": directo, "preequilibrio": preeq,
                               "compound": compound}}


class TalysSpectraRunner:
    """Ejecuta TALYS y cachea espectros (p,xn) como dato versionado."""

    def __init__(self, cache_dir: Path, cmd: str | None = None,
                 timeout_s: int = 300) -> None:
        self._cmd = cmd or os.environ.get("TALYS_CMD")
        self._cache = Path(cache_dir)
        self._cache.mkdir(parents=True, exist_ok=True)
        self._timeout = timeout_s

    def _binario(self) -> str:
        cmd = self._cmd or shutil.which("talys")
        if not cmd or (self._cmd and not Path(cmd).exists()):
            raise TalysUnavailable(
                "TALYS no disponible (sin_runtime): configurar TALYS_CMD "
                "o instalar TALYS (IAEA-NDS) — la plataforma nunca "
                "simula un espectro neutrónico")
        return cmd

    def available(self) -> bool:
        try:
            self._binario()
            return True
        except TalysUnavailable:
            return False

    def espectro(self, element: str, mass: int,
                 energy_mev: float) -> dict:
        """Espectro (p,xn) real a una energía (con caché versionado)."""
        clave = f"{element.lower()}{mass}_p_xn_{energy_mev:g}MeV"
        ruta = self._cache / f"{clave}.json"
        if ruta.exists():
            return json.loads(ruta.read_text())
        if Z_TABLE.get(element.lower()) is None:
            raise TalysError(f"elemento desconocido: {element}")
        binario = self._binario()
        inp = (f"projectile p\nelement {element.lower()}\nmass {mass}\n"
               f"energy {energy_mev}\nfilespectrum n\noutspectra y\n")
        with tempfile.TemporaryDirectory(prefix="talys_nspec_") as tmp:
            tmp_p = Path(tmp)
            env = dict(os.environ)
            talysdir = os.environ.get("TALYSDIR")
            if talysdir:
                env["TALYSDIR"] = talysdir
            proc = subprocess.run([binario], input=inp, cwd=tmp_p,
                                  capture_output=True, text=True,
                                  timeout=self._timeout, env=env)
            if proc.returncode != 0:
                raise TalysError(
                    f"TALYS rc={proc.returncode}: {proc.stdout[-400:]}")
            candidatos = sorted(tmp_p.glob("nspec*.tot"))
            if not candidatos:
                raise TalysError(
                    "TALYS no generó nspec*.tot — espectro no_demostrable")
            parsed = parse_nspec(candidatos[0].read_text())
        registro = {
            "reaccion": f"p+{mass}{element}",
            "energia_mev": energy_mev,
            "sigma_n_total_mb": round(parsed["sigma_total_mb"], 4),
            "componentes_mb": {k: round(v, 4)
                               for k, v in parsed["componentes_mb"].items()},
            "espectro": [[round(e, 6), round(s, 6)]
                         for e, s in parsed["puntos"]],
            "fuente": "TALYS-2 (IAEA-NDS / A.J. Koning) — ejecución real",
            "talys_cmd": binario,
            "ejecutado_en": datetime.now(timezone.utc).isoformat(),
        }
        ruta.write_text(json.dumps(registro, ensure_ascii=False, indent=2))
        return registro
