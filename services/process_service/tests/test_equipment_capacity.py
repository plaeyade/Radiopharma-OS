"""Pruebas Fase 30: catálogo de equipamiento + capacidades."""
import math
import pytest

from app.domain import equipment_catalog as ec
from app.domain import production_capacity as pc


# ---- catálogo ----
def test_catalogos_tienen_fuente():
    for v in ec.CICLOTRONES_EXT.values():
        assert v["fuente"]
    for v in ec.MODULOS_SINTESIS.values():
        assert v["fuente"]
    for v in ec.KITS_RADIOQUIMICA.values():
        assert v["fuente"]
    for v in ec.MATERIALES_BLANCO.values():
        assert v["fuente"]
    for v in ec.FUENTES_IONES.values():
        assert v["fuente"]


def test_ciclotrones_clave_presentes():
    for cid in ("abt_bg75", "best_b100", "best_b6_15", "ge_pettrace_840",
                "ge_pettrace_860", "ge_pettrace_880", "lbt_7", "lbt_11", "lbt_20"):
        assert cid in ec.CICLOTRONES_EXT
    assert ec.CICLOTRONES_EXT["abt_bg75"]["energia_mev"] == 7.5
    assert ec.CICLOTRONES_EXT["ge_pettrace_840"]["corriente_max_ua"] == 60.0


def test_modulos_y_kits_pedidos():
    for m in ("neptis_rs", "neptis_db", "neptis_lc", "neptis_perform",
              "trasis_allinone", "trasis_miniallinone", "iba_cassy",
              "scintomics_grp4v"):
        assert m in ec.MODULOS_SINTESIS
    for k in ("abx_fdg_kit", "scintomics_kits", "trasis_kits"):
        assert k in ec.KITS_RADIOQUIMICA


def test_estatus_proveedor_no_autorizado_advierte():
    r = ec.validar_estatus_proveedor("tercero_no_autorizado")
    assert "ADVERTENCIA" in r
    assert ec.validar_estatus_proveedor("oem_original") == "oem_original"
    with pytest.raises(ValueError):
        ec.validar_estatus_proveedor("pirata")


def test_tantalio_vs_plata_datos_citados():
    assert ec.MATERIALES_BLANCO["plata"]["conductividad_w_mk"] == 415.0
    assert ec.MATERIALES_BLANCO["tantalio"]["conductividad_w_mk"] == 57.0


def test_optimizacion_fuente_iones():
    r = ec.recomendacion_fuente_iones("penning_pettrace")
    assert "RECOMENDACIÓN" in r["naturaleza"]
    assert r["vida_catodo"].startswith("16-26 semanas")
    with pytest.raises(ValueError):
        ec.recomendacion_fuente_iones("inventada")


# ---- capacidades ----
def test_f18_saturacion_formula_exacta():
    r = pc.capacidad_f18("ge_pettrace_840", 60.0, 60.0)
    lam = math.log(2) / (109.77 * 60)
    esperado = 60.0 * 8.9 * (1 - math.exp(-lam * 3600))
    assert r["actividad_eob_gb"] == pytest.approx(esperado, rel=1e-3)
    assert r["modelo"] == "saturación con Y_sat citado"


def test_f18_bg75_usa_modelo_vendedor_no_extrapola():
    r = pc.capacidad_f18("abt_bg75", 5.0, 40.0)
    assert r["modelo"].startswith("modelo_vendedor")
    assert "NO" in r["advertencia"]
    assert r["actividad_eob_gb"] == pytest.approx(40 * 0.037, rel=1e-3)  # 40 mCi


def test_f18_exceder_corriente_rechazado():
    with pytest.raises(ValueError, match="máximo citado"):
        pc.capacidad_f18("abt_bg75", 5.5, 30.0)


def test_f18_lbt_calcula_con_corriente_declarada():
    # LBT no tiene máximo citado: el tablero lo marca pendiente; el cálculo
    # directo con corriente declarada por el usuario sí es posible.
    r = pc.capacidad_f18("lbt_20", 100.0, 60.0)
    assert r["actividad_eob_gb"] > 0
    assert r["fuente"]


def test_n13_escala_citada():
    r = pc.capacidad_n13("ge_pettrace_840", 55.0, 40.0)
    assert r["actividad_eob_gb"] == pytest.approx(29.0, rel=1e-3)
    with pytest.raises(ValueError, match="no demostrable"):
        pc.capacidad_n13("abt_bg75", 5.0, 20.0)


def test_cu64_ventana_citada():
    r = pc.capacidad_cu64("ge_pettrace_840", 20.0, 4.0)
    lam_h = math.log(2) / 12.7
    esperado_mbq = 20.0 * 228.0 / lam_h * (1 - math.exp(-lam_h * 4))
    assert r["actividad_eob_gb"] == pytest.approx(esperado_mbq / 1000, rel=1e-3)
    with pytest.raises(ValueError, match="12 MeV"):
        pc.capacidad_cu64("abt_bg75", 5.0, 4.0)


def test_tablero_marca_pendientes():
    t = pc.tablero_capacidades()
    estados = {e["ciclotron"]: e.get("estado") for e in t["escenarios"]}
    assert "pendiente_fuente" in estados["lbt_7"]
    assert estados["abt_bg75"] is None  # tiene cálculo real


# ---- API ----
def test_api_equipamiento():
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient
    from app.main import app
    c = TestClient(app)
    assert c.get("/api/v1/equipamiento/ciclotrones").status_code == 200
    assert c.get("/api/v1/equipamiento/modulos-sintesis").status_code == 200
    assert c.get("/api/v1/equipamiento/kits").status_code == 200
    r = c.post("/api/v1/equipamiento/capacidad/f18",
               json={"ciclotron_id": "abt_bg75", "corriente": 5.0, "tiempo": 40.0})
    assert r.status_code == 201 or r.status_code == 200
    assert r.json()["modelo"].startswith("modelo_vendedor")
    r2 = c.get("/api/v1/equipamiento/capacidad/tablero")
    assert r2.status_code == 200
    r3 = c.get("/api/v1/equipamiento/fuentes-iones/penning_pettrace/optimizacion")
    assert "RECOMENDACIÓN" in r3.json()["naturaleza"]
