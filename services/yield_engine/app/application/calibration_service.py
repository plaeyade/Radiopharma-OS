"""
Calibration Layer: catálogo de equipos (multivendor) y almacén versionado
de modelos de calibración (reacción, equipo) → factor C con trazabilidad.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

from app.application.production_service import REACTIONS
from app.domain.calibration import FitResult, Measurement, fit_factor


@dataclass(frozen=True)
class Equipment:
    id: str
    fabricante: str
    modelo: str
    energia_max_mev: float | None
    energia_fija_mev: bool
    corriente_max_ua: float | None
    reacciones_tipicas: tuple[str, ...]
    notas: str


@dataclass(frozen=True)
class CalibrationModel:
    model_id: str
    reaction_id: str
    equipment_id: str
    version: int
    factor: float
    factor_uncertainty: float
    n_points: int
    chi2_ndf: float
    status: str
    fitted_at: str
    medidas: tuple[dict, ...]


class EquipmentCatalog:
    """Catálogo de ciclotrones multivendor (data/equipment.json)."""

    def __init__(self, path: Path) -> None:
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
        self._equipos = {
            e["id"]: Equipment(
                id=e["id"], fabricante=e["fabricante"], modelo=e["modelo"],
                energia_max_mev=e.get("energia_max_mev"),
                energia_fija_mev=bool(e.get("energia_fija_mev", False)),
                corriente_max_ua=e.get("corriente_max_ua"),
                reacciones_tipicas=tuple(e.get("reacciones_tipicas", ())),
                notas=e.get("notas", ""))
            for e in raw["cyclotrons"]
        }

    def list(self) -> list[Equipment]:
        return list(self._equipos.values())

    def get(self, equipment_id: str) -> Equipment:
        try:
            return self._equipos[equipment_id]
        except KeyError:
            raise ValueError(f"Equipo no registrado en el catálogo: {equipment_id}")


class CalibrationService:
    """Ajusta, almacena y aplica modelos de calibración versionados."""

    def __init__(self, store_path: Path, catalog: EquipmentCatalog) -> None:
        self._store = Path(store_path)
        self._catalog = catalog
        self._models: list[dict] = []
        if self._store.exists():
            self._models = json.loads(self._store.read_text(encoding="utf-8"))["models"]

    # -- persistencia -------------------------------------------------------
    def _save(self) -> None:
        self._store.parent.mkdir(parents=True, exist_ok=True)
        tmp = self._store.with_suffix(".tmp")
        tmp.write_text(json.dumps({"models": self._models}, indent=2),
                       encoding="utf-8")
        tmp.replace(self._store)

    # -- operaciones ---------------------------------------------------------
    def fit_and_store(self, reaction_id: str, equipment_id: str,
                      medidas: list[Measurement]) -> CalibrationModel:
        if reaction_id not in REACTIONS:
            raise ValueError(f"Reacción desconocida: {reaction_id}")
        equipo = self._catalog.get(equipment_id)
        fit: FitResult = fit_factor(medidas)
        version = 1 + sum(1 for m in self._models
                          if m["reaction_id"] == reaction_id
                          and m["equipment_id"] == equipment_id)
        model = CalibrationModel(
            model_id=f"CAL-{reaction_id}-{equipment_id}-v{version}",
            reaction_id=reaction_id, equipment_id=equipo.id,
            version=version, factor=fit.factor,
            factor_uncertainty=fit.factor_uncertainty, n_points=fit.n_points,
            chi2_ndf=fit.chi2_ndf, status=fit.status,
            fitted_at=datetime.now(timezone.utc).isoformat(),
            medidas=tuple(asdict(m) for m in medidas))
        self._models.append(asdict(model))
        self._save()
        return model

    def get_active(self, reaction_id: str, equipment_id: str) -> dict | None:
        """Última versión del modelo para (reacción, equipo), o None."""
        candidatos = [m for m in self._models
                      if m["reaction_id"] == reaction_id
                      and m["equipment_id"] == equipment_id]
        if not candidatos:
            return None
        return max(candidatos, key=lambda m: m["version"])

    def history(self, reaction_id: str | None = None,
                equipment_id: str | None = None) -> list[dict]:
        return [m for m in self._models
                if (reaction_id is None or m["reaction_id"] == reaction_id)
                and (equipment_id is None or m["equipment_id"] == equipment_id)]

    def apply(self, production: dict, reaction_id: str,
              equipment_id: str) -> dict:
        """Aplica el factor vigente a un resultado de producción del Physics
        Twin. Si no hay modelo, devuelve el resultado sin modificar con
        calibrated=False (trazabilidad explícita)."""
        model = self.get_active(reaction_id, equipment_id)
        out = dict(production)
        if model is None:
            out["calibration"] = {
                "calibrated": False, "equipment_id": equipment_id,
                "note": "Sin modelo de calibración vigente para esta "
                        "(reacción, equipo): se reporta la predicción física pura."}
            return out
        c = model["factor"]
        uc = model["factor_uncertainty"]
        out["eob_activity_gbq"] = round(production["eob_activity_gbq"] * c, 3)
        out["saturation_yield_mbq_ua"] = round(
            production["saturation_yield_mbq_ua"] * c, 1)
        if "saturation_yield_gbq_ua" in production:
            out["saturation_yield_gbq_ua"] = round(
                out["saturation_yield_mbq_ua"] / 1000.0, 3)
        if "eob_activity_gbq_uncertainty" in production:
            out["eob_activity_gbq_uncertainty"] = round(
                production["eob_activity_gbq_uncertainty"] * c, 3)
        if "yield_gbq_ua" in production:
            out["yield_gbq_ua"] = round(production["yield_gbq_ua"] * c, 4)
        out["calibration"] = {
            "calibrated": True, "equipment_id": equipment_id,
            "model_id": model["model_id"], "version": model["version"],
            "factor": c, "factor_uncertainty": uc,
            "status": model["status"], "fitted_at": model["fitted_at"],
            "eob_fisico_sin_calibrar_gbq": production["eob_activity_gbq"]}
        return out
