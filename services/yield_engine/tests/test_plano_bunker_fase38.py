"""Tests F38 — geometría real del búnker desde el plano DWG BIND."""
import json

import pytest

from app.domain.plano_bunker import (
    CASO_F32,
    GEOMETRIA_REAL,
    TOL_M,
    verificar_contra_f32,
)


def test_medidas_tienen_fuente_y_estado():
    for clave, g in GEOMETRIA_REAL.items():
        if isinstance(g, dict) and "estado" in g:
            assert g["estado"] in (
                "medido_sobre_plano", "observado_en_plano",
                "estimado_sobre_plano_pendiente_verificacion"), clave


def test_muro_oeste_coherente_con_envolvente():
    env = GEOMETRIA_REAL["envolvente_bunker_m"]
    assert env["ancho_m"] == pytest.approx(
        env["x"][1] - env["x"][0], abs=TOL_M)
    assert env["largo_m"] == pytest.approx(
        env["cota_plano_m"], abs=TOL_M)  # cota 15,499 del plano
    assert GEOMETRIA_REAL["muro_oeste_m"]["espesor_m"] >= 2.0


def test_verificacion_checklist_honesto():
    r = verificar_contra_f32()
    assert len(r["checks"]) == 5
    assert any(c["veredicto"] == "cumple" for c in r["checks"])
    assert any(c["veredicto"] == "pendiente" for c in r["checks"])
    assert "pendiente_entorno" in r["estado"]
    # nada de veredictos inflados: ningún "cumple" sin medida
    for c in r["checks"]:
        assert c["real"] and c["detalle"]


def test_caso_f32_declarado_no_modificado():
    # ALCOA+: el caso OIEA F32 se conserva como referencia histórica
    assert CASO_F32["boveda_m"] == (6.0, 6.0, 4.0)
    assert CASO_F32["laberinto_cambios"] == 1


def test_serializable_alcoa():
    s = json.dumps(verificar_contra_f32(), ensure_ascii=False)
    assert "BIND" in s and "muro" in s
