"""Tests del script de calificación DQ/IQ/OQ + PQ (fase 10, 14.9).

Regla bajo prueba: un criterio jamás se declara «cumple» sin verificación
real — si /health falla, IQ se ejecuta como NO superada (49.11).
"""
from __future__ import annotations

import importlib.util
import os

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_spec = importlib.util.spec_from_file_location(
    "calificar_plataforma_pq",
    os.path.join(RAIZ, "scripts", "calificar_plataforma_pq.py"))
mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mod)


class FakeHttp:
    """qc_engine en memoria: respeta el orden estricto DQ/IQ/OQ/PQ."""

    def __init__(self):
        self.base = "http://test"
        self.componentes: list[dict] = []
        self.protocolos: dict[str, list[dict]] = {}
        self.ejecuciones: list[dict] = []
        self.pq_protocolos: dict[str, dict] = {}

    def get(self, path):
        assert path == "/api/v1/qualification/components"
        return 200, self.componentes

    def post(self, path, body):
        if path == "/api/v1/qualification/components":
            self.componentes.append(body)
            return 201, {"componente_id": body["componente_id"]}
        if path.endswith("/protocols") and "qualification/pq" not in path:
            etapa = body["etapa"]
            version = len(self.protocolos.get(etapa, [])) + 1
            self.protocolos.setdefault(etapa, []).append(
                {**body, "version": version})
            return 201, {"etapa": etapa, "version": version}
        if path.endswith("/executions"):
            etapa = body["etapa"]
            orden = ["DQ", "IQ", "OQ"]
            idx = orden.index(etapa)
            for previa in orden[:idx]:
                assert any(e["etapa"] == previa and e["estado"] == "superada"
                           for e in self.ejecuciones), \
                    f"orden estricto: {previa} debe superarse antes de {etapa}"
            estado = ("superada" if all(r["cumple"] for r in body["resultados"])
                      else "fallida")
            ejec = {"etapa": etapa, "estado": estado,
                    "resultados": body["resultados"]}
            self.ejecuciones.append(ejec)
            return 201, {**ejec, "ejecucion_id": "X"}
        if path == "/api/v1/qualification/pq/protocols":
            self.pq_protocolos[body["protocolo_id"]] = body
            return 201, {"protocolo_id": body["protocolo_id"], "version": 1}
        raise AssertionError(path)


def test_iq_no_cumple_si_health_cae(monkeypatch):
    """Un servicio caído → IQ «fallida», jamás declarada superada."""
    http = FakeHttp()
    monkeypatch.setattr(mod, "health_200",
                        lambda h, p: (p != 8007,
                                      f":{p} {'200' if p != 8007 else 'FALLO'}"))
    mod.etapa(http, "DQ", "c0", "m", lambda: (True, "ok"), "ref")
    res = mod.etapa(http, "IQ", "servicios_instalados_health_200",
                    "motivo",
                    lambda: (False, ":8007 FALLO ConnectionError"),
                    "ref")
    assert res["estado"] == "fallida"
    assert res["verificado"] is False
    ejec = http.ejecuciones[-1]
    assert ejec["resultados"][0]["cumple"] is False


def test_flujo_dq_iq_oq_orden_estricto():
    """DQ→IQ→OQ con verificación verdadera → todas superadas, PQ definido."""
    http = FakeHttp()
    mod.asegurar_componente(http)
    for nombre in ("DQ", "IQ", "OQ"):
        res = mod.etapa(http, nombre, "c1", "m", lambda: (True, "ok"), "ref")
        assert res["estado"] == "superada"
    mod.definir_pq_deploy(http, http)
    pq = http.pq_protocolos["pq_deploy"]
    assert len(pq["criterios"]) == 8  # un /health por servicio
    assert {c["url"].split(":")[-1].split("/")[0] for c in pq["criterios"]} == {
        str(p) for p in mod.SERVICIOS.values()}


def test_componente_nunca_duplicado():
    """asegurar_componente no recrea un componente ya registrado."""
    http = FakeHttp()
    mod.asegurar_componente(http)
    mod.asegurar_componente(http)
    assert len(http.componentes) == 1
