"""Las pruebas que importan app.main no deben escribir en data/costos/corridas.json (archivo versionado)."""

import os
import shutil
import tempfile
from pathlib import Path

_tmp = Path(tempfile.mkdtemp(prefix="rpos-costos-"))
_src = Path(__file__).resolve().parents[1] / "data/costos/corridas.json"
shutil.copy(_src, _tmp / "corridas.json")
os.environ.setdefault("RPOS_COSTOS_CORRIDAS", str(_tmp / "corridas.json"))
