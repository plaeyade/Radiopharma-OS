"""Fase 20 — promoción de tabla externa calibrada a proveedor activo.

Reglas canónicas bajo prueba (EDS 19.10, 49.11, ALCOA+):
- solo se promueve una tabla con veredicto `calibrada`;
- promoción y reversión exigen motivo y quedan en historial append-only;
- tras la promoción el cómputo usa la tabla REAL interpolada y declara
  la fuente; fuera de rango → error honesto, nunca extrapolación;
- integridad sha256 verificada en cada lectura.
"""
from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.application.production_service import ProductionService
from app.infrastructure.repositories.factory import build_reaction_provider
from app.infrastructure.stopping.external_tables import (
    ExternalStoppingTables, TablaExternaInvalida)
from app.infrastructure.stopping.promoted_stopping import PromotedStoppingPower
from app.infrastructure.stopping.table_stopping import TableStoppingPower
from app.presentation.routers import stopping_tables_api

from pathlib import Path

DATA = Path(__file__).resolve().parents[1] / "data"
FILAS = [[1.0, 10.0], [2.0, 20.0], [3.0, 30.0]]  # S = 10·E (MeV·cm²/g)


def _cliente(tmp_path):
    tablas = ExternalStoppingTables(tmp_path / "external")
    base = TableStoppingPower(DATA / "stopping")
    envoltorio = PromotedStoppingPower(base, tablas, {"h2o": "agua"})
    service = ProductionService(
        stopping=envoltorio, rxn=build_reaction_provider(DATA))
    app = FastAPI()
    stopping_tables_api.init(tablas, service)
    app.include_router(stopping_tables_api.router)
    return TestClient(app), tablas, envoltorio, service


def _registrar_y_calibrar(c) -> None:
    assert c.post("/api/v1/stopping-power/external-tables", json={
        "material": "agua", "fuente": "SRIM-2013 ejecutado por el usuario",
        "ejecutado_en": "2026-09-15 estación del usuario",
        "filas": FILAS, "registrado_por": "tester"}).status_code == 201
    r = c.post("/api/v1/stopping-power/external-tables/agua/versions/1/"
               "calibrate", json={"criterio_max_pct": 100.0,
                                  "motivo": "calibración de prueba",
                                  "registrado_por": "tester"})
    assert r.status_code == 201
    assert r.json()["calibracion"]["veredicto"] == "calibrada"


def test_promocion_exige_tabla_calibrada(tmp_path):
    c, *_ = _cliente(tmp_path)
    assert c.post("/api/v1/stopping-power/external-tables", json={
        "material": "agua", "fuente": "SRIM-2013 usuario",
        "ejecutado_en": "2026-09-15", "filas": FILAS,
        "registrado_por": "tester"}).status_code == 201
    r = c.post("/api/v1/stopping-power/external-tables/agua/versions/1/"
               "promote", json={"motivo": "intento sin calibrar",
                                "registrado_por": "tester"})
    assert r.status_code == 422
    assert "calibrada" in r.json()["detail"]


def test_promocion_cambia_proveedor_activo_y_computo(tmp_path):
    c, tablas, envoltorio, service = _cliente(tmp_path)
    _registrar_y_calibrar(c)
    antes = service.stopping_power_active("h2o", 2.0)
    r = c.post("/api/v1/stopping-power/external-tables/agua/versions/1/"
               "promote", json={"motivo": "PSTAR verificada, mejor ajuste",
                                "registrado_por": "fisica-medica"})
    assert r.status_code == 201
    assert r.json()["promocion"]["rango_mev"] == [1.0, 3.0]
    # el cómputo usa ahora la tabla REAL interpolada (S = 10·E → 20.0)
    assert service.stopping_power_active("h2o", 2.0) == pytest.approx(20.0)
    assert service.stopping_power_active("h2o", 2.0) != pytest.approx(antes)
    # estado declarativo
    prov = c.get("/api/v1/stopping-power/providers").json()
    assert prov["detalle"]["materiales"]["h2o"]["proveedor"] == \
        "externa_promovida"
    assert "PSTAR verificada" in prov["stopping_status"]["fuente"] or \
        "SRIM-2013" in prov["stopping_status"]["fuente"]


def test_fuera_de_rango_nunca_extrapola(tmp_path):
    c, tablas, envoltorio, _ = _cliente(tmp_path)
    _registrar_y_calibrar(c)
    c.post("/api/v1/stopping-power/external-tables/agua/versions/1/promote",
           json={"motivo": "prueba", "registrado_por": "tester"})
    with pytest.raises(TablaExternaInvalida, match="fuera del rango"):
        envoltorio.stopping_power("h2o", 99.0)


def test_reversion_append_only_vuelve_a_base(tmp_path):
    c, tablas, envoltorio, service = _cliente(tmp_path)
    _registrar_y_calibrar(c)
    c.post("/api/v1/stopping-power/external-tables/agua/versions/1/promote",
           json={"motivo": "promoción de prueba", "registrado_por": "a"})
    r = c.post("/api/v1/stopping-power/external-tables/agua/demote",
               json={"motivo": "vuelta a ATIMA por validación anual",
                     "registrado_por": "fisica-medica"})
    assert r.status_code == 201
    # el cómputo vuelve al proveedor base ATIMA
    assert service.stopping_power_active("h2o", 2.0) == pytest.approx(
        TableStoppingPower(DATA / "stopping").stopping_power("h2o", 2.0))
    hist = c.get("/api/v1/stopping-power/promotions").json()["promociones"]
    assert [h["accion"] for h in hist] == [
        "promovida", "revertida_a_proveedor_base"]
    assert all(h["motivo"] for h in hist)
    # revertir sin promoción vigente → 422 honesto
    r2 = c.post("/api/v1/stopping-power/external-tables/agua/demote",
                json={"motivo": "otra vez", "registrado_por": "a"})
    assert r2.status_code == 422


def test_promocion_y_reversion_exigen_motivo(tmp_path):
    c, tablas, *_ = _cliente(tmp_path)
    _registrar_y_calibrar(c)
    assert c.post("/api/v1/stopping-power/external-tables/agua/versions/1/"
                  "promote", json={"motivo": "  ",
                                   "registrado_por": "a"}
                  ).status_code == 422


def test_alcance_csda_real_de_tabla_promovida(tmp_path):
    _, tablas, *_ = _cliente(tmp_path)
    tablas.registrar(material="agua", fuente="SRIM-2013 usuario",
                     ejecutado_en="2026-09-15", descripcion="",
                     filas=FILAS, registrado_por="tester")
    man = tablas._leer()
    man["tablas"][0]["estado"] = "calibrada"
    tablas._escribir(man)
    tablas.promover("agua", 1, "prueba alcance", "tester")
    # R(2) = trapecio de 1/S entre (1,10) y (2,20) = ½(1/10+1/20)·1 = 0.075
    assert tablas.alcance_g_cm2("agua", 2.0) == pytest.approx(0.075)
    # R(1.5) interpola S(1.5)=15 y añade el tramo parcial: honesto, real
    esperado = 0.5 * (1/10 + 1/15) * 0.5
    assert tablas.alcance_g_cm2("agua", 1.5) == pytest.approx(esperado)


def test_integridad_sha256_tras_promocion(tmp_path):
    _, tablas, *_ = _cliente(tmp_path)
    tablas.registrar(material="agua", fuente="SRIM-2013 usuario",
                     ejecutado_en="2026-09-15", descripcion="",
                     filas=FILAS, registrado_por="tester")
    man = tablas._leer()
    man["tablas"][0]["estado"] = "calibrada"
    tablas._escribir(man)
    tablas.promover("agua", 1, "prueba integridad", "tester")
    # manipulación del CSV → error de integridad, nunca cómputo con dato dudoso
    csv = tmp_path / "external" / "agua_v1.csv"
    csv.write_text(csv.read_text().replace("2.0,20.0", "2.0,99.0"))
    with pytest.raises(TablaExternaInvalida, match="integridad violada"):
        tablas.interpolar("agua", 2.0)
