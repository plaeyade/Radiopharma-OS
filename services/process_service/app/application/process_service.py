"""
Servicio de aplicación del Process Twin.

Carga el catálogo de protocolos (data/protocols.json) y ejecuta
simulaciones de cadena EOB -> EOS. Los protocolos marcados
validated=false son parametrizaciones de referencia pendientes de
validación con datos reales de planta (honestidad de datos).
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from app.domain.bottleneck import BottleneckResult, bottleneck_analysis
from app.domain.entities import ChainResult, Protocol, ProtocolStep
from app.domain.process_chain import simulate_chain
from app.domain.scheduling import ScheduleResult, backward_schedule

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

    def schedule(self, protocol_id: str,
                 dose_time: datetime,
                 irradiation_time_min: float,
                 setup_min: float = 0.0,
                 eos_target_gbq: float | None = None,
                 target_doses: int | None = None) -> ScheduleResult:
        """Planificación inversa desde la hora de dosis.

        Objetivo clínico: eos_target_gbq directo o target_doses (que se
        convierte con la dosis por paciente del protocolo).
        """
        proto = self._catalog.get(protocol_id)
        if eos_target_gbq is None:
            if target_doses is None or target_doses <= 0:
                raise ValueError(
                    "indique eos_target_gbq o target_doses (> 0)")
            eos_target_gbq = target_doses * proto.dose_per_patient_gbq
        return backward_schedule(proto, eos_target_gbq, dose_time,
                                 irradiation_time_min, setup_min)

    def bottleneck(self, protocol_id: str,
                   eob_activity_gbq: float) -> BottleneckResult:
        proto = self._catalog.get(protocol_id)
        return bottleneck_analysis(proto, eob_activity_gbq)
