"""
Casos de uso del QC Release (EDS Vol. II, cap. 25): catálogo
versionado de protocolos QC (25.6) y especificaciones oficiales
(25.10), Validation Engine (25.11) y Release Engine (25.12).
"""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from app.domain.qc_release import (QcInvalido, QcProtocol, ReleaseResult,
                                   Specification, evaluar_resultados,
                                   recomendar_liberacion)

DATA_DIR = Path(__file__).resolve().parents[1] / "data"


class ProtocoloQcNoEncontrado(KeyError):
    pass


class QcReleaseCatalog:
    """Protocolos QC + especificaciones versionadas (25.6/25.10)."""

    def __init__(self, path: Path | None = None) -> None:
        self._path = path or DATA_DIR / "qc_protocols.json"
        raw = json.loads(self._path.read_text(encoding="utf-8"))
        self._protocols = {p["id"]: QcProtocol(
            protocol_id=p["id"], radiopharmaceutical=p["radiopharmaceutical"],
            version=p["version"],
            ensayos_requeridos=tuple(p["ensayos_requeridos"]),
            criterios_aceptacion=p["criterios_aceptacion"],
            documentacion=p["documentacion"], validated=p["validated"],
            source=p["source"]) for p in raw["qc_protocols"]}
        # 25.10: cada especificación registra versión y vigencia;
        # los cambios generan nuevas versiones sin sobrescribir.
        self._specs: dict[str, list[Specification]] = {}
        for s in raw["specifications"]:
            spec = Specification(
                parametro=s["parametro"], limite_inferior=s["limite_inferior"],
                limite_superior=s["limite_superior"], unidades=s["unidades"],
                version=s["version"], vigencia_desde=s["vigencia_desde"])
            self._specs.setdefault(spec.parametro, []).append(spec)

    def protocol(self, protocol_id: str) -> QcProtocol:
        try:
            return self._protocols[protocol_id]
        except KeyError:
            raise ProtocoloQcNoEncontrado(
                f"protocolo QC no registrado: {protocol_id}")

    def specs_vigentes(self, fecha: date | None = None) -> dict[str, Specification]:
        """Última versión por vigencia para cada parámetro (25.10)."""
        vig: dict[str, Specification] = {}
        for parametro, versiones in self._specs.items():
            ordenadas = sorted(versiones, key=lambda s: (s.vigencia_desde, s.version))
            vig[parametro] = ordenadas[-1]
        return vig

    def list_protocols(self) -> list[QcProtocol]:
        return list(self._protocols.values())


class QcReleaseService:
    """Validation Engine + Release Engine (25.11/25.12)."""

    def __init__(self, catalog: QcReleaseCatalog | None = None) -> None:
        self._catalog = catalog or QcReleaseCatalog()

    @property
    def catalog(self) -> QcReleaseCatalog:
        return self._catalog

    def release(self, protocol_id: str, resultados: dict[str, float | None],
                operador: str = "sistema", motivo: str = "",
                lote: str = "", fecha: date | None = None) -> ReleaseResult:
        protocol = self._catalog.protocol(protocol_id)
        specs = self._catalog.specs_vigentes(fecha)
        for ensayo, valor in resultados.items():
            if ensayo not in specs and ensayo not in protocol.ensayos_requeridos:
                raise QcInvalido(
                    f"resultado para ensayo '{ensayo}' sin especificación ni "
                    "requerimiento en el protocolo (25.8/25.10)")
        evaluaciones = evaluar_resultados(protocol, specs, resultados, fecha)
        return recomendar_liberacion(protocol, evaluaciones,
                                     operador=operador, motivo=motivo, lote=lote)
