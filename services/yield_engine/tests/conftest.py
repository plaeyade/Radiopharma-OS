"""Aislar el estado mutable del servicio durante las pruebas.

Las pruebas que importan app.main registraban tablas de stopping de prueba en
data/stopping/external (versionado) y en calibrations.json: el manifiesto llegó a 85 tablas,
84 de ellas de pruebas. Aquí se redirige ese estado a un directorio temporal.
"""

import os
import shutil
import tempfile
from pathlib import Path

_tmp = Path(tempfile.mkdtemp(prefix="rpos-ye-"))
_data = Path(__file__).resolve().parents[1] / "data"
shutil.copytree(_data / "stopping" / "external", _tmp / "external")
os.environ.setdefault("YE_STOPPING_EXTERNAL", str(_tmp / "external"))
os.environ.setdefault("YE_CALIBRATION_STORE", str(_tmp / "calibrations.json"))


# --- Evidencia externa (RPOS_AGENTS_ROOT) -------------------------------------------------
# Varias fases leen evidencia que vive fuera de git (por defecto /mnt/agents, configurable con
# RPOS_AGENTS_ROOT). Las pruebas que fallan porque falta un archivo bajo esa raíz se reportan
# como OMITIDAS con el motivo, no como fallos.
# RPOS_REQUIRE_EVIDENCIA=1 desactiva la omisión (equipo con la evidencia restaurada).
import os as _os

import pytest as _pytest

_RAIZ = _os.environ.get("RPOS_AGENTS_ROOT", "/mnt/agents")


def _evidencia_ausente(exc) -> bool:
    if _os.environ.get("RPOS_REQUIRE_EVIDENCIA") == "1":
        return False
    while exc is not None:
        if isinstance(exc, FileNotFoundError) and str(getattr(exc, "filename", "") or "").startswith(_RAIZ):
            return True
        exc = exc.__cause__ or exc.__context__
    return False


@_pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    rep = outcome.get_result()
    if call.excinfo is not None and rep.failed and _evidencia_ausente(call.excinfo.value):
        rep.outcome = "skipped"
        rep.longrepr = (str(item.path), item.location[1] or 0, f"evidencia externa ausente ({_RAIZ})")


@_pytest.hookimpl(hookwrapper=True)
def pytest_make_collect_report(collector):
    outcome = yield
    rep = outcome.get_result()
    if rep.failed and getattr(rep, "longrepr", None) is not None and _RAIZ in str(rep.longrepr) \
            and "FileNotFoundError" in str(rep.longrepr) and _evidencia_ausente(FileNotFoundError(2, "", _RAIZ)):
        rep.outcome = "skipped"
        rep.longrepr = (str(collector.path), 0, f"evidencia externa ausente ({_RAIZ})")
        rep.result = []
