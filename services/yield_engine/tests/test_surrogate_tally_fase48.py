"""Tests F48 — surrogate de tally (didáctico, validación espacial honesta)."""
import json

import numpy as np
import pytest

from app.domain.surrogate_tally import (
    SurrogateTally,
    entrenar,
    validar_holdout_espacial,
)

DIMS = (40, 40, 20)


def _mapa(semilla):
    rng = np.random.default_rng(semilla)
    base = np.zeros(DIMS)
    base[10:30, 10:30, 5:15] = rng.random((20, 20, 10)) * 100 + 1
    return base


def test_reproduccion_perfecta_cuando_y_es_x():
    phi = _mapa(1)
    s = entrenar(phi, phi)
    assert isinstance(s, SurrogateTally)
    pred = s.predecir(phi)
    comun = phi > 0
    np.testing.assert_allclose(pred[comun], phi[comun], rtol=1e-6)


def test_formas_incompatibles_no_demostrable():
    r = entrenar(np.zeros((5, 5, 5)), np.zeros(DIMS))
    assert r["estado"] == "no_demostrable"


def test_pocos_voxels_no_demostrable():
    a = np.zeros(DIMS); a[0, 0, 0] = 1.0
    r = entrenar(a, a)
    assert r["estado"] == "no_demostrable"


def test_holdout_espacial_reporta_metricas():
    pb = _mapa(2)
    ph = pb * 2.0  # HP = 2× BERT (caso F44 idealizado)
    r = validar_holdout_espacial(pb, ph)
    assert r["estado"] == "completado"
    assert r["n_test"] > 0 and r["n_train"] > 0
    # y = 2x es exacto en log → R² ≈ 1
    assert r["r2_log_test"] == pytest.approx(1.0, abs=1e-6)
    assert "OPTIMISTA" in r["limitacion_declarada"]


def test_serializable_alcoa():
    pb, ph = _mapa(3), _mapa(3) * 1.5
    r = validar_holdout_espacial(pb, ph)
    json.dumps(r, ensure_ascii=False)
