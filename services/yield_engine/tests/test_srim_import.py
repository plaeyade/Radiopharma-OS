"""Tests del importador de tablas SRIM reales (Fase 25).

Fixture REAL: las tres primeras filas del ejemplo documentado en el
manual oficial SRIM-2013, cap. 8 (srim.org/SRIM/SRIM 08.pdf) —
H en agua líquida, Stopping Units = MeV/(mg/cm2). Los valores son los
publicados en el manual (fuente citada), no inventados.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.infrastructure.stopping.srim_import import (
    SrimFormatoInvalido, parse_srim_table)

# Ejemplo literal del manual SRIM-2013 cap. 8 (H en agua, 10 keV–10 MeV).
# Valores S(Elec)/S(Nuc) = los impresos en el manual para las 3 primeras
# filas. Fuente: srim.org/SRIM/SRIM 08.pdf, ejemplo de salida.
SRIM_MANUAL_H2O = """\
Ion=Hydrogen, Mass=1.008
Tgt=H+O(Solid), Density=1 g/cm3
Stopping Units=MeV/(mg/cm2)
Energy(keV)   S(Elec)   S(Nuc)
 1.020E+00  1.751E-01  3.921E-02
 2.550E+00  2.694E-01  2.391E-02
 3.980E+00  3.264E-01  1.681E-02
"""


def test_parse_tabla_real_manual():
    t = parse_srim_table(SRIM_MANUAL_H2O)
    assert t["ion"] == "Hydrogen"
    assert t["masa_ion_u"] == 1.008
    assert t["unidades_originales"] == "MeV/(mg/cm2)"
    assert len(t["filas"]) == 3
    e0, s0 = t["filas"][0]
    assert e0 == pytest.approx(1.020e-3)          # keV → MeV
    # (0.1751 + 0.03921) MeV/(mg/cm2) × 1000 = MeV·cm²/g
    assert s0 == pytest.approx((0.1751 + 0.03921) * 1000.0)
    assert t["nota_honestidad"]


def test_unidades_masicas_equivalentes():
    base = SRIM_MANUAL_H2O.replace("MeV/(mg/cm2)", "keV/(mg/cm2)")
    t = parse_srim_table(base)
    assert t["filas"][0][1] == pytest.approx(0.1751 + 0.03921)


def test_rechaza_unidades_longitud_no_convertible():
    txt = SRIM_MANUAL_H2O.replace("MeV/(mg/cm2)", "MeV/mm")
    with pytest.raises(SrimFormatoInvalido, match="no_convertible"):
        parse_srim_table(txt)


def test_rechaza_basura_y_vacio():
    with pytest.raises(SrimFormatoInvalido):
        parse_srim_table("")
    with pytest.raises(SrimFormatoInvalido):
        parse_srim_table("hola\nmundo\n")


def test_rechaza_energias_no_monotonas():
    txt = SRIM_MANUAL_H2O.replace("2.550E+00", "1.010E+00")
    with pytest.raises(SrimFormatoInvalido, match="monótonas"):
        parse_srim_table(txt)


def test_rechaza_tabla_corta():
    txt = "\n".join(SRIM_MANUAL_H2O.splitlines()[:5]) + "\n"
    with pytest.raises(SrimFormatoInvalido, match="<3"):
        parse_srim_table(txt)


def test_rechaza_linea_corrupta_dentro_de_tabla():
    txt = SRIM_MANUAL_H2O + "ZZZ corrupto\n"
    with pytest.raises(SrimFormatoInvalido, match="irreconocible"):
        parse_srim_table(txt)


# ---------------------------------------------------------------------
# endpoint: importar → queda registrada_no_calibrada (nunca en cómputo)
# ---------------------------------------------------------------------

@pytest.fixture()
def client(tmp_path):
    from app.infrastructure.stopping.external_tables import (
        ExternalStoppingTables)
    from app.presentation.routers import stopping_tables_api

    class _SvcStub:  # sin proveedor activo: no se calibra en este test
        pass

    prev = (stopping_tables_api._tablas, stopping_tables_api._service)
    stopping_tables_api.init(ExternalStoppingTables(tmp_path), _SvcStub())
    from fastapi import FastAPI
    app = FastAPI()
    app.include_router(stopping_tables_api.router)
    yield TestClient(app)
    stopping_tables_api._tablas, stopping_tables_api._service = prev


def test_endpoint_importa_y_registra_con_fuente(client):
    r = client.post("/api/v1/stopping-power/external-tables/srim", json={
        "material": "agua",
        "fuente": "SRIM-2013 manual cap.8 (srim.org) — ejemplo H en agua",
        "ejecutado_en": "manual SRIM-2013, tabla impresa",
        "registrado_por": "qa",
        "texto_srim": SRIM_MANUAL_H2O})
    assert r.status_code == 201, r.text
    d = r.json()
    assert d["n_filas"] == 3
    assert d["parseo"]["ion"] == "Hydrogen"
    lst = client.get("/api/v1/stopping-power/external-tables").json()
    agua = [t for t in lst["tablas"] if t["material"] == "agua"]
    assert agua and agua[-1]["estado"] == "registrada_no_calibrada"


def test_endpoint_422_archivo_invalido(client):
    r = client.post("/api/v1/stopping-power/external-tables/srim", json={
        "material": "agua", "fuente": "x", "ejecutado_en": "y",
        "registrado_por": "qa", "texto_srim": "no es SRIM"})
    assert r.status_code == 422
