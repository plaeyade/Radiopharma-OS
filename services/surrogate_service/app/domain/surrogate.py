"""
Surrogate Modeling Server — núcleo (EDS Vol. II, cap. 20).

Los modelos sustitutos NUNCA reemplazan al modelo físico de
referencia (20.3): siempre coexisten la simulación completa y la
inferencia rápida. Los surrogates se entrenan fuera del servidor de
inferencia con resultados de alta fidelidad (20.8) y solo se
despliegan modelos previamente validados (20.8/20.21).

Componentes implementados: Dataset Manager (20.6, datasets
versionados con hash), Feature Engineering Engine (20.7,
transformaciones documentadas), Model Registry (20.9, ningún
modelo se sobrescribe), Validation Engine (20.21, puerta previa al
despliegue), Drift Monitor (20.20) y gestión de incertidumbre
(20.22, indicador de confianza del holdout).
"""
from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass, field
from datetime import datetime, timezone

import numpy as np


# ------------------------------------------------------------ dataset (20.6)
@dataclass(frozen=True)
class TrainingDataset:
    """Dataset de entrenamiento versionado (20.6).

    features: matriz (n, d) ya transformada por el Feature
    Engineering Engine (20.7); transform_doc documenta la
    transformación aplicada. El hash garantiza el versionado
    permanente (20.23).
    """
    dataset_id: str
    version: str
    source: str
    feature_names: tuple[str, ...]
    transform_doc: str
    features: tuple[tuple[float, ...], ...]
    target: tuple[float, ...]

    @property
    def n_points(self) -> int:
        return len(self.target)

    @property
    def content_hash(self) -> str:
        h = hashlib.sha256()
        h.update(json.dumps({
            "id": self.dataset_id, "version": self.version,
            "features": self.features, "target": self.target,
        }, sort_keys=True).encode())
        return h.hexdigest()


# ------------------------------------------------- feature engineering (20.7)
def log10_features(energies: np.ndarray) -> tuple[np.ndarray, str]:
    """Transformación documentada: X = [1, log10(E), log10(E)^2, log10(E)^3].

    El rendimiento a saturación Y(E) crece suavemente con la energía
    del haz; en espacio log10 la curva es cuasi-polínomica de bajo
    grado, lo que permite un surrogate ridge estable.
    """
    le = np.log10(np.asarray(energies, dtype=float))
    x = np.column_stack([np.ones_like(le), le, le ** 2, le ** 3,
                         le ** 4, le ** 5])
    return x, ("X=[1, log10(E), ..., log10(E)^5]; y=log10(Y_sat)")


# ------------------------------------------------------------ modelo (20.8)
@dataclass(frozen=True)
class PolynomialSurrogate:
    """Surrogate polinómico ridge en espacio transformado.

    Algoritmo: mínimos cuadrados regularizados (ridge) sobre las
    características del dataset; la predicción se devuelve en
    unidades físicas junto con un indicador de confianza (20.22)
    derivado del error holdout de validación.
    """
    algorithm: str
    degree: int
    coefficients: tuple[float, ...]
    target_transform: str  # 'log10'
    validation_rel_rmse: float
    validation_max_rel_err: float
    holdout_size: int
    train_size: int

    def predict(self, x_row: np.ndarray) -> float:
        z = float(np.dot(np.asarray(x_row, dtype=float),
                         np.asarray(self.coefficients)))
        return float(10.0 ** z) if self.target_transform == "log10" else z


def fit_ridge(x: np.ndarray, y: np.ndarray, lam: float = 1e-6) -> np.ndarray:
    a = x.T @ x + lam * np.eye(x.shape[1])
    return np.linalg.solve(a, x.T @ y)


# ------------------------------------------------------ validación (20.21)
@dataclass(frozen=True)
class ValidationReport:
    """Puerta previa al despliegue (20.21).

    Holdout determinístico: cada 4º punto queda fuera del
    entrenamiento. El modelo solo se publica si rel_rmse y
    max_rel_err quedan por debajo de los umbrales declarados.
    """
    holdout_size: int
    train_size: int
    rel_rmse: float
    max_rel_err: float
    umbral_rel_rmse: float
    umbral_max_rel_err: float
    approved: bool
    motivos: tuple[str, ...]


def validar_surrogate(dataset: TrainingDataset,
                      umbral_rel_rmse: float = 0.05,
                      umbral_max_rel_err: float = 0.15,
                      min_points: int = 12) -> tuple[PolynomialSurrogate | None,
                                                     ValidationReport]:
    """Entrena y valida; devuelve el modelo SOLO si aprueba (20.21)."""
    motivos: list[str] = []
    if dataset.n_points < min_points:
        motivos.append(
            f"calidad del dataset: {dataset.n_points} puntos < mínimo "
            f"{min_points} (20.21)")
    x = np.asarray(dataset.features, dtype=float)
    y = np.log10(np.maximum(np.asarray(dataset.target, dtype=float), 1e-30))

    idx_hold = np.arange(3, dataset.n_points, 4)
    idx_train = np.setdiff1d(np.arange(dataset.n_points), idx_hold)
    if len(idx_hold) < 2 or len(idx_train) < x.shape[1] + 1:
        motivos.append("holdout no representativo para validar (20.21)")
        report = ValidationReport(len(idx_hold), len(idx_train),
                                  float("nan"), float("nan"),
                                  umbral_rel_rmse, umbral_max_rel_err,
                                  False, tuple(motivos))
        return None, report

    coef = fit_ridge(x[idx_train], y[idx_train])
    pred_hold = x[idx_hold] @ coef
    err = 10.0 ** pred_hold / 10.0 ** y[idx_hold] - 1.0
    rel_rmse = float(np.sqrt(np.mean(err ** 2)))
    max_rel = float(np.max(np.abs(err)))

    if rel_rmse > umbral_rel_rmse:
        motivos.append(
            f"desempeño del modelo: rel_rmse {rel_rmse:.4f} > umbral "
            f"{umbral_rel_rmse} (20.21)")
    if max_rel > umbral_max_rel_err:
        motivos.append(
            f"desempeño del modelo: max_rel_err {max_rel:.4f} > umbral "
            f"{umbral_max_rel_err} (20.21)")
    approved = not motivos
    report = ValidationReport(len(idx_hold), len(idx_train), rel_rmse,
                              max_rel, umbral_rel_rmse, umbral_max_rel_err,
                              approved, tuple(motivos))
    if not approved:
        return None, report

    # modelo final: reajuste con TODOS los puntos validados
    coef_full = fit_ridge(x, y)
    model = PolynomialSurrogate(
        algorithm="ridge-polinomico-loglog",
        degree=x.shape[1] - 1,
        coefficients=tuple(float(c) for c in coef_full),
        target_transform="log10",
        validation_rel_rmse=rel_rmse,
        validation_max_rel_err=max_rel,
        holdout_size=len(idx_hold), train_size=len(idx_train))
    return model, report


# ------------------------------------------------------------ registry (20.9)
@dataclass(frozen=True)
class ModelRecord:
    """Entrada del Model Registry (20.9). Ningún modelo se sobrescribe."""
    model_id: str
    version: str
    algorithm: str
    fecha: str
    dataset_id: str
    dataset_version: str
    dataset_hash: str
    metricas_validacion: dict
    responsable: str
    modelo: PolynomialSurrogate
    descripcion: str = ""


class ModelRegistry:
    def __init__(self) -> None:
        self._records: dict[tuple[str, str], ModelRecord] = {}

    def register(self, record: ModelRecord) -> ModelRecord:
        key = (record.model_id, record.version)
        if key in self._records:
            raise ValueError(
                f"el modelo {record.model_id}:{record.version} ya existe; "
                "ningún modelo se sobrescribe (20.9)")
        self._records[key] = record
        return record

    def get(self, model_id: str, version: str | None = None) -> ModelRecord:
        if version is None:
            candidatos = [r for (mid, _), r in self._records.items()
                          if mid == model_id]
            if not candidatos:
                raise KeyError(f"modelo no registrado: {model_id}")
            return sorted(candidatos, key=lambda r: r.version)[-1]
        try:
            return self._records[(model_id, version)]
        except KeyError:
            raise KeyError(f"modelo no registrado: {model_id}:{version}")

    def list(self) -> list[ModelRecord]:
        return sorted(self._records.values(),
                      key=lambda r: (r.model_id, r.version))


# --------------------------------------------------------- drift (20.20)
@dataclass
class DriftMonitor:
    """Supervisa predicción vs medición operativa validada (20.20)."""
    umbral_rel_rmse: float = 0.075
    observaciones: list[dict] = field(default_factory=list)

    def observar(self, model_id: str, version: str, prediccion: float,
                 medicion: float, fuente: str, fecha: str) -> dict:
        if medicion <= 0 or prediccion < 0:
            raise ValueError("medición y predicción deben ser positivas (20.20)")
        obs = {"model_id": model_id, "version": version,
               "prediccion": prediccion, "medicion": medicion,
               "error_rel": prediccion / medicion - 1.0,
               "fuente": fuente, "fecha": fecha}
        self.observaciones.append(obs)
        return obs

    def estado(self, model_id: str | None = None) -> dict:
        obs = [o for o in self.observaciones
               if model_id is None or o["model_id"] == model_id]
        if not obs:
            return {"n": 0, "reentrenamiento_recomendado": False,
                    "nota": "sin observaciones operativas (20.20)"}
        err = np.array([o["error_rel"] for o in obs])
        rmse = float(np.sqrt(np.mean(err ** 2)))
        sesgo = float(np.mean(err))
        retrain = rmse > self.umbral_rel_rmse or abs(sesgo) > self.umbral_rel_rmse
        return {"n": len(obs), "rel_rmse": rmse, "sesgo_rel": sesgo,
                "umbral": self.umbral_rel_rmse,
                "estabilidad_temporal": "estable" if not retrain else "deriva",
                "reentrenamiento_recomendado": bool(retrain)}


def ahora_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
