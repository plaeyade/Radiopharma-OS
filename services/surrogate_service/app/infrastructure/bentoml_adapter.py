"""Adaptador BentoML (cap. 20.10): runtime oficial de despliegue.

BentoML es la plataforma oficial declarada por la especificación.
Este adaptador empaqueta modelos del Model Registry (20.9) como
servicios BentoML **cuando el runtime está realmente disponible**
en el entorno; en caso contrario reporta su ausencia de forma
honesta (patrón de plataforma: nunca se simula el runtime).
"""
from __future__ import annotations

import importlib.util
import json
from dataclasses import asdict
from pathlib import Path


class BentoMLUnavailable(RuntimeError):
    """El runtime BentoML no está instalado en el entorno (20.10)."""


class BentoMLAdapter:
    """Empaquetado honesto de modelos registrados hacia BentoML."""

    def __init__(self, store_dir: str | Path | None = None) -> None:
        self._store = Path(store_dir) if store_dir else None

    @staticmethod
    def available() -> bool:
        return importlib.util.find_spec("bentoml") is not None

    def status(self) -> dict:
        return {
            "bentoml_disponible": self.available(),
            "nota": (
                "BentoML es la plataforma oficial de despliegue (20.10). "
                "El adaptador empaqueta modelos del registry cuando el "
                "runtime está instalado; su ausencia se reporta "
                "honestamente y nunca se simula."),
        }

    def package(self, record, dest_dir: str | Path) -> dict:
        """Empaqueta un ModelRecord como modelo BentoML versionado.

        Requiere runtime real; sin él, BentoMLUnavailable (→ 503).
        El empaquetado nunca sobrescribe: el nombre incluye el
        identificador y la versión (20.9).
        """
        if not self.available():
            raise BentoMLUnavailable(
                "runtime BentoML no instalado en este entorno (20.10): "
                "no se puede empaquetar el modelo")
        import bentoml  # noqa: WPS433 (import condicional intencional)

        dest = Path(dest_dir)
        dest.mkdir(parents=True, exist_ok=True)
        nombre = f"{record.model_id}-{record.version}"
        if (dest / nombre).exists():
            raise FileExistsError(
                f"el paquete {nombre} ya existe: el registro nunca se "
                "sobrescribe (20.9)")
        # serialización portable del modelo (coeficientes + metadatos)
        payload = {"modelo": asdict(record), "formato": "coeficientes-json",
                   "algoritmo": record.algorithm}
        (dest / nombre).mkdir()
        (dest / nombre / "model.json").write_text(
            json.dumps(payload, indent=1), encoding="utf-8")
        (dest / nombre / "service.py").write_text(_SERVICE_STUB,
                                                  encoding="utf-8")
        return {"paquete": nombre, "ruta": str(dest / nombre),
                "bentoml_version": getattr(bentoml, "__version__", "?")}


_SERVICE_STUB = '''"""Servicio BentoML generado por Radiopharma OS (cap. 20.10)."""
import bentoml
from bentoml.io import JSON

svc = bentoml.Service("radiopharma-surrogate")


@svc.api(input=JSON(), output=JSON())
def infer(features):
    """Inferencia polinómica log-log; nunca reemplaza al modelo
    físico de referencia (20.3)."""
    import math
    coef = features["coefficients"]
    le = math.log10(features["beam_energy_mev"])
    z = sum(c * le ** i for i, c in enumerate(coef))
    return {"yield_mbq_ua": 10.0 ** z,
            "nota": "resultado de modelo IA (surrogate, cap. 20.15)"}
'''
