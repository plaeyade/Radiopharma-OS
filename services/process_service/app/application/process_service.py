"""
Servicio de aplicación del Process Twin.

Carga el catálogo de protocolos (data/protocols.json) y ejecuta
simulaciones de cadena EOB -> EOS. Los protocolos marcados
validated=false son parametrizaciones de referencia pendientes de
validación con datos reales de planta (honestidad de datos).
"""
from __future__ import annotations

import json
from pathlib import Path

from app.domain.entities import ChainResult, Protocol, ProtocolStep
from app.domain.process_chain import simulate_chain

_DEFAULT_DATA = Path(__file__).resolve().parents[2] / "data" / "protocols.json"


class ProtocolCatalog:
    """Catálogo de protocolos de proceso cargado desde JSON."""

    def __init__(self, path: Path | None = None) -> None:
        self._path = path or _DEFAULT_DATA
        self._protocols = self._load(self._path)

    @staticmethod
    def _load(path: Path) -> dict[str, Protocol]:
        raw = json.loads(path.read_text(encoding="utf-8"))
        protocols: dict[str, Protocol] = {}
        for p in raw.get("protocols", []):
            steps = tuple(ProtocolStep(
                name=s["name"],
                duration_min=float(s["duration_min"]),
                efficiency=float(s["efficiency"])) for s in p["steps"])
            proto = Protocol(
                protocol_id=p["id"],
                name=p["name"],
                nuclide=p["nuclide"],
                half_life_min=float(p["half_life_min"]),
                dose_per_patient_gbq=float(p["dose_per_patient_gbq"]),
                validated=bool(p.get("validated", False)),
                source=p.get("source", ""),
                steps=steps)
            protocols[proto.protocol_id] = proto
        if not protocols:
            raise ValueError(f"catálogo vacío en {path}")
        return protocols

    def list(self) -> list[Protocol]:
        return list(self._protocols.values())

    def get(self, protocol_id: str) -> Protocol:
        proto = self._protocols.get(protocol_id)
        if proto is None:
            raise KeyError(protocol_id)
        return proto


class ProcessService:
    """Casos de uso del Process Twin."""

    def __init__(self, catalog: ProtocolCatalog | None = None) -> None:
        self._catalog = catalog or ProtocolCatalog()

    @property
    def catalog(self) -> ProtocolCatalog:
        return self._catalog

    def list_protocols(self) -> list[Protocol]:
        return self._catalog.list()

    def get_protocol(self, protocol_id: str) -> Protocol:
        return self._catalog.get(protocol_id)

    def simulate(self, protocol_id: str,
                 eob_activity_gbq: float) -> ChainResult:
        proto = self._catalog.get(protocol_id)
        return simulate_chain(proto, eob_activity_gbq)
