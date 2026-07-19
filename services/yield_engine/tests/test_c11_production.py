"""
Tests de producción de 11C: 14N(p,a)11C en blanco N2.

Referencia de validación: rendimientos a saturación calculados por la
IAEA-NDS Medical Portal (May-2021) a partir de la misma σ(E) recomendada.
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

# IAEA-NDS Medical Portal, yield table 14N(p,a)11C (saturación, GBq/µA, gas)
IAEA_SAT_GBQ_UA = {8.0: 1.76, 10.0: 2.71, 12.0: 4.08, 16.0: 7.47, 20.0: 9.84}


def test_rendimiento_11c_vs_iaea():
    """Saturación del motor vs. tabla IAEA: desviación < 8%."""
    for e_mev, ref_gbq in IAEA_SAT_GBQ_UA.items():
        res = service.compute(
            reaction_id="n14_p_a_c11", target_id="n2_gas",
            beam_energy_mev=e_mev, current_ua=1.0,
            irradiation_time_min=600.0)
        got_gbq = res.saturation_yield_mbq_ua / 1000.0
        desv = abs(got_gbq - ref_gbq) / ref_gbq
        assert desv < 0.08, f"E={e_mev}: motor={got_gbq:.2f} vs IAEA={ref_gbq:.2f} ({desv:.1%})"


def test_bajo_umbral_11c_cero():
    res = service.compute("n14_p_a_c11", "n2_gas", 2.5, 1.0, 20.0)
    assert res.saturation_yield_mbq_ua == 0.0


def test_media_vida_11c_factor_saturacion():
    """A t = T1/2 (20.364 min) el factor de saturación es 0.5."""
    res = service.compute("n14_p_a_c11", "n2_gas", 16.0, 1.0, 20.364)
    assert math.isclose(res.saturation_factor, 0.5, rel_tol=1e-3)


def test_caso_tipico_11c():
    """Caso típico: 16 MeV, 30 µA, 30 min, N2 gas."""
    res = service.compute("n14_p_a_c11", "n2_gas", 16.0, 30.0, 30.0)
    # sat ~7.4 GBq/µA; 30 min -> factor ~0.64; EOB ~ 7.4*30*0.64 ~ 142 GBq
    assert 100.0 < res.eob_activity_gbq < 190.0
    assert res.product_nuclide == "11C"
    assert res.dataset_id == "n14_p_a_c11_iaea2021"


def test_stopping_n2_positivo():
    s = service._stopping.stopping_power("n2", 10.0)
    assert 30.0 < s < 60.0
