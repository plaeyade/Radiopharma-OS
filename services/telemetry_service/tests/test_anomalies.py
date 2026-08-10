"""Pruebas de la detección de anomalías (EDS 6.22/6.23)."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.application.anomalies import (DeteccionInvalida, PoliticaAnomalias,  # noqa: E402,E501
                                       detectar_anomalias)


def _serie_base() -> list[float]:
    return [10.0 + (i % 3) * 0.1 for i in range(30)]


def test_detecta_outlier_claro():
    valores = _serie_base()
    valores[15] = 25.0  # anomalía evidente
    res = detectar_anomalias(valores, series="beam_current")
    assert len(res.anomalias) == 1
    assert res.anomalias[0].indice == 15
    assert res.auditoria["n_anomalias"] == 1  # 6.23: evento de auditoría
    assert "nunca actúa" in res.auditoria["nota"]


def test_serie_estable_sin_anomalias():
    res = detectar_anomalias(_serie_base())
    assert res.anomalias == []
    assert res.mad > 0


def test_datos_invalidos_rechazados_por_politica():
    valores = _serie_base()
    valores[3] = None
    with pytest.raises(DeteccionInvalida, match="6.23"):
        detectar_anomalias(valores)  # max_nan_frac=0.0 por defecto


def test_serie_insuficiente_rechazada():
    with pytest.raises(DeteccionInvalida, match="insuficiente"):
        detectar_anomalias([1.0, 2.0, 3.0])


def test_politica_externa_versionada():
    pol = PoliticaAnomalias(version="mad-strict-2.0.0", umbral_mad=3.0)
    valores = _serie_base()
    valores[20] = 12.5  # desviación moderada
    res = detectar_anomalias(valores, politica=pol)
    assert res.politica == "mad-strict-2.0.0"
    assert res.anomalias  # con umbral más estricto sí se detecta


def test_mad_cero_no_detecta():
    res = detectar_anomalias([5.0] * 20)
    assert res.anomalias == []
    assert res.mad == 0.0
