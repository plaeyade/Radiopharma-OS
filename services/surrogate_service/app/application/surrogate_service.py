"""
Surrogate Service (EDS Vol. II, cap. 20).

Flujo 20.4: dataset versionado (20.6) → entrenamiento fuera del
servidor de inferencia (20.8, aquí como pipeline documentado y
reproducible) → puerta de validación (20.21) → Model Registry
(20.9) → Inference API (20.11) con auditoría por inferencia
(20.24) y Drift Monitor (20.20).

El modelo físico completo permanece disponible en paralelo
(20.3): las respuestas se identifican siempre como resultado de
un modelo IA (20.15).
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from app.domain.surrogate import (DriftMonitor, ModelRecord, ModelRegistry,
                                  TrainingDataset, ahora_iso,
                                  log10_features, validar_surrogate)

DATA_DIR = Path(__file__).resolve().parents[1] / "data"


class SurrogateNoEncontrado(KeyError):
    pass


class SurrogateService:
    def __init__(self, data_dir: Path | None = None) -> None:
        self._dir = data_dir or DATA_DIR
        self._registry = ModelRegistry()
        self._drift = DriftMonitor()
        self._audit: list[dict] = []
        self._datasets: dict[tuple[str, str], TrainingDataset] = {}

    # --------------------------------------------------- datasets (20.6)
    def load_dataset(self, filename: str = "yield_saturation_dataset.json"
                     ) -> TrainingDataset:
        raw = json.loads((self._dir / filename).read_text(encoding="utf-8"))
        energies = np.asarray(raw["energies_mev"], dtype=float)
        x, doc = log10_features(energies)  # 20.7: transformación documentada
        ds = TrainingDataset(
            dataset_id=raw["dataset_id"], version=raw["version"],
            source=raw["source"],
            feature_names=tuple(raw["feature_names"]),
            transform_doc=doc,
            features=tuple(tuple(float(v) for v in row) for row in x),
            target=tuple(float(v) for v in raw["yield_sat_mbq_ua"]))
        self._datasets[(ds.dataset_id, ds.version)] = ds
        return ds

    def list_datasets(self) -> list[dict]:
        return [{"dataset_id": d.dataset_id, "version": d.version,
                 "n_points": d.n_points, "source": d.source,
                 "hash": d.content_hash, "transform": d.transform_doc}
                for d in self._datasets.values()]

    # ------------------------------------------------- entrenamiento (20.8)
    def train_yield_surrogate(self, version: str, responsable: str,
                              umbral_rel_rmse: float = 0.05,
                              umbral_max_rel_err: float = 0.15) -> dict:
        """Entrena el surrogate de rendimiento físico (20.12).

        Solo se registra si la puerta de validación aprueba (20.21);
        el registro es permanente y no sobrescribe (20.9).
        """
        ds = self._datasets.get(("yield_sat_f18_h2o18", "1.0.0")) \
            or self.load_dataset()
        model, report = validar_surrogate(ds, umbral_rel_rmse,
                                          umbral_max_rel_err)
        resultado = {
            "dataset_id": ds.dataset_id, "dataset_version": ds.version,
            "dataset_hash": ds.content_hash,
            "validation": {
                "holdout_size": report.holdout_size,
                "train_size": report.train_size,
                "rel_rmse": report.rel_rmse,
                "max_rel_err": report.max_rel_err,
                "umbral_rel_rmse": report.umbral_rel_rmse,
                "umbral_max_rel_err": report.umbral_max_rel_err,
                "approved": report.approved,
                "motivos": list(report.motivos),
            },
            "registrado": False,
        }
        if not report.approved or model is None:
            return resultado  # 20.21: no se publica lo que no cumple
        record = ModelRecord(
            model_id="yield_sat_f18", version=version,
            algorithm=model.algorithm, fecha=ahora_iso(),
            dataset_id=ds.dataset_id, dataset_version=ds.version,
            dataset_hash=ds.content_hash,
            metricas_validacion=resultado["validation"],
            responsable=responsable, modelo=model,
            descripcion="Rendimiento a saturación 18O(p,n)18F en H2-18O "
                        "(surrogate del Yield Engine; el modelo físico "
                        "completo permanece disponible, 20.3)")
        self._registry.register(record)
        resultado["registrado"] = True
        resultado["model_id"] = record.model_id
        resultado["version"] = record.version
        resultado["algorithm"] = record.algorithm
        return resultado

    # --------------------------------------------------- inferencia (20.11)
    def infer(self, model_id: str, version: str | None,
              beam_energy_mev: float, usuario: str,
              request_id: str | None = None) -> dict:
        """Inferencia con auditoría completa (20.24).

        La respuesta se identifica como resultado de un modelo IA
        (20.15) e incluye indicador de confianza (20.22) derivado
        del holdout de validación.
        """
        try:
            rec = self._registry.get(model_id, version)
        except KeyError as exc:
            raise SurrogateNoEncontrado(str(exc))
        if not (2.5 <= beam_energy_mev <= 18.0):
            raise ValueError(
                "energía fuera del dominio de entrenamiento [4, 18] MeV "
                "con margen de umbral (20.21: no se extrapola)")
        le = math_log10(beam_energy_mev)
        x = np.array([1.0, le, le ** 2, le ** 3, le ** 4, le ** 5])
        pred = rec.modelo.predict(x)
        audit = {
            "request_id": request_id or f"inf-{len(self._audit)+1:06d}",
            "fecha": ahora_iso(),
            "usuario": usuario,
            "model_id": rec.model_id,
            "version": rec.version,
            "parametros": {"beam_energy_mev": beam_energy_mev},
        }
        self._audit.append(audit)
        return {
            "tipo": "resultado de modelo IA (surrogate, cap. 20.15) — el "
                    "modelo físico completo permanece disponible (20.3)",
            "model_id": rec.model_id,
            "version": rec.version,
            "prediccion_yield_sat_mbq_ua": pred,
            "confianza_rel_holdout": rec.modelo.validation_rel_rmse,  # 20.22
            "max_rel_err_holdout": rec.modelo.validation_max_rel_err,
            "metadatos": {
                "algorithm": rec.algorithm,
                "dataset_id": rec.dataset_id,
                "dataset_version": rec.dataset_version,
                "responsable": rec.responsable,
                "reaction": "18O(p,n)18F",
                "target": "H2-18O 97%",
            },
            "auditoria": audit,
        }

    # -------------------------------------------------------- drift (20.20)
    def drift_observe(self, model_id: str, version: str | None,
                      prediccion: float, medicion: float,
                      fuente: str) -> dict:
        rec = self._registry.get(model_id, version)
        return self._drift.observar(rec.model_id, rec.version, prediccion,
                                    medicion, fuente, ahora_iso())

    def drift_status(self, model_id: str | None = None) -> dict:
        return self._drift.estado(model_id)

    # ------------------------------------------------------- consulta meta
    def list_models(self) -> list[dict]:
        return [{"model_id": r.model_id, "version": r.version,
                 "algorithm": r.algorithm, "fecha": r.fecha,
                 "dataset_id": r.dataset_id,
                 "dataset_version": r.dataset_version,
                 "metricas_validacion": r.metricas_validacion,
                 "responsable": r.responsable,
                 "descripcion": r.descripcion}
                for r in self._registry.list()]

    def audit_log(self) -> list[dict]:
        return list(self._audit)

    # ------------------------------------------------ BentoML (20.10)
    def bentoml_status(self) -> dict:
        """Estado honesto del runtime BentoML (plataforma oficial)."""
        from app.infrastructure.bentoml_adapter import BentoMLAdapter
        return BentoMLAdapter().status()

    def bentoml_package(self, model_id: str, version: str | None,
                        dest_dir: str) -> dict:
        """Empaqueta un modelo del registry como servicio BentoML.

        Requiere runtime real; sin él, BentoMLUnavailable (→ 503).
        """
        from app.infrastructure.bentoml_adapter import BentoMLAdapter
        try:
            rec = self._registry.get(model_id, version)
        except KeyError as exc:
            raise SurrogateNoEncontrado(str(exc))
        return BentoMLAdapter().package(rec, dest_dir)


def math_log10(x: float) -> float:
    import math
    return math.log10(x)
