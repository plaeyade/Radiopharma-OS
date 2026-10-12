# -*- coding: utf-8 -*-
"""Surrogate del tally del búnker — Fase 48.

Modelo didáctico (declarado, NO validado para producción) que predice el
tally HP a partir del tally BERT del MISMO caso, usando solo tallies
reales de F35/F37. Regresión lineal en espacio log sobre voxels activos
comunes con dos características locales: log φ_BERT del voxel y media de
log φ_BERT en la ventana 3×3×3 (captura la redistribución térmica de HP,
F44). Validación: holdout ESPACIAL (mitad inferior de la malla para
entrenar, mitad superior para predecir) — nunca se mezclan voxel-vecinos
de train/test sin declararlo: la correlación espacial infla la métrica y
se declara como limitación.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

VENTANA = 1  # voxels por lado (ventana 3³)


def _media_local_log(phi: np.ndarray) -> np.ndarray:
    """Media de log10 φ en ventana 3³ (padding reflectante)."""
    log = np.log10(np.maximum(phi, 1e-30))
    pad = np.pad(log, VENTANA, mode="symmetric")
    acc = np.zeros_like(phi)
    for dx in range(2 * VENTANA + 1):
        for dy in range(2 * VENTANA + 1):
            for dz in range(2 * VENTANA + 1):
                acc += pad[dx:dx + phi.shape[0], dy:dy + phi.shape[1],
                           dz:dz + phi.shape[2]]
    return acc / (2 * VENTANA + 1) ** 3


@dataclass
class SurrogateTally:
    """φ̂_HP = 10^(b0 + b1·log10 φ_B + b2·media_local log10 φ_B)."""
    coef: np.ndarray
    n_train: int

    def predecir(self, phi_bert: np.ndarray) -> np.ndarray:
        lb = np.log10(np.maximum(phi_bert, 1e-30))
        X = np.stack([np.ones_like(lb), lb, _media_local_log(phi_bert)], axis=-1)
        return 10.0 ** (X @ self.coef)


def entrenar(phi_bert: np.ndarray, phi_hp: np.ndarray,
             mascara_train: np.ndarray | None = None) -> SurrogateTally | dict:
    """Ajuste por mínimos cuadrados en log sobre voxels activos en AMBOS."""
    if phi_bert.shape != phi_hp.shape:
        return {"estado": "no_demostrable",
                "motivo": f"formas {phi_bert.shape} vs {phi_hp.shape}"}
    comun = (phi_bert > 0) & (phi_hp > 0)
    if mascara_train is not None:
        if mascara_train.shape != phi_bert.shape:
            return {"estado": "no_demostrable", "motivo": "máscara de otra forma"}
        comun &= mascara_train
    if comun.sum() < 10:
        return {"estado": "no_demostrable",
                "motivo": f"solo {int(comun.sum())} voxels comunes"}
    lb = np.log10(phi_bert[comun])
    ly = np.log10(phi_hp[comun])
    ml = _media_local_log(phi_bert)[comun]
    X = np.column_stack([np.ones(comun.sum()), lb, ml])
    coef, *_ = np.linalg.lstsq(X, ly, rcond=None)
    return SurrogateTally(coef=coef, n_train=int(comun.sum()))


def validar_holdout_espacial(phi_bert: np.ndarray,
                             phi_hp: np.ndarray) -> dict:
    """Entrena en z < mitad, predice z ≥ mitad; métricas honestas."""
    z_half = phi_bert.shape[2] // 2
    train = np.zeros(phi_bert.shape, dtype=bool)
    train[:, :, :z_half] = True
    s = entrenar(phi_bert, phi_hp, mascara_train=train)
    if isinstance(s, dict):
        return s
    comun_test = (phi_bert > 0) & (phi_hp > 0) & ~train
    if comun_test.sum() < 10:
        return {"estado": "no_demostrable",
                "motivo": "voxels de test insuficientes"}
    pred = s.predecir(phi_bert)
    y, yh = phi_hp[comun_test], pred[comun_test]
    ss_res = float(np.sum((np.log10(y) - np.log10(yh)) ** 2))
    ss_tot = float(np.sum((np.log10(y) - np.log10(y).mean()) ** 2))
    dif = np.abs(yh - y) / ((yh + y) / 2)
    return {
        "estado": "completado",
        "n_train": s.n_train,
        "n_test": int(comun_test.sum()),
        "coef": [float(c) for c in s.coef],
        "r2_log_test": 1.0 - ss_res / ss_tot if ss_tot > 0 else None,
        "dif_simetrica_mediana_test": float(np.median(dif)),
        "limitacion_declarada": (
            "Holdout espacial: los voxels de test tienen vecinos en train "
            "(correlación espacial) — la métrica es OPTIMISTA y se declara "
            "así. Surrogate didáctico; no sustituye al MC ni valida "
            "producción. El gap irreducible es la física térmica (F44): "
            "HP activa voxels donde BERT tiene 0 counts — impredecibles "
            "desde BERT y excluidos de la métrica por construcción."),
    }
