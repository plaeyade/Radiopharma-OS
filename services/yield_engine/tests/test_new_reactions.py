"""
Tests de producción de 15O y 68Ga (v0.3.0).

Referencias: rendimientos a saturación calculados por IAEA-NDS Medical
Portal (May-2021) a partir de las mismas σ(E) recomendadas.
"""
from __future__ import annotations

import math
from pathlib import Path

from app.main import DATA_DIR
from app.application.production_service import ProductionService
from app.infrastructure.repositories.local_reaction_data import LocalReactionDataProvider
from app.infrastructure.stopping.factory import build_stopping_provider

service = ProductionService(
    stopping=build_stopping_provider(DATA_DIR / "stopping"),
    rxn=LocalReactionDataProvider(DATA_DIR),
)

# IAEA yield tables, columna saturación [MBq/µA]
IAEA_O15 = {8.0: 1680.0, 10.0: 2360.0, 12.0: 3350.0, 16.0: 6000.0, 20.0: 7730.0}
IAEA_GA68 = {8.0: 1940.0, 10.0: 4600.0, 12.0: 8460.0, 16.0: 15000.0, 20.0: 17500.0}


def test_rendimiento_15o_vs_iaea():
    for e_mev, ref in IAEA_O15.items():
        res = service.compute("n15_p_n_o15", "n15_gas", e_mev, 1.0, 60.0)
        desv = abs(res.saturation_yield_mbq_ua - ref) / ref
        assert desv < 0.08, f"E={e_mev}: {res.saturation_yield_mbq_ua:.0f} vs {ref:.0f} ({desv:.1%})"


def test_rendimiento_68ga_vs_iaea():
    for e_mev, ref in IAEA_GA68.items():
        res = service.compute("zn68_p_n_ga68", "zn68", e_mev, 1.0, 60.0)
        desv = abs(res.saturation_yield_mbq_ua - ref) / ref
        assert desv < 0.08, f"E={e_mev}: {res.saturation_yield_mbq_ua:.0f} vs {ref:.0f} ({desv:.1%})"


def test_15o_saturacion_rapida():
    """T1/2 = 122 s: a 10 min el factor de saturación es ~0.97."""
    res = service.compute("n15_p_n_o15", "n15_gas", 16.0, 1.0, 10.0)
    assert res.saturation_factor > 0.96


def test_68ga_bajo_umbral_cero():
    res = service.compute("zn68_p_n_ga68", "zn68", 3.0, 1.0, 60.0)
    assert res.saturation_yield_mbq_ua == 0.0


def test_caso_tipico_68ga():
    """Caso típico 68Ga: 14.5 MeV, 25 µA, 60 min (blanco líquido)."""
    res = service.compute("zn68_p_n_ga68", "zn68", 14.5, 25.0, 60.0)
    assert 50.0 < res.eob_activity_gbq < 250.0
    assert res.product_nuclide == "68Ga"
