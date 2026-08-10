"""
Synthesis Service — orquesta los motores químicos del Process Twin
(EDS Vol. II, caps. 22-24).

Flujo (22.4/22.17/23.17):
  Activity EOB (Physics Twin, 22.14)
      → Reaction Engine (cap. 22)
      → Purification Engine (cap. 23)
      → Formulation Engine (caps. 21.13/24)

Los protocolos se cargan de un catálogo JSON versionado (22.6,
23.6, 24.6). Toda la trazabilidad (operador, lote, motivo,
versiones) viaja en las auditorías de cada motor (22.24).
"""
from __future__ import annotations

import json
from dataclasses import asdict
from datetime import date
from pathlib import Path

from app.domain.formulation_engine import (Excipient, FormulationProtocol,
                                           FormulationResult,
                                           simular_formulacion)
from app.domain.purification_engine import (Cartridge, PurificationProtocol,
                                            PurificationResult,
                                            PurificationStep,
                                            simular_purificacion)
from app.domain.reaction_engine import (ProtocoloInvalido, simular_reaccion)
from app.domain.synthesis_entities import (KineticParams, ReactionProtocol,
                                           ReactionResult, ReactionStep,
                                           Reagent, ThermalProfile)

DATA_DIR = Path(__file__).resolve().parents[2] / "data"


class ProtocoloNoEncontrado(KeyError):
    pass


class SynthesisCatalog:
    """Catálogo versionado de protocolos químicos (22.6/23.6/24.6)."""

    def __init__(self, path: Path | None = None) -> None:
        self._path = path or DATA_DIR / "synthesis_protocols.json"
        raw = json.loads(self._path.read_text(encoding="utf-8"))
        self._reaction = {p["id"]: self._reaction(p) for p in raw["reaction_protocols"]}
        self._purification = {p["id"]: self._purification(p) for p in raw["purification_protocols"]}
        self._formulation = {p["id"]: self._formulation(p) for p in raw["formulation_protocols"]}

    @staticmethod
    def _reaction(d: dict) -> ReactionProtocol:
        return ReactionProtocol(
            protocol_id=d["id"], version=d["version"],
            radiopharmaceutical=d["radiopharmaceutical"],
            nuclide=d["nuclide"], half_life_min=d["half_life_min"],
            reagents=tuple(Reagent(**r) for r in d["reagents"]),
            steps=tuple(ReactionStep(**s) for s in d["steps"]),
            thermal=ThermalProfile(**d["thermal"]) if d.get("thermal") else None,
            kinetic=KineticParams(**d["kinetic"]) if d.get("kinetic") else None,
            validated=d["validated"], source=d["source"])

    @staticmethod
    def _purification(d: dict) -> PurificationProtocol:
        return PurificationProtocol(
            protocol_id=d["id"], version=d["version"],
            radiopharmaceutical=d["radiopharmaceutical"],
            half_life_min=d["half_life_min"],
            steps=tuple(PurificationStep(**s) for s in d["steps"]),
            cartridges=tuple(Cartridge(**c) for c in d["cartridges"]),
            validated=d["validated"], source=d["source"])

    @staticmethod
    def _formulation(d: dict) -> FormulationProtocol:
        return FormulationProtocol(
            protocol_id=d["id"], version=d["version"],
            radiopharmaceutical=d["radiopharmaceutical"],
            half_life_min=d["half_life_min"],
            duration_min=d["duration_min"],
            volumen_final_ml=d["volumen_final_ml"],
            concentracion_max_gbq_ml=d.get("concentracion_max_gbq_ml"),
            excipients=tuple(Excipient(**e) for e in d["excipients"]),
            validated=d["validated"], source=d["source"])

    def list_reaction(self) -> list[ReactionProtocol]:
        return list(self._reaction.values())

    def list_purification(self) -> list[PurificationProtocol]:
        return list(self._purification.values())

    def list_formulation(self) -> list[FormulationProtocol]:
        return list(self._formulation.values())

    def reaction(self, protocol_id: str) -> ReactionProtocol:
        try:
            return self._reaction[protocol_id]
        except KeyError:
            raise ProtocoloNoEncontrado(f"protocolo de reacción no registrado: {protocol_id}")

    def purification(self, protocol_id: str) -> PurificationProtocol:
        try:
            return self._purification[protocol_id]
        except KeyError:
            raise ProtocoloNoEncontrado(f"protocolo de purificación no registrado: {protocol_id}")

    def formulation(self, protocol_id: str) -> FormulationProtocol:
        try:
            return self._formulation[protocol_id]
        except KeyError:
            raise ProtocoloNoEncontrado(f"protocolo de formulación no registrado: {protocol_id}")


class SynthesisService:
    """Fachada de los tres motores químicos + cadena completa."""

    def __init__(self, catalog: SynthesisCatalog | None = None) -> None:
        self._catalog = catalog or SynthesisCatalog()

    @property
    def catalog(self) -> SynthesisCatalog:
        return self._catalog

    # -------------------------------------------------- Reaction (cap. 22)
    def reaction(self, protocol_id: str, eob_activity_gbq: float,
                 incertidumbre_inicial_rel: float = 0.0,
                 operador: str = "sistema", motivo: str = "",
                 lote: str = "", fecha_lote: date | None = None) -> ReactionResult:
        p = self._catalog.reaction(protocol_id)
        return simular_reaccion(p, eob_activity_gbq, incertidumbre_inicial_rel,
                                operador=operador, motivo=motivo, lote=lote,
                                fecha_lote=fecha_lote)

    # ----------------------------------------------- Purification (cap. 23)
    def purification(self, protocol_id: str, input_activity_gbq: float,
                     impurezas_iniciales: dict | None = None,
                     operador: str = "sistema", motivo: str = "",
                     lote: str = "") -> PurificationResult:
        p = self._catalog.purification(protocol_id)
        return simular_purificacion(p, input_activity_gbq, impurezas_iniciales,
                                    operador=operador, motivo=motivo, lote=lote)

    # ----------------------------------------------- Formulation (cap. 24)
    def formulation(self, protocol_id: str, input_activity_gbq: float,
                    input_volumen_ml: float,
                    operador: str = "sistema", motivo: str = "",
                    lote: str = "", fecha_lote: date | None = None) -> FormulationResult:
        p = self._catalog.formulation(protocol_id)
        return simular_formulacion(p, input_activity_gbq, input_volumen_ml,
                                   operador=operador, motivo=motivo, lote=lote,
                                   fecha_lote=fecha_lote)

    # ----------------------------------------- cadena EOB → producto final
    def synthesis_e2e(self, reaction_id: str, purification_id: str,
                      formulation_id: str, eob_activity_gbq: float,
                      incertidumbre_inicial_rel: float = 0.0,
                      volumen_crudo_ml: float = 3.0,
                      impurezas_iniciales: dict | None = None,
                      operador: str = "sistema", motivo: str = "",
                      lote: str = "", fecha_lote: date | None = None) -> dict:
        """Cadena completa RE → PU → FE (22.17/23.17).

        La compatibilidad de radiofármaco entre etapas se verifica
        antes de ejecutar (22.22, coherencia del proceso).
        """
        pr = self._catalog.reaction(reaction_id)
        pp = self._catalog.purification(purification_id)
        pf = self._catalog.formulation(formulation_id)
        if not (pr.radiopharmaceutical == pp.radiopharmaceutical == pf.radiopharmaceutical):
            raise ProtocoloInvalido(
                "compatibilidad del radiofármaco: los protocolos de las tres "
                "etapas deben corresponder al mismo producto (22.22)")
        if abs(pr.half_life_min - pp.half_life_min) > 1e-6 or \
                abs(pr.half_life_min - pf.half_life_min) > 1e-6:
            raise ProtocoloInvalido(
                "vidas medias incoherentes entre protocolos de la cadena (22.13)")

        r_reac = self.reaction(reaction_id, eob_activity_gbq,
                               incertidumbre_inicial_rel, operador=operador,
                               motivo=motivo, lote=lote, fecha_lote=fecha_lote)
        # 22.17: se transfiere actividad, composición, rendimiento y
        # productos secundarios (impurezas iniciales de la purificación)
        r_pur = self.purification(purification_id, r_reac.final_activity_gbq,
                                  impurezas_iniciales, operador=operador,
                                  motivo=motivo, lote=lote)
        # 23.17: actividad, composición, volumen, rendimiento, impurezas
        r_form = self.formulation(formulation_id, r_pur.final_activity_gbq,
                                  volumen_crudo_ml, operador=operador,
                                  motivo=motivo, lote=lote, fecha_lote=fecha_lote)

        return {
            "pipeline": "synthesis-e2e (Process Twin químico, caps. 22-24)",
            "radiopharmaceutical": pr.radiopharmaceutical,
            "nuclide": pr.nuclide,
            "eob_activity_gbq": eob_activity_gbq,
            "final_activity_gbq": r_form.final_activity_gbq,
            "volumen_final_ml": r_form.volumen_final_ml,
            "concentracion_final_gbq_ml": r_form.concentracion_final_gbq_ml,
            "eficiencia_cadena": (r_form.final_activity_gbq / eob_activity_gbq
                                  if eob_activity_gbq else 0.0),
            "tiempo_total_min": (r_reac.total_time_min + r_pur.total_time_min
                                 + r_form.duration_min),
            "incertidumbre_final_gbq": (r_form.final_activity_gbq
                                        * incertidumbre_inicial_rel),
            "validated": pr.validated and pp.validated and pf.validated,
            "reaction": asdict(r_reac),
            "purification": asdict(r_pur),
            "formulation": asdict(r_form),
        }
