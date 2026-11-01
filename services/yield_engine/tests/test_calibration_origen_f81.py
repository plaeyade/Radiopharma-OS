"""F81 — puerta de origen del Calibration Layer (memoria 3): la telemetría simulada declarada del gemelo nunca entra
al ajuste como medida de lote real, aunque sea numéricamente válida."""
from app.domain.calibration_batch import BatchMeasurement, quality_gate


def _m(**kw):
    base = dict(batch_id="L-0001", fecha="2026-10-28", eob_predicho_gbq=300.0, eob_medido_gbq=280.0,
                incertidumbre_gbq=10.0, operador="op1")
    base.update(kw)
    return BatchMeasurement(**base)


def test_real_por_defecto_se_acepta():
    g = quality_gate(_m())
    assert g["accepted"] and g["reasons"] == []


def test_simulado_declarado_se_rechaza_con_motivo():
    g = quality_gate(_m(origen="simulado_declarado"))
    assert not g["accepted"]
    assert any("memoria 3" in r for r in g["reasons"])
    assert g["k"] is not None            # el cociente se calcula y queda en auditoría, pero no entra al ajuste


def test_origen_desconocido_se_rechaza():
    g = quality_gate(_m(origen="estimado"))
    assert not g["accepted"] and any("origen desconocido" in r for r in g["reasons"])
