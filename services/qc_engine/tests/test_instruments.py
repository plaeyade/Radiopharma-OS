"""Pruebas del Instrument Integration Layer (EDS cap. 26)."""
from __future__ import annotations

import base64
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.domain.instruments import (FileImportManager, Instrument,  # noqa: E402,E501
                                    InstrumentoInvalido, InstrumentRegistry,
                                    normalizar_cromatograma,
                                    normalizar_espectro_gamma,
                                    normalizar_tabla)
from app.main import app  # noqa: E402

client = TestClient(app)

HPLC_CSV = """tiempo_min,senal
0.0,0.0
1.0,0.1
2.0,0.2
3.0,1.0
4.0,50.0
5.0,80.0
6.0,45.0
7.0,1.0
8.0,0.2
9.0,0.1
10.0,0.0
"""

ESPECTRO_CSV = """energia_kev,cuentas
100,5
200,8
300,10
400,20
511,900
600,30
700,10
"""

TABLA_CSV = """parametro,valor
ph,7.1
k222_ppm,12.0
acetonitrilo_ppm,80.0
"""


def test_normalizacion_cromatograma_pureza():
    res = normalizar_cromatograma(HPLC_CSV, tiempo_pico_esperado_min=5.0)
    assert res["tiempo_pico_min"] == pytest.approx(5.0)
    assert res["pureza_radioquimica_pct"] > 95.0
    assert res["desviacion_rt_min"] == pytest.approx(0.0, abs=1e-9)


def test_normalizacion_espectro_identidad_f18():
    res = normalizar_espectro_gamma(ESPECTRO_CSV)
    assert res["energia_pico_kev"] == pytest.approx(511.0)
    assert res["identidad_radionuclidica_ok"] == 1.0


def test_normalizacion_tabla():
    res = normalizar_tabla(TABLA_CSV)
    assert res == {"ph": 7.1, "k222_ppm": 12.0, "acetonitrilo_ppm": 80.0}


def test_registry_nunca_sobrescribe():
    reg = InstrumentRegistry()
    inst = Instrument("hplc-01", "hplc", "Agilent", "1260", "lab QC",
                      "csv_cromatograma", "cfg-1.0.0")
    reg.register(inst)
    with pytest.raises(InstrumentoInvalido, match="26.6"):
        reg.register(inst)


def test_importacion_con_auditoria_26_13():
    reg = InstrumentRegistry()
    reg.register(Instrument("gc-01", "gc", "Shimadzu", "GC-2030", "lab",
                            "csv_tabla", "cfg-1.0.0"))
    fim = FileImportManager(reg)
    res = fim.importar("gc-01", "lote42_gc.csv", TABLA_CSV.encode(),
                       "disolventes_residuales", operador="qa", batch="L-42")
    assert res.resultados["k222_ppm"] == 12.0
    assert res.archivo_sha256
    assert res.auditoria["batch"] == "L-42"  # 26.13
    assert "26.12" in res.auditoria["nota"]
    assert len(fim.eventos()) == 1  # 26.20


def test_endpoints_cap26():
    r = client.post("/api/v1/qc/instruments/register", json={
        "instrument_id": "hplc-e2e", "tipo": "hplc", "fabricante": "Agilent",
        "modelo": "1260", "ubicacion": "lab", "formato_export":
        "csv_cromatograma", "configuracion": "cfg-1.0.0", "validado": False})
    assert r.status_code == 201
    r2 = client.post("/api/v1/qc/instruments/hplc-e2e/import", json={
        "nombre_archivo": "lote1_hplc.csv",
        "contenido_b64": base64.b64encode(HPLC_CSV.encode()).decode(),
        "ensayo": "pureza_radioquimica", "operador": "qa", "batch": "L-1"})
    assert r2.status_code == 201
    cuerpo = r2.json()
    assert cuerpo["resultados"]["pureza_radioquimica_pct"] > 95.0
    assert cuerpo["archivo_sha256"]
    ev = client.get("/api/v1/qc/instruments/events").json()
    assert any(e["batch"] == "L-1" for e in ev)


def test_import_instrumento_desconocido_422():
    r = client.post("/api/v1/qc/instruments/fantasma/import", json={
        "nombre_archivo": "x.csv", "contenido_b64": "eA==",
        "ensayo": "ph", "operador": "qa", "batch": "L-9"})
    assert r.status_code == 422
