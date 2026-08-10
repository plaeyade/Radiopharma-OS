"""
Ejecutor de OpenGATE/Geant4 (Monte Carlo Interface, cap. 19).

OpenGATE (Opengate Collaboration, Apache-2.0) sobre Geant4 (CERN,
licencia Geant4) es el motor Monte Carlo oficial del Physics Twin
(19.1): transporte explícito de partículas para validación de alta
fidelidad, dosimetría y estudios de diseño. No sustituye al flujo
operativo diario (19.3): los motores deterministas siguen siendo la
vía rutinaria; el MC se emplea para validación, diseño e investigación.

Localización honesta del motor (mismo patrón que TALYS_CMD, ELMER_CMD
y VERAPDF_CMD): la variable de entorno OPENGATE_PYTHON apunta al
intérprete Python donde `import opengate` funciona; si no existe o el
import falla, los endpoints que lo requieren responden 503 con estado
honesto — nunca se simula un resultado Monte Carlo.
"""
from __future__ import annotations

import os
import subprocess
from pathlib import Path


class GateUnavailable(RuntimeError):
    """OpenGATE/Geant4 no está disponible en este entorno."""


class GateError(RuntimeError):
    """OpenGATE se ejecutó pero no produjo resultados válidos."""


class GateRunner:
    """Ejecuta scripts OpenGATE como subproceso aislado (Run Manager 19.5).

    El script generado por `gate_case.build_case` escribe
    `mc_results.json` con las magnitudes del Scoring Manager; el runner
    solo verifica su existencia y devuelve la ruta junto con el log.

    `env_extra` propaga la configuración de datos Geant4 (GATEONRTD=1
    para omitir la auto-descarga del wheel y señalar las rutas de los
    datasets instalados explícitamente — ver `build_gate_env`).
    """

    def __init__(self, python_cmd: str | None = None, timeout_s: int = 1800,
                 env_extra: dict | None = None) -> None:
        self.python_cmd = python_cmd or os.environ.get("OPENGATE_PYTHON", "python3")
        self.timeout_s = timeout_s
        self.env_extra = dict(env_extra or {})
        self._available: bool | None = None
        self._versions: dict | None = None

    def _env(self) -> dict:
        env = dict(os.environ)
        env.update(self.env_extra)
        return env

    @property
    def cmd_label(self) -> str:
        return f"{self.python_cmd} (+opengate)"

    def check(self, force: bool = False) -> bool:
        """Disponibilidad real: el intérprete importa opengate (19.24)."""
        if self._available is not None and not force:
            return self._available
        code = (
            "import json,re,opengate,opengate_core as c;"
            "from importlib.metadata import version as _v;"
            "from pathlib import Path;"
            "g4='unknown';"
            "_so=next(Path(c.__file__).parent.glob('opengate_core*.so'),None);"
            "_b=_so.read_bytes() if _so else b'';"
            "_m=re.search(rb'geant4-(\\d+)-(\\d+)-patch-(\\d+)',_b);"
            "_m=_m or re.search(rb'geant4-(\\d+)-(\\d+)',_b);"
            "g4='.'.join(str(int(g)) for g in _m.groups() if g) if _m else g4;"
            "print(json.dumps({'opengate':_v('opengate'),'geant4':g4}))"
        )
        try:
            proc = subprocess.run(
                [self.python_cmd, "-c", code],
                capture_output=True, text=True, timeout=120, env=self._env(),
            )
            import json as _json

            self._versions = _json.loads(proc.stdout.strip().splitlines()[-1]) if proc.returncode == 0 else None
            self._available = proc.returncode == 0
        except Exception:
            self._versions = None
            self._available = False
        return self._available

    def versions(self) -> dict:
        if self._versions is None and not self.check():
            raise GateUnavailable(
                f"OpenGATE no disponible con {self.python_cmd!r}: defina OPENGATE_PYTHON "
                "apuntando a un intérprete con opengate instalado (cap. 19.4)."
            )
        return self._versions or {}

    def run(self, script_path: Path, work_dir: Path) -> str:
        """Ejecuta el caso; devuelve el log completo (stdout+stderr).

        Lanza GateError si el proceso falla o no genera `mc_results.json`
        (las simulaciones incompletas no se incorporan al Data Lake, 19.21).
        """
        try:
            proc = subprocess.run(
                [self.python_cmd, str(script_path)],
                cwd=str(work_dir), capture_output=True, text=True,
                timeout=self.timeout_s, env=self._env(),
            )
        except FileNotFoundError as exc:
            raise GateUnavailable(f"intérprete no encontrado: {self.python_cmd}") from exc
        except subprocess.TimeoutExpired as exc:
            raise GateError(f"OpenGATE superó el tiempo máximo ({self.timeout_s}s)") from exc
        log = (proc.stdout or "") + ("\n" + proc.stderr if proc.stderr else "")
        if proc.returncode != 0:
            raise GateError(f"OpenGATE rc={proc.returncode}: {log[-800:]}")
        if not (work_dir / "mc_results.json").exists():
            raise GateError("OpenGATE terminó sin generar mc_results.json (simulación incompleta, 19.21)")
        return log


# Datasets Geant4 requeridos por las listas FTFP_BERT (referencia Geant4,
# 19.9) para protones en blanco líquido. Las listas _HP (QGSP_BIC_HP,
# QGSP_BERT_HP) requieren además G4NDL (datos de neutrones HP): el estado
# se reporta en /mc/status de forma honesta.
G4_DATASET_VARS = {
    "G4LEDATA": "G4EMLOW8.8",
    "G4LEVELGAMMADATA": "PhotonEvaporation6.1.2",
    "G4RADIOACTIVEDATA": "RadioactiveDecay6.1.2",
    "G4PARTICLEXSDATA": "G4PARTICLEXS4.2",
    "G4PIIDATA": "G4PII1.3",
    "G4SAIDXSDATA": "G4SAIDDATA2.0",
    "G4ABLADATA": "G4ABLA3.3",
    "G4INCLDATA": "G4INCL1.3",
    "G4ENSDFSTATEDATA": "G4ENSDFSTATE3.0",
}
G4_HP_DATASET = ("G4NEUTRONHPDATA", "G4NDL4.7.1")


def build_gate_env(gatepy_dir: str | None = None, g4data_dir: str | None = None) -> dict:
    """Entorno para ejecutar OpenGATE instalado en `gatepy_dir`.

    - GATEONRTD=1 omite la auto-descarga del wheel: los datasets se
      instalan explícitamente (descarga controlada y registrada) y sus
      rutas se exportan aquí; los ausentes simplemente no se definen y
      Geant4 fallará con honestidad si una física los requiere.
    - GLIBC_TUNABLES reserva TLS estático (requisito del wheel
      manylinux de opengate-core para cargar libG4*).
    """
    gatepy = Path(gatepy_dir or os.environ.get("GATEPY_DIR", "/tmp/gatepy"))
    g4data = Path(g4data_dir or os.environ.get("G4DATA_DIR", str(gatepy / "opengate_core" / "geant4_data")))
    env: dict[str, str] = {
        "GATEONRTD": "1",
        "GLIBC_TUNABLES": "glibc.rtld.optional_static_tls=2000000",
        "PYTHONPATH": str(gatepy) + (":" + os.environ["PYTHONPATH"] if os.environ.get("PYTHONPATH") else ""),
        "LD_LIBRARY_PATH": str(gatepy / "opengate_core.libs")
        + (":" + os.environ["LD_LIBRARY_PATH"] if os.environ.get("LD_LIBRARY_PATH") else ""),
    }
    for var, folder in G4_DATASET_VARS.items():
        if (g4data / folder).is_dir():
            env[var] = str(g4data / folder)
    hp_var, hp_folder = G4_HP_DATASET
    if (g4data / hp_folder).is_dir():
        env[hp_var] = str(g4data / hp_folder)
    return env


def datasets_instalados(g4data_dir: str | None = None) -> dict:
    """Inventario honesto de datasets (19.24): qué física es ejecutable."""
    gatepy = Path(os.environ.get("GATEPY_DIR", "/tmp/gatepy"))
    g4data = Path(g4data_dir or os.environ.get("G4DATA_DIR", str(gatepy / "opengate_core" / "geant4_data")))
    base = {var: (g4data / folder).is_dir() for var, folder in G4_DATASET_VARS.items()}
    hp_ok = (g4data / G4_HP_DATASET[1]).is_dir()
    return {
        "datasets": base,
        "g4ndl_hp": hp_ok,
        "ftfp_bert_ok": all(base.values()),
        "hp_lists_ok": all(base.values()) and hp_ok,
    }
